"""Qdrant vector store service with strict tenant and role isolation."""

import logging
import uuid
from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient, models
from app.core.config import settings
from app.services.memory.embeddings import VECTOR_DIMENSION, get_embedding

logger = logging.getLogger("memory.qdrant")

COLLECTION_NAME = "knowledge"


class QdrantService:
    """Manages vector embeddings, indexing, and multi-tenant isolated hybrid search in Qdrant."""

    def __init__(self, qdrant_url: Optional[str] = None):
        url = qdrant_url or settings.QDRANT_URL
        self._client: Optional[QdrantClient] = None
        self._init_client(url)

    def _init_client(self, url: str) -> None:
        """Initializes client connecting to Qdrant server or falling back to in-memory."""
        try:
            # Try connecting to Qdrant instance
            c = QdrantClient(url=url, timeout=3.0)
            c.get_collections()
            self._client = c
            logger.info("Connected to Qdrant at %s", url)
        except Exception:
            # Fallback to local in-memory Qdrant instance
            logger.info("Remote Qdrant unavailable at %s; using local in-memory Qdrant vector store", url)
            self._client = QdrantClient(":memory:")

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Ensures the knowledge collection exists with correct vector dimension."""
        assert self._client is not None
        collections = [col.name for col in self._client.get_collections().collections]
        if COLLECTION_NAME not in collections:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_DIMENSION,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection: %s", COLLECTION_NAME)

    def upsert_chunks(
        self,
        tenant_id: str,
        document_id: str,
        chunks: List[Dict[str, Any]],
        document_name: str,
        version: int = 1,
        allowed_roles: Optional[List[str]] = None,
    ) -> List[str]:
        """Indexes document chunks with embeddings and multi-tenant metadata payload."""
        assert self._client is not None
        roles = allowed_roles if allowed_roles else ["owner", "manager", "approver", "member"]
        points = []
        point_ids = []

        for c in chunks:
            text = c["text"]
            chunk_idx = c["chunk_index"]
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            vector = get_embedding(text)

            payload = {
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
                "version": version,
                "allowed_roles": roles,
                "chunk_index": chunk_idx,
                "source_name": document_name,
                "page": c.get("page", 1),
                "text": text,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        if points:
            self._client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
            )

        return point_ids

    def search(
        self,
        query: str,
        tenant_id: str,
        role: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Executes vector search with MANDATORY tenant_id and role filter isolation.
        Throws ValueError if tenant_id or role is missing (conforming to doc 06 Section 4).
        """
        assert self._client is not None

        # Hard security check: Every search MUST include tenant_id filter and role filter
        if not tenant_id or not str(tenant_id).strip():
            raise ValueError("Tenant ID filter is strictly required for vector search")
        if not role or not str(role).strip():
            raise ValueError("Role filter is strictly required for vector search")

        query_vector = get_embedding(query)
        tenant_str = str(tenant_id)

        # Build Qdrant filter
        search_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=tenant_str),
                ),
            ],
            should=[
                models.FieldCondition(
                    key="allowed_roles",
                    match=models.MatchValue(value=role),
                ),
            ],
        )

        query_res = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k * 2,  # retrieve extra for hybrid reranking
        )
        results = query_res.points

        # Hybrid keyword reranking
        query_words = set(re_clean(query).split())
        scored_results = []

        for hit in results:
            payload = hit.payload or {}
            # Verify tenant_id in payload strictly matches
            if payload.get("tenant_id") != tenant_str:
                continue

            # Role verification: role must be in allowed_roles or caller is owner
            allowed_roles = payload.get("allowed_roles", [])
            if role != "owner" and role not in allowed_roles:
                continue

            text = payload.get("text", "")
            chunk_words = set(re_clean(text).split())
            keyword_overlap = len(query_words.intersection(chunk_words))

            # Combined score: 70% vector cosine similarity + 30% keyword overlap
            vector_score = hit.score
            hybrid_score = (vector_score * 0.7) + (min(keyword_overlap / max(len(query_words), 1), 1.0) * 0.3)

            source_name = payload.get("source_name", "Document")
            chunk_idx = payload.get("chunk_index", 0)
            page = payload.get("page", 1)

            citation = f"[{source_name}, Page {page}, Chunk {chunk_idx}]"

            scored_results.append({
                "document_id": payload.get("document_id"),
                "source_name": source_name,
                "chunk_index": chunk_idx,
                "page": page,
                "text": text,
                "score": round(float(hybrid_score), 4),
                "citation": citation,
            })

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def delete_document(self, tenant_id: str, document_id: str) -> None:
        """Deletes all vector points associated with a document under a specific tenant."""
        assert self._client is not None
        if not tenant_id or not document_id:
            return

        delete_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=str(tenant_id)),
                ),
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(document_id)),
                ),
            ]
        )

        self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(filter=delete_filter),
        )


def re_clean(text: str) -> str:
    """Helper to tokenize text for keyword overlap matching."""
    import re
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


# Global singleton
qdrant_service = QdrantService()
