"""知识库管理 API — document upload, search, list, delete, bulk ingest."""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete

from app.core.database import get_db
from app.core.security import decode_token
from app.core.rag import get_rag, DocType
from app.core.pdf_parser import extract_text
from app.models.document import Document

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(decode_token)],
)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(..., description="exam | policy | news | model"),
    title: str = Form(...),
    source_url: str = Form(""),
    source_name: str = Form(""),
    db = Depends(get_db),
):
    """Upload a document (PDF / Markdown / TXT) to the knowledge base."""
    if doc_type not in ("exam", "policy", "news", "model"):
        raise HTTPException(status_code=400, detail=f"无效的文档类型: {doc_type}")

    allowed_exts = {".pdf", ".md", ".txt"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    if f".{ext}" not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: .{ext}")

    file_bytes = await file.read()
    try:
        text = extract_text(file_bytes, file.filename or "upload")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    doc_record = Document(
        title=title,
        doc_type=doc_type,
        source_url=source_url,
        source_name=source_name,
        file_type=ext,
        status="ingesting",
    )
    db.add(doc_record)
    await db.commit()
    await db.refresh(doc_record)

    try:
        rag = get_rag()
        metadata = {
            "title": title,
            "doc_type": doc_type,
            "source_url": source_url,
            "source_name": source_name,
            "document_id": str(doc_record.id),
        }
        chunk_count = rag.ingest(text, doc_type, metadata)

        doc_record.chunk_count = chunk_count
        doc_record.status = "ingested"
        await db.commit()
        await db.refresh(doc_record)

        return {
            "id": str(doc_record.id),
            "title": title,
            "doc_type": doc_type,
            "chunk_count": chunk_count,
            "status": "ingested",
        }
    except Exception as e:
        doc_record.status = "error"
        doc_record.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"向量化存储失败: {str(e)}")


@router.get("/search")
async def search_knowledge(
    q: str = Query(min_length=1),
    doc_type: str = Query("exam", description="exam | policy | news | model"),
    top_k: int = Query(5, ge=1, le=20),
):
    """Semantic search across the knowledge base."""
    if doc_type not in ("exam", "policy", "news", "model"):
        raise HTTPException(status_code=400, detail=f"无效的文档类型: {doc_type}")

    rag = get_rag()
    results = rag.retrieve(q, doc_type, top_k=top_k)

    return {
        "query": q,
        "doc_type": doc_type,
        "total": len(results),
        "results": results,
    }


@router.get("/documents")
async def list_documents(
    doc_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db = Depends(get_db),
):
    """Paginated list of uploaded documents."""
    query = select(Document)
    count_query = select(func.count(Document.id))

    if doc_type:
        query = query.where(Document.doc_type == doc_type)
        count_query = count_query.where(Document.doc_type == doc_type)

    query = query.order_by(Document.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    docs_result = await db.execute(query)
    docs = docs_result.scalars().all()

    return {
        "documents": [
            {
                "id": str(d.id),
                "title": d.title,
                "doc_type": d.doc_type,
                "file_type": d.file_type,
                "source_name": d.source_name,
                "chunk_count": d.chunk_count,
                "status": d.status,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    db = Depends(get_db),
):
    """Delete a document from both ChromaDB and PostgreSQL."""
    doc_result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = doc_result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Remove from ChromaDB first — log but don't block DB cleanup on failure
    try:
        rag = get_rag()
        chunks_deleted = rag.remove(doc_id, doc.doc_type)
        logger.info("ChromaDB cleanup for doc %s: %s chunks deleted", doc_id, chunks_deleted)
    except Exception as e:
        logger.warning("ChromaDB cleanup failed for doc %s: %s", doc_id, e)

    # Use Core DELETE to bypass identity-map caching issues
    await db.execute(delete(Document).where(Document.id == doc_id))
    await db.commit()

    return {"ok": True, "deleted": doc_id}


# ============================================================
# Bulk ingest schemas (for crawler pipeline)
# ============================================================


class IngestItem(BaseModel):
    doc_type: str = Field(..., description="exam | policy | news | model")
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source_url: str = ""
    source_name: str = ""
    topic: str | None = None
    exam_year: int | None = None
    category: str | None = None
    tags: list[str] | None = None


class IngestRequest(BaseModel):
    items: list[IngestItem] = Field(..., min_length=1, max_length=200)


class IngestItemResult(BaseModel):
    index: int
    title: str
    doc_type: str
    status: str  # "ingested" | "skipped" | "error"
    chunk_count: int = 0
    error: str | None = None


class IngestResponse(BaseModel):
    total: int
    ingested: int
    skipped: int
    errors: int
    results: list[IngestItemResult]


@router.post("/ingest", status_code=status.HTTP_200_OK)
async def ingest_items(
    body: IngestRequest,
    db = Depends(get_db),
):
    """
    Bulk ingest knowledge items from JSON payload (used by crawler pipeline).

    Each item is chunked, embedded, stored in ChromaDB, and recorded in PostgreSQL.
    Returns per-item status for pipeline observability.
    """
    rag = get_rag()
    results: list[IngestItemResult] = []
    ingested_count = 0
    skipped_count = 0
    error_count = 0

    for i, item in enumerate(body.items):
        # Validate doc_type
        if item.doc_type not in ("exam", "policy", "news", "model"):
            results.append(IngestItemResult(
                index=i, title=item.title, doc_type=item.doc_type,
                status="error", error=f"无效的文档类型: {item.doc_type}",
            ))
            error_count += 1
            continue

        # Dedup: skip if source_url already exists
        if item.source_url:
            existing = await db.execute(
                select(Document).where(Document.source_url == item.source_url)
            )
            if existing.scalar_one_or_none() is not None:
                results.append(IngestItemResult(
                    index=i, title=item.title, doc_type=item.doc_type,
                    status="skipped",
                ))
                skipped_count += 1
                continue

        # Create DB record
        doc_record = Document(
            title=item.title,
            doc_type=item.doc_type,
            source_url=item.source_url,
            source_name=item.source_name,
            file_type="txt",
            status="ingesting",
        )
        db.add(doc_record)
        await db.commit()
        await db.refresh(doc_record)

        # Ingest into ChromaDB
        try:
            metadata = {
                "title": item.title,
                "doc_type": item.doc_type,
                "source_url": item.source_url,
                "source_name": item.source_name,
                "document_id": str(doc_record.id),
            }
            if item.topic:
                metadata["topic"] = item.topic
            if item.exam_year:
                metadata["exam_year"] = str(item.exam_year)
            if item.category:
                metadata["category"] = item.category

            chunk_count = rag.ingest(item.content, item.doc_type, metadata)

            doc_record.chunk_count = chunk_count
            doc_record.status = "ingested"
            await db.commit()

            results.append(IngestItemResult(
                index=i, title=item.title, doc_type=item.doc_type,
                status="ingested", chunk_count=chunk_count,
            ))
            ingested_count += 1

        except Exception as e:
            doc_record.status = "error"
            doc_record.error_message = str(e)
            await db.commit()
            results.append(IngestItemResult(
                index=i, title=item.title, doc_type=item.doc_type,
                status="error", error=str(e),
            ))
            error_count += 1

    return IngestResponse(
        total=len(body.items),
        ingested=ingested_count,
        skipped=skipped_count,
        errors=error_count,
        results=results,
    )
