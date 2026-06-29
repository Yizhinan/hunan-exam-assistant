"""
Document chunking strategies for different content types.

Strategies:
  - exam_question: Keep question + answer + analysis together as one chunk
  - policy: Split by section/paragraph, keep heading context
  - news: One article per chunk, preserve title + source + date metadata
"""

from dataclasses import dataclass, field
import re


@dataclass
class Chunk:
    """A single text chunk with metadata."""

    content: str
    metadata: dict = field(default_factory=dict)

    # Approximate token count (Chinese chars ≈ tokens)
    @property
    def char_count(self) -> int:
        return len(self.content)


def chunk_by_paragraphs(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
    metadata: dict | None = None,
) -> list[Chunk]:
    """
    General-purpose paragraph-based chunking with overlap.
    Used for policy files and news articles.
    """
    meta = metadata or {}
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: list[Chunk] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > chunk_size and current:
            chunks.append(Chunk(content=current.strip(), metadata=meta))
            # Overlap: keep last N chars of previous chunk
            overlap_text = current[-overlap:] if len(current) > overlap else ""
            current = overlap_text + para + "\n\n"
        else:
            current += para + "\n\n"

    if current.strip():
        chunks.append(Chunk(content=current.strip(), metadata=meta))

    return chunks


def chunk_exam_questions(
    text: str,
    metadata: dict | None = None,
) -> list[Chunk]:
    """
    Smart chunking for exam papers.
    Tries to split on question boundaries (题号 markers like 一、二、 or 1. 2.)
    so each chunk contains one complete question + answer.
    """
    meta = metadata or {}

    # Try to split on Chinese numbering or digit numbering
    markers = re.split(r"\n(?=(?:[一二三四五六七八九十]+[、．.])|(?:\d+[、．.]))", text)

    if len(markers) <= 1:
        # Fallback: split on double newlines
        markers = re.split(r"\n\s*\n", text)

    chunks: list[Chunk] = []
    for i, section in enumerate(markers):
        section = section.strip()
        if not section:
            continue
        chunk_meta = {**meta, "section_index": i}
        chunks.append(Chunk(content=section, metadata=chunk_meta))

    return chunks


def chunk_document(
    text: str,
    doc_type: str,
    metadata: dict | None = None,
) -> list[Chunk]:
    """
    Dispatch to the appropriate chunking strategy based on document type.

    doc_type: "exam" | "policy" | "news" | "general"
    """
    meta = metadata or {}

    if doc_type == "exam":
        return chunk_exam_questions(text, meta)
    elif doc_type in ("policy", "general"):
        return chunk_by_paragraphs(text, metadata=meta)
    elif doc_type == "news":
        # News: one chunk per article (typically short enough)
        return [Chunk(content=text.strip(), metadata=meta)]
    else:
        return chunk_by_paragraphs(text, metadata=meta)
