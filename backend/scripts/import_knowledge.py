"""
批量导入知识库素材脚本

用法:
  cd backend
  python scripts/import_knowledge.py

自动扫描 ../knowledge_materials/{exam,policy,news,model}/ 下的所有
PDF/Markdown/TXT 文件，解析后存入 ChromaDB 和 PostgreSQL/SQLite。
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.database import engine, Base, SessionLocal
from app.core.pdf_parser import extract_text
from app.core.rag import get_rag, DocType

# Import models so tables are created
import app.models.user  # noqa
import app.models.document  # noqa
import app.models.essay  # noqa

MATERIALS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge_materials"

# Map directory names to doc_type
DIR_TO_TYPE: dict[str, DocType] = {
    "exam": "exam",
    "policy": "policy",
    "news": "news",
    "model": "model",
}

SUPPORTED_EXTS = {".pdf", ".md", ".txt"}


def main():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Ensure ChromaDB collections exist
    rag = get_rag()

    db = SessionLocal()
    total_imported = 0

    for dir_name, doc_type in DIR_TO_TYPE.items():
        dir_path = MATERIALS_DIR / dir_name
        if not dir_path.exists():
            print(f"[SKIP] 目录不存在: {dir_path}")
            continue

        files = [f for f in dir_path.iterdir() if f.suffix.lower() in SUPPORTED_EXTS]
        if not files:
            print(f"[EMPTY] {dir_path}")
            continue

        print(f"\n{'='*50}")
        print(f"[{doc_type}] 发现 {len(files)} 个文件")
        print(f"{'='*50}")

        for file_path in files:
            ext = file_path.suffix.lower()
            title = file_path.stem  # filename without extension
            print(f"\n  导入: {file_path.name} ...", end=" ")

            try:
                # Read and parse
                with open(file_path, "rb") as f:
                    file_bytes = f.read()

                text = extract_text(file_bytes, file_path.name)

                if not text.strip():
                    print("SKIP (内容为空)")
                    continue

                # Check for duplicates in ChromaDB
                # (We use a simple URL-based dedup via the document model)
                from app.models.document import Document
                exists = db.query(Document).filter(
                    Document.source_url == f"file://{file_path}"
                ).first()
                if exists:
                    print("SKIP (已导入过)")
                    continue

                # Create DB record
                doc_record = Document(
                    title=title,
                    doc_type=doc_type,
                    source_url=f"file://{file_path}",
                    source_name="手动导入",
                    file_type=ext[1:],  # remove dot
                    status="ingesting",
                )
                db.add(doc_record)
                db.commit()
                db.refresh(doc_record)

                # Ingest into ChromaDB
                metadata = {
                    "title": title,
                    "doc_type": doc_type,
                    "source_name": "手动导入",
                    "document_id": str(doc_record.id),
                    "filename": file_path.name,
                }

                chunk_count = rag.ingest(text, doc_type, metadata)

                doc_record.chunk_count = chunk_count
                doc_record.status = "ingested"
                db.commit()

                print(f"OK ({chunk_count} chunks)")
                total_imported += chunk_count

            except Exception as e:
                print(f"ERROR: {e}")
                db.rollback()

    db.close()
    print(f"\n{'='*50}")
    print(f"导入完成! 总计 {total_imported} 个分块")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
