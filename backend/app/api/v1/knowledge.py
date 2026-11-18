"""Knowledge API router: hybrid vector search and question answering with citations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context
from app.schemas.knowledge import (
    KnowledgeAskRequest,
    KnowledgeAskResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResultItem,
)
from app.services.agents.knowledge import knowledge_agent
from app.services.memory.qdrant import qdrant_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    req: KnowledgeSearchRequest,
    ctx: TenantContext = Depends(get_tenant_context),
):
    """Executes hybrid vector and keyword search strictly isolated by tenant and caller role."""
    try:
        results = qdrant_service.search(
            query=req.query,
            tenant_id=str(ctx.tenant_id),
            role=ctx.role,
            top_k=req.top_k,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    items = [
        KnowledgeSearchResultItem(
            document_id=r.get("document_id"),
            source_name=r["source_name"],
            chunk_index=r["chunk_index"],
            page=r.get("page", 1),
            text=r["text"],
            score=r["score"],
            citation=r["citation"],
        )
        for r in results
    ]

    return KnowledgeSearchResponse(
        query=req.query,
        results=items,
        count=len(items),
    )


@router.post("/ask", response_model=KnowledgeAskResponse)
async def ask_knowledge(
    req: KnowledgeAskRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Answers a question using RAG over the tenant's uploaded knowledge base with source citations."""
    try:
        res = await knowledge_agent.answer_question(
            query=req.query,
            tenant_id=str(ctx.tenant_id),
            role=ctx.role,
            db=db,
            top_k=req.top_k,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return KnowledgeAskResponse(
        query=req.query,
        answer=res["answer"],
        citations=res["citations"],
        chunks_used=res["chunks_used"],
        sources=res.get("sources", []),
    )

