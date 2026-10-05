"""SSRF-hardened HTTP fetcher for live web research.

Controls:
* scheme allowlist (http/https) and port allowlist;
* every hostname is resolved and *all* resolved addresses must be public (no loopback, private,
  link-local - which includes cloud metadata 169.254.169.254 - multicast, reserved or unspecified);
* the connection is pinned to the validated IP (Host header + TLS SNI keep the original name), which
  closes the DNS-rebinding window between check and connect;
* redirects are followed manually (max 5) and each hop is re-validated;
* response size is capped while streaming, content types are allowlisted, and credentials in URLs are
  rejected.
Residual risk and network-level controls (egress firewall in Azure) are described in docs/threat-model.md.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from sip.research.html import extract_html
from sip.research.injection import screen
from sip.research.search.base import FetchedPage, FetchError
from sip.research.source_typing import infer_source_type
from sip.research.text import clean_untrusted

ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml", "text/plain", "application/pdf"}
MAX_REDIRECTS = 5
USER_AGENT = "StrategicInvestigationPlatform/0.2 (+research; respects robots via provider)"


def _is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


async def resolve_public(host: str, port: int) -> str:
    """Resolve ``host`` and return one address, refusing if *any* resolved address is not public."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"Cannot resolve host {host}") from exc
    addrs = sorted({str(i[4][0]) for i in infos})
    if not addrs:
        raise FetchError(f"No addresses for {host}")
    blocked = [a for a in addrs if not _is_public(a)]
    if blocked:
        raise FetchError(f"Refusing to fetch {host}: resolves to non-public address")
    return addrs[0]


def validate_url(url: str, allowed_ports: set[int]) -> tuple[str, str, int]:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise FetchError(f"Scheme '{parts.scheme}' is not allowed")
    if parts.username or parts.password:
        raise FetchError("Credentials in URLs are not allowed")
    if not parts.hostname:
        raise FetchError("URL has no host")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port not in allowed_ports:
        raise FetchError(f"Port {port} is not allowed")
    try:  # literal IPs are checked directly
        if not _is_public(parts.hostname):
            raise FetchError("Refusing to fetch a non-public IP literal")
    except ValueError:
        pass
    return parts.scheme, parts.hostname, port


class SafeFetcher:
    def __init__(
        self,
        *,
        timeout_s: float = 15.0,
        max_bytes: int = 3_000_000,
        allowed_ports: set[int] | None = None,
        client: httpx.AsyncClient | None = None,
        resolver: Callable[[str, int], Awaitable[str]] = resolve_public,
    ) -> None:
        self.timeout_s = timeout_s
        self.max_bytes = max_bytes
        self.allowed_ports = allowed_ports or {80, 443}
        self._client = client or httpx.AsyncClient(timeout=timeout_s, follow_redirects=False)
        self._resolve = resolver

    async def fetch(self, url: str) -> FetchedPage:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            scheme, host, port = validate_url(current, self.allowed_ports)
            ip = await self._resolve(host, port)
            parts = urlsplit(current)
            netloc_ip = f"[{ip}]" if ":" in ip else ip
            pinned = urlunsplit((scheme, f"{netloc_ip}:{port}", parts.path or "/", parts.query, ""))
            headers = {
                "Host": parts.netloc.split("@")[-1],
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,text/plain,application/pdf",
            }
            extensions = {"sni_hostname": host} if scheme == "https" else {}
            async with self._client.stream("GET", pinned, headers=headers, extensions=extensions) as resp:
                if resp.status_code in {301, 302, 303, 307, 308}:
                    location = resp.headers.get("location")
                    if not location:
                        raise FetchError("Redirect without location")
                    current = urljoin(current, location)
                    continue
                if resp.status_code >= 400:
                    raise FetchError(f"HTTP {resp.status_code}")
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype not in ALLOWED_CONTENT_TYPES:
                    raise FetchError(f"Content type '{ctype}' not allowed")
                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.max_bytes:
                        raise FetchError("Response exceeds size limit")
            try:
                return self._to_page(current, ctype, bytes(body))
            except Exception as exc:  # unreadable content (bad PDF, odd encoding) is a failed fetch, not a crash
                raise FetchError(f"Could not read content: {exc.__class__.__name__}") from exc
        raise FetchError("Too many redirects")

    @staticmethod
    def _to_page(url: str, ctype: str, body: bytes) -> FetchedPage:
        host = urlsplit(url).hostname or ""
        if ctype in {"text/html", "application/xhtml+xml"}:
            doc = extract_html(body.decode("utf-8", errors="replace"))
            raw_text, title = doc.text, doc.title or url
            published, updated, publisher = doc.published_on, doc.updated_on, doc.site_name
        elif ctype == "application/pdf":
            from sip.privacy.extraction import extract_text

            raw_text, title, published, updated, publisher = extract_text(body, ctype), url, None, None, None
        else:
            raw_text, title, published, updated, publisher = (
                body.decode("utf-8", errors="replace"),
                url,
                None,
                None,
                None,
            )
        flags = sorted({f.kind for f in screen(raw_text)})
        text = clean_untrusted(raw_text)[:60_000]
        return FetchedPage(
            url=url,
            title=title[:300],
            text=text,
            content_type=ctype,
            sha256=hashlib.sha256(body).hexdigest(),
            publisher=publisher or host,
            domain=host,
            published_on=published,
            updated_on=updated,
            source_type_hint=infer_source_type(host, title),
            injection_flags=flags,
            provider="web",
        )
