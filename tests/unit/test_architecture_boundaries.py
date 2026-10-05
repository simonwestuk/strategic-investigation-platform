"""Structural guarantees that documentation alone cannot give.

* Nothing on the agent side of the privacy boundary may import raw-content stores, the vault or the
  detectors (which handle raw values).
* Application code never reads evaluation ground truth.
* Agents never import persistence or vendor model SDKs directly.
"""

import ast
from pathlib import Path

from sip.config import REPO_ROOT

SRC = REPO_ROOT / "src" / "sip"
AGENT_SIDE = ["graph", "agents", "research", "tools", "evidence", "retrieval"]
PRIVACY_INTERNALS = {
    "sip.privacy.vault",
    "sip.privacy.quarantine",
    "sip.privacy.detectors",
    "sip.privacy.azure_language",
    "sip.privacy.gateway",
    "sip.privacy.sensitivity",
}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def files(packages: list[str]) -> list[Path]:
    return [p for pkg in packages for p in (SRC / pkg).rglob("*.py")]


def test_agent_side_cannot_reach_raw_content_or_the_vault() -> None:
    offenders = {str(p.relative_to(SRC)): sorted(imports(p) & PRIVACY_INTERNALS) for p in files(AGENT_SIDE)}
    assert {k: v for k, v in offenders.items() if v} == {}


def test_agents_do_not_touch_persistence_or_vendor_sdks() -> None:
    banned = ("sip.persistence", "openai", "azure", "sqlalchemy")
    offenders = {
        str(p.relative_to(SRC)): sorted(i for i in imports(p) if i.startswith(banned))
        for p in files(["graph", "agents", "evidence", "tools"])
    }
    assert {k: v for k, v in offenders.items() if v} == {}


def test_application_never_reads_ground_truth() -> None:
    for p in SRC.rglob("*.py"):
        text = p.read_text()
        assert "ground_truth" not in text and "evals/scenarios" not in text, p


def test_core_is_domain_agnostic() -> None:
    words = ("apprentice", "northstar", "enrolment", "coffee", "harbourline")
    for pkg in ["domain", "graph", "agents", "evidence", "governance", "tools", "research"]:
        for p in (SRC / pkg).rglob("*"):
            if p.suffix in {".py", ".yaml", ".md"}:
                text = p.read_text().lower()
                hits = [w for w in words if w in text]
                assert not hits, f"{p.relative_to(SRC)} mentions {hits}"
