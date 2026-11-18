"""Voice Session Manager: orchestrates VAD, STT, workflow execution, approvals, and TTS streaming."""

import asyncio
import base64
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, Optional

from app.core.correlation import get_correlation_id
from app.core.database import AsyncSessionLocal
from app.models.models import Workflow
from app.services.guardrails import prompt_injection_guard, security_logger
from app.services.orchestrator.events import event_bus
from app.services.orchestrator.graph import execute_workflow_graph
from app.services.voice.stt import whisper_service
from app.services.voice.tts import tts_service
from app.services.voice.vad import VoiceActivityDetector

logger = logging.getLogger("voice.session")


def format_spoken_summary(intent: str, result: Dict[str, Any]) -> str:
    """Produces a concise, professional spoken summary from workflow result payload."""
    if not result:
        return "Workflow completed successfully."

    # HR Recruitment
    if "rankings" in result or "ranked_candidates" in result or "candidates" in result:
        cands = result.get("rankings") or result.get("ranked_candidates") or result.get("candidates") or []
        count = len(cands)
        if count > 0:
            top = cands[0]
            name = top.get("candidate_name") or top.get("name") or "the leading candidate"
            score = top.get("score") or top.get("match_score", 0)
            score_pct = int(score * 100) if isinstance(score, float) and score <= 1.0 else int(score)
            return f"Recruitment screening complete. Screened {count} candidates. Top candidate is {name} with a match score of {score_pct} percent."
        return f"Recruitment screening complete. Screened {count} candidates."

    # Finance Invoices
    if "clean_invoices" in result or "flagged_invoices" in result:
        clean = result.get("clean_invoices", [])
        flagged = result.get("flagged_invoices", [])
        clean_count = len(clean) if isinstance(clean, list) else 0
        flagged_count = len(flagged) if isinstance(flagged, list) else 0
        return f"Invoice processing complete. {clean_count} invoices cleared, {flagged_count} flagged for manual review."

    # Operations Report
    if "report_path" in result or "pdf_path" in result or "metrics" in result:
        return "Operations report successfully compiled and saved to local storage."

    # Generic summary
    summary = result.get("summary") or result.get("message")
    if summary and isinstance(summary, str):
        # Truncate to first two sentences
        sentences = [s.strip() for s in summary.split(".") if s.strip()]
        if sentences:
            return ". ".join(sentences[:2]) + "."

    return "Workflow finished processing successfully."


class VoiceSession:
    """Manages an active two-way voice session with live captions, interrupt, and approvals."""

    def __init__(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        mode: str = "push_to_talk",
        send_event: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        send_audio: Optional[Callable[[bytes, int], Coroutine[Any, Any, None]]] = None,
    ):
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.mode = mode  # "push_to_talk" or "continuous"
        self.state = "idle"  # idle, listening, processing, speaking, waiting_approval, interrupted

        self.send_event = send_event
        self.send_audio = send_audio

        self.audio_buffer = bytearray()
        self.vad = VoiceActivityDetector()
        self.cancel_event = asyncio.Event()
        self._current_task: Optional[asyncio.Task] = None
        self._active_workflow_id: Optional[str] = None

    async def emit_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Sends a JSON event to the connected client."""
        if self.send_event:
            payload = {
                "event": event_type,
                "session_id": self.session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(data or {}),
            }
            try:
                await self.send_event(payload)
            except Exception as e:
                logger.debug("Failed sending event to client: %s", e)

    async def start(self, mode: Optional[str] = None) -> None:
        """Initializes or resets the session to listening state."""
        if mode:
            self.mode = mode
        self.audio_buffer.clear()
        self.vad.reset()
        self.cancel_event.clear()
        self.state = "listening"
        await self.emit_event("session.started", {"mode": self.mode, "state": self.state})

    async def handle_audio_frame(self, chunk: bytes) -> None:
        """Processes an incoming raw audio frame (PCM or WebM) from the microphone."""
        if self.state not in ("listening", "idle"):
            return

        self.audio_buffer.extend(chunk)

        # Run Voice Activity Detection
        is_voice, transition_event, rms = self.vad.process_chunk(chunk)

        if transition_event == "speech_start":
            self.state = "listening"
            await self.emit_event("vad.speech_start", {"rms": round(rms, 4)})

        elif transition_event == "speech_end":
            await self.emit_event("vad.speech_end", {"rms": round(rms, 4)})
            if self.mode == "continuous":
                # Continuous mode: silence triggers automatic processing of utterance
                await self.process_speech_buffer()

    async def stop_speech(self) -> None:
        """Triggered explicitly by push-to-talk button release."""
        if self.state == "listening" or len(self.audio_buffer) > 0:
            await self.process_speech_buffer()

    async def interrupt(self) -> None:
        """Interrupts speech synthesis, workflow execution, or audio playback."""
        logger.info("Voice session %s interrupted.", self.session_id)
        self.cancel_event.set()
        self.state = "interrupted"

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

        await self.emit_event("session.interrupted", {"state": "interrupted"})

        # Reset cancellation and return to listening/idle
        self.cancel_event.clear()
        self.audio_buffer.clear()
        self.vad.reset()
        self.state = "listening" if self.mode == "continuous" else "idle"
        await self.emit_event("session.state_change", {"state": self.state})

    async def process_speech_buffer(self) -> None:
        """Transcribes current audio buffer, runs orchestrator, and speaks response."""
        if len(self.audio_buffer) < 1600:  # Less than 0.1s of 16kHz audio
            self.audio_buffer.clear()
            self.vad.reset()
            return

        audio_data = bytes(self.audio_buffer)
        self.audio_buffer.clear()
        self.vad.reset()

        self.state = "processing"
        await self.emit_event("session.state_change", {"state": self.state})
        await self.emit_event("transcript.processing", {"bytes_length": len(audio_data)})

        # Transcribe with Whisper
        stt_result = await whisper_service.transcribe(audio_data)
        transcript = stt_result.get("text", "").strip()

        if not transcript:
            await self.emit_event("transcript.final", {"text": "", "message": "No speech detected"})
            self.state = "listening" if self.mode == "continuous" else "idle"
            await self.emit_event("session.state_change", {"state": self.state})
            return

        # Emit live final transcript caption
        await self.emit_event(
            "transcript.final",
            {
                "text": transcript,
                "language": stt_result.get("language", "en"),
                "duration": stt_result.get("duration", 0.0),
            },
        )

        # Execute voice command through orchestrator
        self._current_task = asyncio.create_task(self._execute_voice_workflow(transcript))

    async def _execute_voice_workflow(self, command_text: str) -> None:
        """Executes workflow, enforces guardrails, handles approvals, and speaks result."""
        # 1. Guardrail Check: Prompt Injection Detection
        injection_check = prompt_injection_guard.scan(command_text)
        if injection_check.is_injection:
            corr_id = get_correlation_id()
            security_logger.record_incident(
                event_type="security.prompt_injection",
                threat_category=injection_check.category,
                risk_level=injection_check.risk_level,
                detail=injection_check.detail,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                correlation_id=corr_id,
                payload_sample={"input": command_text[:120]},
            )
            warning_text = "Security alert: Input blocked by prompt injection guardrails."
            await self.emit_event("error", {"code": "PROMPT_INJECTION", "message": warning_text})
            await self.speak_text(warning_text)
            self.state = "listening" if self.mode == "continuous" else "idle"
            await self.emit_event("session.state_change", {"state": self.state})
            return

        # 2. Persist workflow with input_source='voice'
        corr_id = get_correlation_id()
        wf_id = uuid.uuid4()
        self._active_workflow_id = str(wf_id)

        try:
            async with AsyncSessionLocal() as db:
                wf = Workflow(
                    id=wf_id,
                    tenant_id=uuid.UUID(self.tenant_id),
                    created_by=self.user_id,
                    input_text=command_text,
                    input_source="voice",
                    status="pending",
                    correlation_id=corr_id,
                    cost_usd=0.0,
                    tokens_used=0,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(wf)
                await db.commit()
        except Exception as e:
            logger.error("Failed to create voice workflow: %s", e)
            await self.emit_event("error", {"message": "Failed to create workflow record"})
            return

        await self.emit_event(
            "workflow.dispatched",
            {
                "workflow_id": str(wf_id),
                "input": command_text,
                "input_source": "voice",
            },
        )

        # 3. Launch graph execution
        graph_task = asyncio.create_task(
            execute_workflow_graph(
                workflow_id=str(wf_id),
                tenant_id=self.tenant_id,
                input_text=command_text,
                correlation_id=corr_id,
            )
        )

        # 4. Stream events from event bus until completion or waiting approval
        final_result: Optional[Dict[str, Any]] = None
        is_approval_needed = False
        approval_summary = ""

        try:
            async for sse_raw in event_bus.subscribe(str(wf_id)):
                if self.cancel_event.is_set():
                    break

                line = sse_raw.strip()
                if not line.startswith("data:"):
                    continue

                raw_json = line[5:].strip()
                if not raw_json:
                    continue

                evt = json.loads(raw_json)
                evt_type = evt.get("type")

                # Forward workflow progress event to voice client
                await self.emit_event(
                    "workflow.event",
                    {
                        "workflow_id": str(wf_id),
                        "type": evt_type,
                        "agent": evt.get("agent"),
                        "message": evt.get("message"),
                    },
                )

                if evt_type == "approval.requested":
                    is_approval_needed = True
                    req_data = evt.get("data") or {}
                    approval_summary = (
                        req_data.get("reason")
                        or f"Action '{req_data.get('action_type', 'task')}' requires manager approval."
                    )
                    await self.emit_event(
                        "approval.required",
                        {
                            "workflow_id": str(wf_id),
                            "action_type": req_data.get("action_type"),
                            "reason": approval_summary,
                        },
                    )
                    break

                if evt_type in ("workflow.completed", "workflow.failed"):
                    final_result = evt.get("data") or {}
                    break

        except Exception as e:
            logger.error("Error monitoring voice workflow: %s", e)

        # Await graph task completion if not waiting for approval
        if not is_approval_needed:
            try:
                await graph_task
            except Exception:
                pass

        # 5. Speak workflow response
        if is_approval_needed:
            self.state = "waiting_approval"
            await self.emit_event("session.state_change", {"state": self.state})
            spoken_text = f"This action requires approval: {approval_summary}. Please review in the Approval Center."
            await self.speak_text(spoken_text)
        else:
            self.state = "speaking"
            await self.emit_event("session.state_change", {"state": self.state})
            spoken_text = format_spoken_summary("", final_result or {})
            await self.speak_text(spoken_text)
            self.state = "listening" if self.mode == "continuous" else "idle"
            await self.emit_event("session.state_change", {"state": self.state})

    async def speak_text(self, text: str) -> None:
        """Synthesizes text to speech and streams audio chunks to the client."""
        if not text:
            return

        await self.emit_event("tts.started", {"text": text})
        chunk_index = 0

        async for audio_chunk in tts_service.stream_audio_chunks(
            text=text,
            cancel_event=self.cancel_event,
        ):
            if self.cancel_event.is_set():
                break

            # Send raw binary chunk or base64 chunk
            if self.send_audio:
                try:
                    await self.send_audio(audio_chunk, chunk_index)
                except Exception:
                    pass

            # Also emit structured event with base64 for websocket clients
            b64_audio = base64.b64encode(audio_chunk).decode("utf-8")
            await self.emit_event(
                "tts.chunk",
                {
                    "index": chunk_index,
                    "data": b64_audio,
                },
            )
            chunk_index += 1

        await self.emit_event("tts.completed", {"chunks_sent": chunk_index, "text": text})


class VoiceSessionManager:
    """Manages pool of active voice sessions across tenants."""

    def __init__(self):
        self._sessions: Dict[str, VoiceSession] = {}

    def get_or_create_session(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        mode: str = "push_to_talk",
        send_event: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        send_audio: Optional[Callable[[bytes, int], Coroutine[Any, Any, None]]] = None,
    ) -> VoiceSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = VoiceSession(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                mode=mode,
                send_event=send_event,
                send_audio=send_audio,
            )
        else:
            session = self._sessions[session_id]
            session.tenant_id = tenant_id
            session.user_id = user_id
            if send_event:
                session.send_event = send_event
            if send_audio:
                session.send_audio = send_audio
        return self._sessions[session_id]

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


voice_session_manager = VoiceSessionManager()
