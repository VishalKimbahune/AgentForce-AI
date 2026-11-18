"""In-memory event bus and SSE event distributor for real-time workflow timelines."""

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional
from app.schemas.workflow import WorkflowEventSchema


class WorkflowEventBus:
    """Distributes live events to subscribed HTTP clients via Server-Sent Events (SSE)."""

    def __init__(self):
        # workflow_id -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        # workflow_id -> list of past events (replay buffer)
        self._history: Dict[str, List[WorkflowEventSchema]] = {}

    def emit(
        self,
        workflow_id: str,
        event_type: str,
        agent: str,
        message: str,
        correlation_id: str,
        task_id: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> WorkflowEventSchema:
        """Publishes an event to all active SSE clients and stores it in the replay buffer."""
        now_str = datetime.now(timezone.utc).isoformat()
        evt = WorkflowEventSchema(
            type=event_type,
            workflow_id=str(workflow_id),
            task_id=str(task_id) if task_id else None,
            agent=agent,
            message=message,
            timestamp=now_str,
            correlation_id=correlation_id,
            data=data,
        )

        # Store in replay history
        wf_str = str(workflow_id)
        if wf_str not in self._history:
            self._history[wf_str] = []
        self._history[wf_str].append(evt)

        # Broadcast to active subscriber queues
        if wf_str in self._subscribers:
            for q in self._subscribers[wf_str]:
                try:
                    q.put_nowait(evt)
                except asyncio.QueueFull:
                    pass

        return evt

    async def subscribe(self, workflow_id: str) -> AsyncGenerator[str, None]:
        """Subscribes to live events for a workflow, replaying past events first."""
        wf_str = str(workflow_id)
        q: asyncio.Queue = asyncio.Queue(maxsize=100)

        if wf_str not in self._subscribers:
            self._subscribers[wf_str] = []
        self._subscribers[wf_str].append(q)

        # Replay past events
        if wf_str in self._history:
            for past_event in self._history[wf_str]:
                yield f"data: {json.dumps(past_event.model_dump())}\n\n"
            if any(pe.type in ("workflow.completed", "workflow.failed", "workflow.cancelled") for pe in self._history[wf_str]):
                return

        try:
            while True:
                evt: WorkflowEventSchema = await q.get()
                yield f"data: {json.dumps(evt.model_dump())}\n\n"
                # If workflow concluded, terminate the stream
                if evt.type in ("workflow.completed", "workflow.failed", "workflow.cancelled"):
                    break
        finally:
            if wf_str in self._subscribers and q in self._subscribers[wf_str]:
                self._subscribers[wf_str].remove(q)
                if not self._subscribers[wf_str]:
                    del self._subscribers[wf_str]


event_bus = WorkflowEventBus()
