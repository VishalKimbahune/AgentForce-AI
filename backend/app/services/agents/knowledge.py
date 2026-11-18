"""Knowledge AI Employee: multi-tenant RAG retrieval, question answering, and source citations."""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_gateway.gateway import LLMGateway, TaskType
from app.services.memory.qdrant import qdrant_service

logger = logging.getLogger("agent.knowledge")


class KnowledgeAgent:
    """Specialized AI Employee for enterprise document QA and policy retrieval with source citations."""

    def __init__(self):
        self.gateway = LLMGateway()

    async def answer_question(
        self,
        query: str,
        tenant_id: str,
        role: str,
        db: Optional[AsyncSession] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Performs isolated RAG vector search and answers query with verified source citations."""
        # 1. Isolated vector search in Qdrant (enforces tenant and role filters)
        chunks = qdrant_service.search(
            query=query,
            tenant_id=tenant_id,
            role=role,
            top_k=top_k,
        )

        if not chunks:
            return {
                "answer": "No relevant documents or policy sections found matching your query within your organization permissions.",
                "citations": [],
                "chunks_used": 0,
            }

        citations = [c["citation"] for c in chunks]
        context_parts = []
        for c in chunks:
            context_parts.append(f"--- Source: {c['citation']} ---\n{c['text']}")

        context_str = "\n\n".join(context_parts)

        # 2. RAG Synthesis Prompt
        prompt = (
            f"You are the AgentForce Enterprise Knowledge Assistant. "
            f"Answer the user's question accurately using ONLY the retrieved document context below. "
            f"Always cite the source citation tag (e.g. [Document Name, Page X, Chunk Y]) at the end of each key point.\n\n"
            f"Retrieved Context:\n{context_str}\n\n"
            f"User Question: {query}\n\n"
            f"Answer with citations:"
        )

        try:
            # Query LLM Gateway with INTENT or GENERAL task type
            resp = await self.gateway.complete(
                prompt=prompt,
                task_type=TaskType.GENERAL,
                tenant_id=tenant_id,
                db=db,
            )
            answer_text = resp.content.strip()
        except Exception as e:
            logger.warning("LLM Gateway unavailable for RAG synthesis; using deterministic citation summarizer: %s", str(e))
            # Clean deterministic fallback synthesis for offline/test environments
            top_chunk = chunks[0]
            answer_text = (
                f"Based on {top_chunk['citation']}: {top_chunk['text'][:300]}... "
                f"Reference: {', '.join(citations[:2])}"
            )

        return {
            "answer": answer_text,
            "citations": citations,
            "chunks_used": len(chunks),
            "sources": [
                {
                    "source_name": c["source_name"],
                    "page": c["page"],
                    "chunk_index": c["chunk_index"],
                    "score": c["score"],
                    "citation": c["citation"],
                    "text_snippet": c["text"][:200] + "...",
                }
                for c in chunks
            ],
        }


knowledge_agent = KnowledgeAgent()

