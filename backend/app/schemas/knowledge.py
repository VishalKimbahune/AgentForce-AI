"""Pydantic schemas for documents, knowledge search, and RAG."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    storage_key: str
    mime_type: str
    status: str
    version: int
    allowed_roles: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    uploaded_by: Optional[str] = None
    created_at: datetime
    chunk_count: int = 0

    class Config:
        from_attributes = True


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query or keyword phrase")
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of relevant chunks to return")


class KnowledgeSearchResultItem(BaseModel):
    document_id: Optional[str] = None
    source_name: str
    chunk_index: int
    page: int = 1
    text: str
    score: float
    citation: str


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: List[KnowledgeSearchResultItem]
    count: int


class KnowledgeAskRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Question to answer over enterprise knowledge")
    top_k: int = Field(5, ge=1, le=10)


class KnowledgeAskResponse(BaseModel):
    query: str
    answer: str
    citations: List[str] = Field(default_factory=list)
    chunks_used: int
    sources: List[Dict[str, Any]] = Field(default_factory=list)

