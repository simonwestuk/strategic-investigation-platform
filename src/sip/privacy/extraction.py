"""Safe text extraction from uploaded files (runs inside the privacy boundary)."""

from __future__ import annotations

import io
import json
from pathlib import PurePath

ALLOWED_EXTENSIONS = {".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv",
                      ".json": "application/json", ".pdf": "application/pdf"}
MAX_PDF_PAGES = 200


class UnsupportedFile(ValueError):
    pass


def safe_filename(name: str) -> str:
    """Strip any path components and control characters from a client-supplied filename."""
    base = PurePath(name.replace("\\", "/")).name
    cleaned = "".join(ch for ch in base if ch.isprintable() and ch not in '<>:"|?*')
    return cleaned[:200] or "upload"


def detect_content_type(filename: str, content: bytes) -> str:
    ext = PurePath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFile(f"File type '{ext or 'none'}' is not accepted.")
    expected = ALLOWED_EXTENSIONS[ext]
    is_pdf = content.startswith(b"%PDF-")
    if expected == "application/pdf" and not is_pdf:
        raise UnsupportedFile("File extension is .pdf but content is not a PDF.")
    if expected != "application/pdf" and is_pdf:
        raise UnsupportedFile("PDF content uploaded with a non-PDF extension.")
    return expected


def extract_text(content: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise UnsupportedFile("Encrypted PDFs are not accepted.")
        pages = reader.pages[:MAX_PDF_PAGES]
        return "\n\n".join((p.extract_text() or "") for p in pages)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnsupportedFile("Text files must be UTF-8.") from exc
    if content_type == "application/json":
        try:
            return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            raise UnsupportedFile("Invalid JSON.") from exc
    return text.replace("\x00", "")
