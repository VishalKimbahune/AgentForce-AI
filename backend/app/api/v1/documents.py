"""Documents API router: file upload, validation, ingestion, and delete propagation."""

import json
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context
from app.models.models import Document, DocumentChunk
from app.schemas.knowledge import DocumentResponse
from app.services.memory.ingestion import ingest_document, save_uploaded_file
from app.services.memory.qdrant import qdrant_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    allowed_roles: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Uploads a document, saves it to local disk, chunks it, and indexes it in Qdrant."""
    filename = file.filename or "uploaded_document"
    content_bytes = await file.read()

    # Parse allowed roles & tags JSON if supplied
    parsed_roles = ["owner", "manager", "member"]
    if allowed_roles:
        try:
            parsed = json.loads(allowed_roles)
            if isinstance(parsed, list):
                parsed_roles = parsed
        except Exception:
            parsed_roles = [r.strip() for r in allowed_roles.split(",") if r.strip()]

    parsed_tags = []
    if tags:
        try:
            parsed = json.loads(tags)
            if isinstance(parsed, list):
                parsed_tags = parsed
        except Exception:
            parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Save file securely to persistent local directory
    try:
        storage_key, safe_name = await save_uploaded_file(
            content_bytes=content_bytes,
            filename=filename,
            tenant_id=str(ctx.tenant_id),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Create Document record
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=ctx.tenant_id,
        name=safe_name,
        storage_key=storage_key,
        mime_type=file.content_type or "application/octet-stream",
        status="processing",
        version=1,
        allowed_roles=parsed_roles,
        tags=parsed_tags,
        uploaded_by=str(ctx.user.id),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Execute text extraction, chunking, and Qdrant vector indexing
    try:
        chunk_count = await ingest_document(
            document_id=doc.id,
            tenant_id=ctx.tenant_id,
            content_bytes=content_bytes,
            filename=safe_name,
            allowed_roles=parsed_roles,
            db=db,
        )
    except Exception as e:
        doc.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document ingestion failed: {str(e)}",
        )

    return DocumentResponse(
        id=doc.id,
        tenant_id=doc.tenant_id,
        name=doc.name,
        storage_key=doc.storage_key,
        mime_type=doc.mime_type,
        status=doc.status,
        version=doc.version,
        allowed_roles=doc.allowed_roles,
        tags=doc.tags,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at,
        chunk_count=chunk_count,
    )


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Lists all active documents for the authenticated tenant."""
    stmt = (
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(
            Document.tenant_id == ctx.tenant_id,
            Document.deleted_at.is_(None),
        )
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    output = []
    for doc, chunk_cnt in rows:
        output.append(
            DocumentResponse(
                id=doc.id,
                tenant_id=doc.tenant_id,
                name=doc.name,
                storage_key=doc.storage_key,
                mime_type=doc.mime_type,
                status=doc.status,
                version=doc.version,
                allowed_roles=doc.allowed_roles,
                tags=doc.tags,
                uploaded_by=doc.uploaded_by,
                created_at=doc.created_at,
                chunk_count=chunk_cnt,
            )
        )
    return output


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves document detail strictly scoped to tenant."""
    stmt = (
        select(Document, func.count(DocumentChunk.id).label("chunk_count"))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(
            Document.id == document_id,
            Document.tenant_id == ctx.tenant_id,
            Document.deleted_at.is_(None),
        )
        .group_by(Document.id)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    doc, chunk_cnt = row
    return DocumentResponse(
        id=doc.id,
        tenant_id=doc.tenant_id,
        name=doc.name,
        storage_key=doc.storage_key,
        mime_type=doc.mime_type,
        status=doc.status,
        version=doc.version,
        allowed_roles=doc.allowed_roles,
        tags=doc.tags,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at,
        chunk_count=chunk_cnt,
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Propagates deletion across physical storage, database chunks, and Qdrant vectors."""
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == ctx.tenant_id,
    )
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # 1. Delete vector points from Qdrant
    qdrant_service.delete_document(
        tenant_id=str(ctx.tenant_id),
        document_id=str(document_id),
    )

    # 2. Delete physical file from local storage
    if doc.storage_key:
        file_path = Path(settings.LOCAL_STORAGE_PATH) / doc.storage_key
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception:
                pass

    # 3. Delete Document (cascades chunks)
    await db.delete(doc)
    await db.commit()

    return {"deleted": True, "id": str(document_id)}

