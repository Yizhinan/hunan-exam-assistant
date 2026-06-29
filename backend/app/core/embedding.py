"""
Embedding service using BAAI/bge-large-zh-v1.5 for Chinese text.

Lazy-loads the model on first use to keep startup fast.
Provides a singleton embedding function for the RAG pipeline.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_embedding_model: "SentenceTransformer | None" = None


def get_embedding_model() -> "SentenceTransformer":
    """Lazy-load the bge-large-zh model (singleton)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer("BAAI/bge-large-zh-v1.5")
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.

    Returns a list of float vectors, each dimension 1024.
    """
    model = get_embedding_model()
    # bge models benefit from instruction prefix for queries
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """
    Generate embedding for a single query string.
    Adds bge-recommended instruction prefix.
    """
    model = get_embedding_model()
    # Instruction prefix recommended by BAAI for retrieval
    embedding = model.encode(
        [text],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embedding[0].tolist()
