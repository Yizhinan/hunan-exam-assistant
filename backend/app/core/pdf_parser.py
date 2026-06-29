"""PDF and Markdown text extraction utilities."""

import io
from pathlib import Path


def extract_pdf_text(file_bytes: bytes) -> str:
    """
    Extract readable text from a PDF file using PyMuPDF (fitz).

    Returns clean UTF-8 text with paragraphs separated by newlines.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            pages.append(text.strip())
    doc.close()
    return "\n\n".join(pages)


def extract_markdown_text(content: str) -> str:
    """
    Strip Markdown formatting, return plain text.

    Keeps headings (as plain text), removes links/images, keeps list items.
    """
    import re

    # Remove images
    content = re.sub(r"!\[.*?\]\(.*?\)", "", content)
    # Remove links, keep text
    content = re.sub(r"\[([^\]]*)\]\(.*?\)", r"\1", content)
    # Remove code blocks
    content = re.sub(r"```[\s\S]*?```", "", content)
    # Remove inline code
    content = re.sub(r"`([^`]*)`", r"\1", content)

    # Collapse multiple blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Dispatch to correct parser based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text(file_bytes)
    elif ext in (".md", ".txt"):
        return file_bytes.decode("utf-8")
    else:
        raise ValueError(f"Unsupported file type: {ext}")
