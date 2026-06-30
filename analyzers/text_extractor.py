from pathlib import Path

from docx import Document
from pypdf import PdfReader


def _read_plain_text(filepath):
    with open(filepath, "r", encoding="utf-8") as file:
        text = file.read()
    # Normalize line endings and preserve structure
    return text.strip()


def _read_pdf_text(filepath):
    reader = PdfReader(filepath)
    page_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        # Preserve structure by keeping non-empty pages with double newline separation
        if text.strip():
            page_text.append(text.strip())
    return "\n\n".join(page_text)


def _read_docx_text(filepath):
    document = Document(filepath)
    text_parts = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            text_parts.append(text)
    # Use double newlines to preserve section structure
    return "\n\n".join(text_parts)


def extract_text(filepath):
    extension = Path(filepath).suffix.lower()

    if extension in {".txt", ".md", ".json"}:
        return _read_plain_text(filepath)
    if extension == ".pdf":
        return _read_pdf_text(filepath)
    if extension == ".docx":
        return _read_docx_text(filepath)

    raise ValueError(f"Unsupported file type: {extension}")