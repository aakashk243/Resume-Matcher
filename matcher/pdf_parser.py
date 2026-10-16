"""Step 1 of the pipeline: turn an uploaded resume / JD into raw text.

Supports PDF (pdfplumber, with pypdf as a fallback), DOCX (optional, needs
python-docx) and plain-text files.
"""
from __future__ import annotations

import io
import os


class ParseError(Exception):
    pass


def _pdf_text(data: bytes) -> str:
    text = ""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:
        text = ""
    if len(text.strip()) < 20:  # fall back to pypdf for odd layouts
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as exc:  # pragma: no cover
            raise ParseError(f"Could not read PDF: {exc}") from exc
    if not text.strip():
        raise ParseError("The PDF has no extractable text (is it a scanned image?).")
    return text


def _docx_text(data: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError as exc:
        raise ParseError("DOCX support needs `pip install python-docx`.") from exc
    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(filename: str, data: bytes) -> str:
    """Return the text of an uploaded file based on its extension."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext == ".pdf":
        return _pdf_text(data)
    if ext == ".docx":
        return _docx_text(data)
    if ext in {".txt", ".md", ""}:
        return data.decode("utf-8", errors="ignore")
    raise ParseError(f"Unsupported file type '{ext}'. Use PDF, DOCX or TXT.")


def extract_text_from_path(path: str) -> str:
    with open(path, "rb") as fh:
        return extract_text(path, fh.read())
