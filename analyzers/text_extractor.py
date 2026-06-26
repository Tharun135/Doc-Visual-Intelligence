from pathlib import Path

from docx import Document
from pypdf import PdfReader


def _read_plain_text(filepath):
    with open(filepath, "r", encoding="utf-8") as file:
        return file.read()


def _read_pdf_text(filepath):
    reader = PdfReader(filepath)
    page_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            page_text.append(text.strip())
    return "\n\n".join(page_text)


def _read_docx_text(filepath):
    document = Document(filepath)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs)


def extract_text(filepath):
    extension = Path(filepath).suffix.lower()

    if extension in {".txt", ".md", ".json"}:
        return _read_plain_text(filepath)
    if extension == ".pdf":
        return _read_pdf_text(filepath)
    if extension == ".docx":
        return _read_docx_text(filepath)

    raise ValueError(f"Unsupported file type: {extension}")