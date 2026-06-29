"""
RAG (Retrieval-Augmented Generation) service.

Handles:
  - Document ingestion → chunk → embed → store in ChromaDB
  - Hybrid retrieval: semantic search + optional keyword filtering + metadata filters
  - Three retrieval contexts for essay grading:
    1. exam_standard: question model answers & scoring rubrics
    2. policy: Hunan government policies for citation checking
    3. model_essay: high-scoring sample essays as reference
"""

from typing import Literal

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings
from app.core.chunker import chunk_document, Chunk
from app.core.embedding import embed_texts, embed_query

settings = get_settings()

# Knowledge base collection names
COLLECTION_EXAM = "exam_questions"      # 真题 + 标答 + 评分标准
COLLECTION_POLICY = "hunan_policy"      # 湖南政策文件
COLLECTION_NEWS = "hunan_news"          # 湖南时政热点
COLLECTION_MODEL = "model_essays"       # 高分范文

DocType = Literal["exam", "policy", "news", "model"]

COLLECTION_MAP: dict[DocType, str] = {
    "exam": COLLECTION_EXAM,
    "policy": COLLECTION_POLICY,
    "news": COLLECTION_NEWS,
    "model": COLLECTION_MODEL,
}


class RAGService:
    """Singleton RAG service wrapping ChromaDB."""

    def __init__(self):
        if settings.CHROMA_LOCAL:
            # Local persistent mode — no Docker needed
            self._client = chromadb.PersistentClient(
                path="./chroma_data",
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        else:
            self._client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        self._ensure_collections()

    def _ensure_collections(self):
        """Create collections if they don't exist."""
        existing = {c.name for c in self._client.list_collections()}
        for name in COLLECTION_MAP.values():
            if name not in existing:
                self._client.create_collection(name=name)

    # -------- Ingestion --------

    def ingest(
        self,
        text: str,
        doc_type: DocType,
        metadata: dict | None = None,
    ) -> int:
        """
        Ingest a document: chunk → embed → store.

        Returns number of chunks created.
        """
        collection_name = COLLECTION_MAP[doc_type]
        collection = self._client.get_collection(name=collection_name)

        chunks = chunk_document(text, doc_type, metadata)
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        embeddings = embed_texts(texts)

        ids = [f"{doc_type}_{abs(hash(c.content))}" for c in chunks]
        metadatas = [c.metadata for c in chunks]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        return len(chunks)

    # -------- Retrieval --------

    def retrieve(
        self,
        query: str,
        doc_type: DocType,
        top_k: int = 5,
        metadata_filter: dict | None = None,
    ) -> list[dict]:
        """
        Semantic retrieval from a specific collection.

        Args:
            query: Search query
            doc_type: Which collection to search
            top_k: Number of results
            metadata_filter: Optional ChromaDB where-clause for metadata

        Returns list of {content, metadata, score}
        """
        collection_name = COLLECTION_MAP[doc_type]
        collection = self._client.get_collection(name=collection_name)

        query_embedding = embed_query(query)

        where = metadata_filter or None
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        return self._format_results(results)

    def retrieve_for_grading(
        self,
        essay_topic: str,
        top_k_per_type: int = 3,
    ) -> dict[str, list[dict]]:
        """
        Specialized retrieval for essay grading — fetches all 3 contexts.

        Returns {exam_context, policy_context, model_context}
        """
        return {
            "exam_context": self.retrieve(
                f"申论题目: {essay_topic}", "exam", top_k=top_k_per_type
            ),
            "policy_context": self.retrieve(
                f"湖南政策: {essay_topic}", "policy", top_k=top_k_per_type
            ),
            "model_context": self.retrieve(
                f"高分申论范文: {essay_topic}", "model", top_k=top_k_per_type
            ),
        }

    # -------- Helpers --------

    @staticmethod
    def _format_results(raw: dict) -> list[dict]:
        """Convert ChromaDB query result to a list of dicts."""
        results = []
        if not raw.get("ids") or not raw["ids"][0]:
            return results

        for i, doc_id in enumerate(raw["ids"][0]):
            results.append({
                "id": doc_id,
                "content": raw["documents"][0][i],
                "metadata": raw["metadatas"][0][i] if raw.get("metadatas") else {},
                "score": 1 - raw["distances"][0][i],  # convert cosine distance → similarity
            })

        # Sort by relevance score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results


# Singleton
_rag_instance: RAGService | None = None


def get_rag() -> RAGService:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGService()
    return _rag_instance
