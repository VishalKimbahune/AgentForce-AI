"""Voice API Router: WebSocket audio streaming, VAD, Whisper STT, and Edge-TTS synthesis."""

import asyncio
import base64
import json
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.dependencies import TenantContext, get_tenant_context
from app.core.security import verify_supabase_token
from app.models.models import Membership, Organization, User, Workflow
from app.services.voice.session import (
    VoiceSession,
    format_spoken_summary,
    voice_session_manager,
)
from app.services.voice.stt import whisper_service
from app.services.voice.tts import tts_service
from app.services.guardrails import prompt_injection_guard, security_logger
from app.core.correlation import get_correlation_id
from app.services.orchestrator.events import event_bus
from app.services.orchestrator.graph import execute_workflow_graph

logger = logging.getLogger("api.voice")

router = APIRouter(prefix="/voice", tags=["voice"])


class SynthesizeRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize to speech")
    voice: Optional[str] = Field(None, description="TTS voice override")


class VoiceCommandRequest(BaseModel):
    audio_base64: Optional[str] = Field(None, description="Base64 encoded audio payload (WAV/WebM/MP3)")
    text: Optional[str] = Field(None, description="Direct text input if already transcribed")
    mode: Optional[str] = Field("push_to_talk", description="Operating mode")


async def authenticate_ws(
    websocket: WebSocket,
    token: Optional[str],
    tenant_id_param: Optional[str],
) -> Optional[TenantContext]:
    """Authenticates WebSocket connection using Bearer token and verifies tenant membership."""
    if not token:
        # Check Authorization header if available
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing auth token")
        return None

    try:
        payload = verify_supabase_token(token)
    except Exception as e:
        logger.warning("WS auth failed: %s", e)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return None

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(User)
            .options(selectinload(User.memberships).selectinload(Membership.organization))
            .where(User.id == payload.sub)
        )
        user = res.scalar_one_or_none()
        if not user or not user.memberships:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User membership not found")
            return None

        # Resolve tenant
        target_tenant_id = None
        if tenant_id_param:
            try:
                target_tenant_id = uuid.UUID(tenant_id_param)
            except ValueError:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid tenant UUID")
                return None

        selected_membership = None
        for m in user.memberships:
            if target_tenant_id:
                if m.tenant_id == target_tenant_id:
                    selected_membership = m
                    break
            else:
                selected_membership = m
                break

        if not selected_membership:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized tenant access")
            return None

        return TenantContext(
            tenant_id=selected_membership.tenant_id,
            organization=selected_membership.organization,
            user=user,
            membership=selected_membership,
        )


@router.websocket("/stream")
async def voice_websocket_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
):
    """Real-time bi-directional voice WebSocket endpoint.

    Accepts:
    - JSON control messages (start, stop_speech, interrupt, audio_chunk)
    - Raw binary audio frames from browser microphone
    Emits:
    - VAD speech markers, live captions (transcript.final), workflow events, and streamed audio chunks.
    """
    await websocket.accept()

    ctx = await authenticate_ws(websocket, token, tenant_id)
    if not ctx:
        return

    session_id = str(uuid.uuid4())

    async def send_event(payload: Dict[str, Any]) -> None:
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

    async def send_audio(chunk: bytes, index: int) -> None:
        try:
            await websocket.send_bytes(chunk)
        except Exception:
            pass

    session = voice_session_manager.get_or_create_session(
        session_id=session_id,
        tenant_id=str(ctx.tenant_id),
        user_id=str(ctx.user.id),
        mode="push_to_talk",
        send_event=send_event,
        send_audio=send_audio,
    )

    await session.start()

    try:
        while True:
            message = await websocket.receive()
            if "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                if msg_type == "start":
                    mode = data.get("mode", "push_to_talk")
                    await session.start(mode=mode)

                elif msg_type == "stop_speech":
                    await session.stop_speech()

                elif msg_type == "interrupt":
                    await session.interrupt()

                elif msg_type == "audio_chunk":
                    b64_data = data.get("data", "")
                    if b64_data:
                        raw_chunk = base64.b64decode(b64_data)
                        await session.handle_audio_frame(raw_chunk)

            elif "bytes" in message and message["bytes"]:
                await session.handle_audio_frame(message["bytes"])

    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected for session %s", session_id)
    except Exception as e:
        logger.error("Error in voice WebSocket session %s: %s", session_id, e)
    finally:
        voice_session_manager.remove_session(session_id)


@router.post("/transcribe")
async def transcribe_audio_file(
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(get_tenant_context),
):
    """Fallback: transcribes uploaded audio file using Whisper."""
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty",
        )

    result = await whisper_service.transcribe(content)
    return JSONResponse(content=result)


@router.post("/synthesize")
async def synthesize_speech(
    req: SynthesizeRequest,
    ctx: TenantContext = Depends(get_tenant_context),
):
    """Synthesizes text into streaming MP3 audio via Edge-TTS."""
    if not req.text or not req.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty",
        )

    async def audio_generator():
        async for chunk in tts_service.stream_audio_chunks(text=req.text, voice=req.voice):
            yield chunk

    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'inline; filename="synthesized_speech.mp3"'},
    )


@router.post("/command", status_code=status.HTTP_200_OK)
async def execute_voice_command(
    req: VoiceCommandRequest,
    ctx: TenantContext = Depends(get_tenant_context),
):
    """Executes a spoken workflow command end-to-end:
    Speech -> STT -> Prompt Injection Guard -> LangGraph Orchestrator -> Approval / Result -> Spoken Response.
    """
    transcript = ""

    # 1. Transcribe audio if provided
    if req.audio_base64:
        raw_audio = base64.b64decode(req.audio_base64)
        stt_res = await whisper_service.transcribe(raw_audio)
        transcript = stt_res.get("text", "").strip()
    elif req.text:
        transcript = req.text.strip()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either audio_base64 or text",
        )

    if not transcript:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "transcript": "",
                "status": "no_speech",
                "message": "No audible speech was detected",
            },
        )

    # 2. Guardrails: Prompt Injection Check
    injection_check = prompt_injection_guard.scan(transcript)
    if injection_check.is_injection:
        corr_id = get_correlation_id()
        security_logger.record_incident(
            event_type="security.prompt_injection",
            threat_category=injection_check.category,
            risk_level=injection_check.risk_level,
            detail=injection_check.detail,
            tenant_id=str(ctx.tenant_id),
            user_id=str(ctx.user.id),
            correlation_id=corr_id,
            payload_sample={"input": transcript[:120]},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt injection detected in voice command: {injection_check.detail}",
        )

    # 3. Create workflow with input_source='voice'
    corr_id = get_correlation_id()
    wf_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        wf = Workflow(
            id=wf_id,
            tenant_id=ctx.tenant_id,
            created_by=str(ctx.user.id),
            input_text=transcript,
            input_source="voice",
            status="pending",
            correlation_id=corr_id,
            cost_usd=0.0,
            tokens_used=0,
        )
        db.add(wf)
        await db.commit()

    # 4. Execute orchestrator graph
    graph_task = asyncio.create_task(
        execute_workflow_graph(
            workflow_id=str(wf_id),
            tenant_id=str(ctx.tenant_id),
            input_text=transcript,
            correlation_id=corr_id,
        )
    )

    # 5. Monitor events from event_bus
    final_result: Optional[Dict[str, Any]] = None
    is_waiting_approval = False
    approval_data: Dict[str, Any] = {}

    try:
        async for sse_raw in event_bus.subscribe(str(wf_id)):
            line = sse_raw.strip()
            if not line.startswith("data:"):
                continue
            raw_json = line[5:].strip()
            if not raw_json:
                continue

            evt = json.loads(raw_json)
            evt_type = evt.get("type")

            if evt_type == "approval.requested":
                is_waiting_approval = True
                approval_data = evt.get("data") or {}
                break

            if evt_type in ("workflow.completed", "workflow.failed"):
                final_result = evt.get("data") or {}
                break
    except Exception as e:
        logger.error("Error awaiting voice workflow: %s", e)

    if not is_waiting_approval:
        try:
            await graph_task
        except Exception:
            pass

    # 6. Format spoken reply and synthesize TTS audio
    if is_waiting_approval:
        status_str = "waiting_approval"
        reason = approval_data.get("reason", "Mandatory human review required by corporate policy")
        spoken_text = f"This action requires approval: {reason}. Please review in the Approval Center."
    else:
        status_str = "completed"
        spoken_text = format_spoken_summary("", final_result or {})

    # Synthesize reply audio
    speech_bytes = await tts_service.synthesize(spoken_text)
    audio_b64 = base64.b64encode(speech_bytes).decode("utf-8")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "transcript": transcript,
            "workflow_id": str(wf_id),
            "status": status_str,
            "spoken_response": spoken_text,
            "approval_required": is_waiting_approval,
            "approval_data": approval_data if is_waiting_approval else None,
            "result": final_result,
            "audio_base64": audio_b64,
        },
    )

