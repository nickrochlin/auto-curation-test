"""
Turn documentation files into plain text: .txt, .md, .docx and .pdf.

Word files are read with Python's built-in tools (tables included).
PDFs need one extra library:  pip install pypdf

You can also run it on a file directly to see what the model will see:
    python read_documents.py path/to/README.pdf
"""

from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

TEXT_TYPES = (".txt", ".md", ".markdown", ".rst", ".json", ".xml")
DOC_TYPES = TEXT_TYPES + (".docx", ".pdf")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_paragraph(p) -> str:
    parts = []
    for node in p.iter():
        if node.tag == W + "t" and node.text:
            parts.append(node.text)
        elif node.tag == W + "tab":
            parts.append("\t")
        elif node.tag in (W + "br", W + "cr"):
            parts.append("\n")
    return "".join(parts)


def read_docx(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    lines = []
    for block in body:
        if block.tag == W + "p":
            lines.append(_docx_paragraph(block))
        elif block.tag == W + "tbl":
            # Tables (often the data dictionary) become one row per line: cell | cell | cell
            for row in block.iter(W + "tr"):
                cells = [" ".join(_docx_paragraph(p) for p in cell.iter(W + "p")).strip()
                         for cell in row.iter(W + "tc")]
                lines.append(" | ".join(cells))
            lines.append("")
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text, ""


def read_pdf(path: Path) -> tuple[str, str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "PDF not read: run  pip install pypdf  and try again"
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as e:  # damaged or password-protected PDFs
        return "", f"PDF could not be read ({e.__class__.__name__})"
    text = "\n\n".join(f"[page {i + 1}]\n{t.strip()}" for i, t in enumerate(pages) if t.strip())
    chars = sum(len(t.strip()) for t in pages)
    if pages and chars / len(pages) < 50:
        return text, (f"PDF has {len(pages)} page(s) but almost no readable text; it is probably "
                      "scanned images and would need OCR")
    return text, ""


def extract_text(path: Path) -> tuple[str, str]:
    """Return (text, note). The note explains any problem reading the file."""
    suffix = path.suffix.lower()
    if suffix in TEXT_TYPES:
        return path.read_text(encoding="utf-8", errors="replace"), ""
    if suffix == ".docx":
        try:
            return read_docx(path)
        except (zipfile.BadZipFile, KeyError, ET.ParseError):
            return "", "Word file could not be read (it may be damaged or not a real .docx)"
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".doc":
        return "", "old Word format (.doc) not read; save it as .docx"
    return "", f"{suffix} files are not read"


if __name__ == "__main__":
    for p in sys.argv[1:]:
        text, note = extract_text(Path(p))
        print(f"== {p} ==")
        if note:
            print(f"NOTE: {note}")
        print(text)
        print()
