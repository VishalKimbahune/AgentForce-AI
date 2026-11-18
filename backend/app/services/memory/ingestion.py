"""Document storage, text extraction, chunking, and ingestion pipeline."""

import io
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docx
import pypdf
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Document, DocumentChunk
from app.services.memory.qdrant import qdrant_service

# Allowed file extensions and MIME types
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json"}
MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # 25 MB


def sanitize_filename(filename: str) -> str:
    """Removes path separators and invalid characters to prevent traversal attacks."""
    clean = os.path.basename(filename)
    return re.sub(r"[^\w\.\-_]", "_", clean)


def extract_text_from_file(content_bytes: bytes, filename: str) -> str:
    """Extracts raw text from PDF, DOCX, Markdown, or text files."""
    ext = os.path.splitext(filename.lower())[1]

    if ext == ".pdf":
        reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        pages = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    elif ext in (".docx", ".doc"):
        doc = docx.Document(io.BytesIO(content_bytes))
        return "\n\n".join([p.text for p in doc.paragraphs if p.text])

    else:
        # Plain text, Markdown, CSV, JSON
        return content_bytes.decode("utf-8", errors="ignore")


def chunk_text(
    text: str,
    target_tokens: int = 600,
    overlap_tokens: int = 80,
) -> List[Dict[str, Any]]:
    """Chunks text into 500-800 token windows with 80 token overlap (Doc 06 Section 4).
    Approximates tokens at 4 characters per token.
    """
    chunk_char_size = target_tokens * 4  # ~2400 chars
    overlap_char_size = overlap_tokens * 4  # ~320 chars

    # Split text into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []

    chunks: List[Dict[str, Any]] = []
    current_chunk = ""
    current_page = 1

    for para in paragraphs:
        if len(current_chunk) + len(para) < chunk_char_size:
            current_chunk = f"{current_chunk}\n\n{para}".strip()
        else:
            if current_chunk:
                chunks.append({
                    "chunk_index": len(chunks),
                    "text": current_chunk,
                    "page": current_page,
                })
                # Overlap: keep last overlap_char_size characters
                overlap_text = current_chunk[-overlap_char_size:] if len(current_chunk) > overlap_char_size else ""
                current_chunk = f"{overlap_text}\n\n{para}".strip()
            else:
                # Very large paragraph, split directly
                start = 0
                while start < len(para):
                    end = start + chunk_char_size
                    piece = para[start:end]
                    chunks.append({
                        "chunk_index": len(chunks),
                        "text": piece,
                        "page": current_page,
                    })
                    start += (chunk_char_size - overlap_char_size)
                current_chunk = ""

    if current_chunk:
        chunks.append({
            "chunk_index": len(chunks),
            "text": current_chunk,
            "page": current_page,
        })

    return chunks


async def save_uploaded_file(
    content_bytes: bytes,
    filename: str,
    tenant_id: str,
) -> Tuple[str, str]:
    """Validates file, saves to persistent storage directory, and returns (storage_key, safe_name)."""
    if len(content_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB")

    safe_name = sanitize_filename(filename)
    ext = os.path.splitext(safe_name.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext}'. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Relative storage key: <tenant_id>/<uuid>_<safe_name>
    file_id = str(uuid.uuid4())
    storage_key = f"{tenant_id}/{file_id}_{safe_name}"

    base_dir = Path(settings.LOCAL_STORAGE_PATH).resolve()
    target_path = (base_dir / storage_key).resolve()

    # Path traversal protection
    if not str(target_path).startswith(str(base_dir)):
        raise ValueError("Invalid storage path destination (path traversal detected)")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content_bytes)

    return storage_key, safe_name


async def ingest_document(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
    content_bytes: bytes,
    filename: str,
    allowed_roles: List[str],
    db: AsyncSession,
) -> int:
    """Extracts text, chunks content, embeds into Qdrant, and writes chunks to DB."""
    raw_text = extract_text_from_file(content_bytes, filename)
    chunks = chunk_text(raw_text)

    # 1. Store vectors in Qdrant with tenant and role filters
    point_ids = qdrant_service.upsert_chunks(
        tenant_id=str(tenant_id),
        document_id=str(document_id),
        chunks=chunks,
        document_name=filename,
        version=1,
        allowed_roles=allowed_roles,
    )

    # 2. Persist DocumentChunk records in PostgreSQL/SQLite
    for idx, c in enumerate(chunks):
        p_id = point_ids[idx] if idx < len(point_ids) else str(uuid.uuid4())
        chunk_record = DocumentChunk(
            id=uuid.uuid4(),
            document_id=document_id,
            tenant_id=tenant_id,
            chunk_index=c["chunk_index"],
            text=c["text"],
            qdrant_point_id=p_id,
        )
        db.add(chunk_record)

    # 3. Update document status to ready
    await db.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(status="ready")
    )
    await db.commit()

    return len(chunks)

