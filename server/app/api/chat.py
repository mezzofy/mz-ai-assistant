"""
Chat API — message send, conversation history, and WebSocket streaming.

REST Endpoints:
    POST /chat/send          — Send a text message, get AI response
    POST /chat/send-media    — Send image/video/audio/file + optional text
    POST /chat/send-url      — Send a URL for scraping + analysis
    GET  /chat/sessions      — List user's conversation sessions
    GET  /chat/history/{id}  — Get messages for a session
    DELETE /chat/session/{id} — End/clear a session

WebSocket:
    WS /chat/ws              — Real-time streaming: speech, camera, text

Auth:
    REST endpoints: JWT verified by ChatGatewayMiddleware (request.state.user)
    WebSocket: JWT in query param ?token=<JWT> (middleware bypasses WS)
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.database import get_db
from app.core.auth import decode_access_token
from app.input.input_router import process_input
from app.context.session_manager import (
    get_or_create_session,
    get_session_messages,
    list_user_sessions,
    append_message,
)
from app.context.processor import process_result
from app.output.output_formatter import format_ws_message
from app.output.stream_handler import ws_manager
from app.router import route_request

logger = logging.getLogger("mezzofy.api.chat")
router = APIRouter(tags=["chat"])


# ── Request / Response models ─────────────────────────────────────────────────

class SendTextRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    device_token: Optional[str] = None          # FCM registration token for push
    platform: str = "android"                   # "ios" or "android"


class SendURLRequest(BaseModel):
    url: str
    message: Optional[str] = None
    session_id: Optional[str] = None


class SendArtifactRequest(BaseModel):
    artifact_id: str
    message: str = ""
    session_id: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None


# ── Long-running task detection ───────────────────────────────────────────────

_LONG_RUNNING_KEYWORDS = [
    "research", "report", "generate pdf", "create pdf", "analyze all",
    "weekly", "monthly", "compare", "pitch deck", "scrape", "linkedin",
    # Research agent triggers
    "search the web", "web search", "look up online", "find online",
    "what is the latest", "find information about",
    # Developer agent triggers
    "write code", "create a script", "build a program",
    "write a python", "write a bash", "run claude code",
]

_RESEARCH_KEYWORDS = [
    "search the web", "web search", "look up online", "find online",
    "what is the latest", "find information about",
]

_DEVELOPER_KEYWORDS = [
    "write code", "create a script", "build a program",
    "write a python", "write a bash", "run claude code",
]

_SCHEDULER_KEYWORDS = {
    "schedule a", "create a schedule", "set up a schedule",
    "scheduled task", "scheduled job", "recurring task",
    "my schedules", "show my schedule", "list my schedule",
    "delete schedule", "cancel schedule", "remove schedule",
    "run schedule", "trigger schedule",
}

_CALENDAR_SIGNALS = {
    "meeting", "appointment", "call", "catch-up", "catch up",
    "lunch", "dinner", "interview", "event", "calendar",
    "conference", "standup", "stand-up", "1:1", "one-on-one",
    "sync", "huddle", "slot", "availability", "free slot",
    "book", "invite", "rsvp",
}

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic"}


def _is_long_running(message: str) -> bool:
    """Return True if the message contains a long-running task keyword."""
    lower = message.lower()
    return any(kw in lower for kw in _LONG_RUNNING_KEYWORDS)


def _is_scheduler_request(message: str) -> bool:
    """Return True if the message contains a scheduler management keyword."""
    lower = message.lower()
    if not any(kw in lower for kw in _SCHEDULER_KEYWORDS):
        return False
    # If the message contains calendar/meeting signals, it's a calendar request —
    # let it fall through to department routing where MS Calendar tools are available.
    if any(sig in lower for sig in _CALENDAR_SIGNALS):
        return False
    return True


def _detect_agent_type(message: str) -> str | None:
    """
    Detect whether a message should be routed to a specific power-user agent.

    Returns "research", "developer", or None (fall through to department routing).
    Prefix syntax ("research: ...", "developer: ...") takes priority over keyword scan.
    """
    lower = message.lower()
    if lower.startswith("research:") or any(kw in lower for kw in _RESEARCH_KEYWORDS):
        return "research"
    if lower.startswith("developer:") or any(kw in lower for kw in _DEVELOPER_KEYWORDS):
        return "developer"
    return None


# ── REST: POST /chat/send ─────────────────────────────────────────────────────

@router.post("/send")
async def send_message(
    body: SendTextRequest,
    request: Request,
):
    """
    Send a plain text message to the AI assistant.

    Auth: JWT verified by ChatGatewayMiddleware — user in request.state.user.
    """
    user = _get_user_from_state(request)
    config = get_config()
    logger.info(
        f"send_message: user_id={user.get('user_id')} dept={user.get('department')} "
        f"msg_len={len(body.message)}"
    )

    # Build base task
    task = _base_task(user, body.session_id, config)
    task.update({
        "message": body.message,
        "input_type": "text",
    })

    # Scheduler detection runs FIRST — always synchronous, never Celery.
    # Must precede _is_long_running() because common scheduler phrases like
    # "schedule a weekly report" contain long-running keywords ("weekly", "report").
    if _is_scheduler_request(body.message):
        task["agent"] = "scheduler"

    # Detect power-user agent type before long-running check
    # (checked first so "research:"/"developer:" prefixes always route correctly)
    _detected_agent = _detect_agent_type(body.message)

    # Long-running task detection — dispatch to Celery and return 202 immediately.
    # Skipped for scheduler requests (they always run synchronously).
    if not task.get("agent") and _is_long_running(body.message):
        import uuid as _uuid
        from app.tasks.tasks import process_chat_task

        new_task_id = str(_uuid.uuid4())
        task_ref = f"TASK-{new_task_id[:8].upper()}"
        queue_name_value = _detected_agent or "background"

        # Create (or retrieve) session BEFORE inserting agent_tasks.
        # This guarantees session_id is never null in agent_tasks, even if the
        # Celery worker fails before it can write session_id back.
        async with _db_session() as db:
            session = await get_or_create_session(
                db, user["user_id"], body.session_id, user.get("department", "")
            )
            resolved_session_id = session["id"]

            await db.execute(
                text(
                    "INSERT INTO agent_tasks "
                    "(id, task_ref, user_id, session_id, department, title, status, queue_name, notify_on_done) "
                    "VALUES (:id, :ref, :uid, :sid, :dept, :title, 'queued', :qname, true)"
                ),
                {
                    "id": new_task_id,
                    "ref": task_ref,
                    "uid": user["user_id"],
                    "sid": resolved_session_id,   # ← real session ID, never null
                    "dept": user.get("department", ""),
                    "title": body.message[:80],
                    "qname": queue_name_value,
                },
            )
            # Save user message immediately so chat history is never blank
            # if the Celery worker crashes before process_result() runs.
            try:
                await append_message(db, resolved_session_id, "user", body.message)
            except Exception as e:
                logger.warning(
                    f"Failed to pre-save user message (session={resolved_session_id}): {e}"
                )

        task_payload = {
            "user_id": user["user_id"],
            "session_id": resolved_session_id,    # ← pass to Celery so it reuses the session
            "message": body.message,
            "department": user.get("department", ""),
            # Power-user agents use their own name; department agents use dept name
            "agent": _detected_agent or user.get("department", ""),
            "device_token": body.device_token or "",
            "platform": body.platform,
            "source": "mobile",
            "_config": None,   # will be loaded inside _run_chat_task
            "agent_task_id": new_task_id,
        }
        celery_result = process_chat_task.delay(task_payload)
        logger.info(
            f"send_message: long-running task queued "
            f"user_id={user.get('user_id')} agent_task_id={new_task_id} "
            f"session_id={resolved_session_id} celery_id={celery_result.id}"
        )
        return JSONResponse(
            status_code=202,
            content={
                "status": "queued",
                "task_id": new_task_id,
                "session_id": resolved_session_id,  # ← mobile can link task to session immediately
                "message": "Your task has been queued. We'll notify you when it's ready.",
                "estimated_seconds": 120,
            },
        )

    # Process input (text passthrough)
    task = await process_input(task)

    async with _db_session() as db:
        # Get or create session
        session = await get_or_create_session(
            db, user["user_id"], body.session_id, user.get("department", "")
        )
        session_id = session["id"]
        task["session_id"] = session_id
        task["conversation_history"] = session["messages"]

        # Per-user concurrency limit — mobile source only
        if task.get("source") == "mobile":
            limit_result = await db.execute(
                text(
                    "SELECT COUNT(*) FROM agent_tasks "
                    "WHERE user_id = :uid AND status IN ('queued', 'running')"
                ),
                {"uid": user["user_id"]},
            )
            running_count = limit_result.scalar() or 0
            if running_count >= 3:
                return {
                    "success": False,
                    "content": "You already have 3 tasks running. Please wait for one to complete.",
                    "code": "TASK_LIMIT_REACHED",
                    "artifacts": [],
                    "session_id": None,
                }

        # Route to agent
        agent_result = await route_request(task)
        if not agent_result.get("success"):
            logger.error(
                f"send_message: agent returned failure | user_id={user.get('user_id')} "
                f"error={agent_result.get('content')!r}"
            )

        # Process result (save to DB, register artifacts)
        response = await process_result(
            db=db,
            user_id=user["user_id"],
            session_id=session_id,
            user_message=body.message,
            agent_result=agent_result,
            input_summary=task.get("input_summary", ""),
            department=task.get("department", ""),
        )

    return response


# ── REST: POST /chat/send-media ───────────────────────────────────────────────

@router.post("/send-media")
async def send_media(
    request: Request,
    message: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    input_type: str = Form(...),
    media_file: UploadFile = File(...),
):
    """
    Send a message with an image, video, audio, or document attachment.

    Content-Type: multipart/form-data
    Fields: message (optional), session_id (optional), input_type, media_file
    """
    user = _get_user_from_state(request)
    config = get_config()

    # Validate input_type
    valid_types = {"image", "video", "audio", "file"}
    if input_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"input_type must be one of: {', '.join(sorted(valid_types))}",
        )

    # Read file bytes
    file_bytes = await media_file.read()
    filename = media_file.filename or f"upload.{input_type}"

    # Build task
    task = _base_task(user, session_id, config)
    task.update({
        "message": message or "",
        "input_type": input_type,
    })

    # Process media input (OCR, transcription, text extraction)
    task = await process_input(task, file_bytes=file_bytes, filename=filename)

    async with _db_session() as db:
        session = await get_or_create_session(
            db, user["user_id"], session_id, user.get("department", "")
        )
        session_id = session["id"]
        task["session_id"] = session_id
        task["conversation_history"] = session["messages"]

        agent_result = await route_request(task)

        response = await process_result(
            db=db,
            user_id=user["user_id"],
            session_id=session_id,
            user_message=f"{message or ''} [{input_type}: {filename}]",
            agent_result=agent_result,
            input_summary=task.get("input_summary", ""),
            department=task.get("department", ""),
        )

    return response


# ── REST: POST /chat/send-url ─────────────────────────────────────────────────

@router.post("/send-url")
async def send_url(
    body: SendURLRequest,
    request: Request,
):
    """Fetch a URL, scrape its content, and pass to the AI assistant."""
    user = _get_user_from_state(request)
    config = get_config()

    task = _base_task(user, body.session_id, config)
    task.update({
        "message": body.message or body.url,
        "url": body.url,
        "input_type": "url",
    })

    task = await process_input(task)

    async with _db_session() as db:
        session = await get_or_create_session(
            db, user["user_id"], body.session_id, user.get("department", "")
        )
        session_id = session["id"]
        task["session_id"] = session_id
        task["conversation_history"] = session["messages"]

        agent_result = await route_request(task)

        response = await process_result(
            db=db,
            user_id=user["user_id"],
            session_id=session_id,
            user_message=body.message or body.url,
            agent_result=agent_result,
            input_summary=task.get("input_summary", ""),
            department=task.get("department", ""),
        )

    return response


# ── REST: POST /chat/send-artifact ───────────────────────────────────────────

@router.post("/send-artifact")
async def send_artifact(body: SendArtifactRequest, request: Request):
    """
    Send a message referencing an artifact already stored in the user's personal folder.

    Reads the file from disk (ownership-checked via artifact_id + user_id),
    routes it through the existing file processing pipeline, and returns an AI response.
    """
    user = _get_user_from_state(request)
    config = get_config()

    # 1. Ownership check — user can only access their own artifacts
    async with _db_session() as db:
        result = await db.execute(
            text(
                "SELECT id, filename, file_path, file_type, anthropic_file_id FROM artifacts "
                "WHERE id = :aid AND user_id = :uid"
            ),
            {"aid": body.artifact_id, "uid": user["user_id"]},
        )
        artifact = result.fetchone()

    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found or access denied")

    # 2. Read file bytes from disk
    file_path = Path(artifact.file_path)
    if not _artifact_path_exists(file_path):
        raise HTTPException(status_code=404, detail="File has been removed from storage")
    try:
        file_bytes = _read_artifact_bytes(file_path)
    except OSError as e:
        logger.error(f"send_artifact: failed to read {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read file from storage")

    # 3. Build task and route through existing pipeline
    task = _base_task(user, body.session_id, config)
    file_ext = Path(artifact.filename).suffix.lower()
    is_image = file_ext in _IMAGE_EXTENSIONS or (artifact.file_type or "").startswith("image")
    task.update({"message": body.message, "input_type": "image" if is_image else "file"})

    # Use cached Anthropic file_id for PDFs to skip re-upload on repeat requests
    cached_file_id = getattr(artifact, "anthropic_file_id", None)
    if cached_file_id and file_ext == ".pdf":
        task["anthropic_file_id"] = cached_file_id
        task["anthropic_file_name"] = artifact.filename
        task["extracted_text"] = body.message or "Please analyze this document."
        task["media_content"] = {"filename": artifact.filename, "extension": file_ext}
        task["input_summary"] = f"File: {artifact.filename} (cached Files API)"
    else:
        task = await process_input(task, file_bytes=file_bytes, filename=artifact.filename)
        # Persist a newly obtained file_id so subsequent calls can skip re-upload
        new_file_id = task.get("anthropic_file_id")
        if new_file_id and not cached_file_id:
            try:
                async with _db_session() as db:
                    await db.execute(
                        text(
                            "UPDATE artifacts SET anthropic_file_id = :fid WHERE id = :aid"
                        ),
                        {"fid": new_file_id, "aid": body.artifact_id},
                    )
                    await db.commit()
            except Exception as cache_err:
                logger.warning(
                    f"send_artifact: failed to cache anthropic_file_id for artifact "
                    f"{body.artifact_id}: {cache_err}"
                )

    async with _db_session() as db:
        session = await get_or_create_session(
            db, user["user_id"], body.session_id, user.get("department", "")
        )
        task["session_id"] = session["id"]
        task["conversation_history"] = session["messages"]
        agent_result = await route_request(task)
        return await process_result(
            db=db,
            user_id=user["user_id"],
            session_id=session["id"],
            user_message=f"{body.message} [file: {artifact.filename}]",
            agent_result=agent_result,
            input_summary=task.get("input_summary", ""),
            department=task.get("department", ""),
        )


# ── REST: GET /chat/sessions ──────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    request: Request,
    limit: int = 20,
    offset: int = 0,
):
    """List all conversation sessions for the current user."""
    user = _get_user_from_state(request)
    async with _db_session() as db:
        sessions = await list_user_sessions(
            db, user["user_id"], limit=limit, offset=offset
        )
    return {"sessions": sessions, "total": len(sessions)}


# ── REST: GET /chat/history/{session_id} ──────────────────────────────────────

@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    request: Request,
):
    """Get message history for a specific session."""
    user = _get_user_from_state(request)

    async with _db_session() as db:
        messages = await get_session_messages(db, session_id, user["user_id"])

    return {"session_id": session_id, "messages": messages}


# ── REST: PATCH /chat/session/{session_id} ────────────────────────────────────

@router.patch("/session/{session_id}")
async def update_session(
    session_id: str,
    body: SessionUpdateRequest,
    request: Request,
):
    """Update session metadata (favorite / archived)."""
    user = _get_user_from_state(request)

    # Build SET clause dynamically — only update non-None fields
    set_parts = []
    params: dict = {"id": session_id, "uid": user["user_id"]}
    if body.is_favorite is not None:
        set_parts.append("is_favorite = :is_favorite")
        params["is_favorite"] = body.is_favorite
    if body.is_archived is not None:
        set_parts.append("is_archived = :is_archived")
        params["is_archived"] = body.is_archived

    if not set_parts:
        return {"success": True}

    set_clause = ", ".join(set_parts) + ", updated_at = NOW()"

    async with _db_session() as db:
        result = await db.execute(
            text(
                f"UPDATE conversations SET {set_clause} "
                "WHERE id = :id AND user_id = :uid"
            ),
            params,
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True}


# ── REST: DELETE /chat/session/{session_id} ───────────────────────────────────

@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    request: Request,
):
    """Clear all messages from a session (soft reset — keeps session record)."""
    user = _get_user_from_state(request)

    async with _db_session() as db:
        result = await db.execute(
            text(
                "UPDATE conversations SET messages = '[]', updated_at = NOW() "
                "WHERE id = :id AND user_id = :uid"
            ),
            {"id": session_id, "uid": user["user_id"]},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")

    return {"session_id": session_id, "cleared": True}


# ── WebSocket: /chat/ws ───────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time WebSocket stream for speech, camera, and text messages.

    Auth: JWT passed as query parameter: /chat/ws?token=<JWT>

    Client → Server messages:
      {"type": "speech_start"}
      {"type": "speech_audio", "data": "<base64 chunk>"}
      {"type": "speech_end"}
      {"type": "camera_frame", "data": "<base64 JPEG>"}
      {"type": "text", "message": "...", "session_id": "..."}

    Server → Client messages (see output_formatter.format_ws_message):
      {"type": "transcript", "text": "...", "is_final": bool}
      {"type": "camera_analysis", "description": "..."}
      {"type": "status", "message": "..."}
      {"type": "complete", "response": {...}}
      {"type": "error", "detail": "..."}
    """
    # ── JWT auth from query param ─────────────────────────────────────────────
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    try:
        user = decode_access_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return

    user_id = user.get("user_id")
    if not user_id:
        await websocket.close(code=1008, reason="Invalid token payload")
        return

    config = get_config()

    # Register connection
    await ws_manager.connect(websocket, user_id)

    # Initialize speech session for this connection
    from app.input.speech_handler import SpeechSession
    speech_session = SpeechSession(config)

    # Subscribe to Redis notifications channel for this user
    import redis.asyncio as aioredis
    _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _redis_client = aioredis.from_url(_redis_url)
    _pubsub = _redis_client.pubsub()
    await _pubsub.subscribe(f"user:{user_id}:notifications")
    _redis_task = asyncio.create_task(
        _listen_redis_notifications(_pubsub, websocket, user_id)
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send(
                    user_id, format_ws_message("error", detail="Invalid JSON")
                )
                continue

            msg_type = msg.get("type", "")

            # ── Speech ───────────────────────────────────────────────────────
            if msg_type == "speech_start":
                speech_session.start()
                continue

            if msg_type == "speech_audio":
                speech_session.add_chunk(msg.get("data", ""))
                continue

            if msg_type == "speech_end":
                transcript = await speech_session.end_and_transcribe()
                await ws_manager.send(
                    user_id,
                    format_ws_message("transcript", text=transcript, is_final=True),
                )
                if transcript:
                    # Process transcript as a text message
                    await _handle_ws_text(
                        websocket=websocket,
                        user=user,
                        message=transcript,
                        session_id=msg.get("session_id"),
                        config=config,
                    )
                continue

            # ── Camera ───────────────────────────────────────────────────────
            if msg_type == "camera_frame":
                from app.input.camera_handler import handle_camera_frame
                result = await handle_camera_frame(msg.get("data", ""), config)
                await ws_manager.send(
                    user_id,
                    format_ws_message(
                        "camera_analysis",
                        description=result.get("description", ""),
                    ),
                )
                continue

            # ── Text ─────────────────────────────────────────────────────────
            if msg_type == "text":
                await _handle_ws_text(
                    websocket=websocket,
                    user=user,
                    message=msg.get("message", ""),
                    session_id=msg.get("session_id"),
                    config=config,
                )
                continue

            await ws_manager.send(
                user_id,
                format_ws_message("error", detail=f"Unknown message type: {msg_type!r}"),
            )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: user={user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user={user_id}: {e}", exc_info=True)
        try:
            await ws_manager.send(user_id, format_ws_message("error", detail=str(e)))
        except Exception:
            pass
    finally:
        _redis_task.cancel()
        try:
            await _pubsub.unsubscribe(f"user:{user_id}:notifications")
            await _redis_client.aclose()
        except Exception:
            pass
        await ws_manager.disconnect(user_id)


async def _listen_redis_notifications(
    pubsub,
    websocket: WebSocket,
    user_id: str,
) -> None:
    """
    Async task that forwards Redis pub/sub messages to the WebSocket client.
    Used to deliver task_complete notifications when the Celery task finishes.
    """
    async for message in pubsub.listen():
        if message.get("type") == "message":
            try:
                await websocket.send_text(message["data"].decode())
            except Exception:
                break


async def _handle_ws_text(
    websocket: WebSocket,
    user: dict,
    message: str,
    session_id: Optional[str],
    config: dict,
) -> None:
    """Process a text message received over WebSocket and stream the response."""
    user_id = user["user_id"]

    # Status update
    await ws_manager.send(user_id, format_ws_message("status", message="Processing…"))

    task = _base_task(user, session_id, config)
    task.update({"message": message, "input_type": "text", "source": "mobile"})
    task = await process_input(task)

    async with _db_session() as db:
        session = await get_or_create_session(
            db, user_id, session_id, user.get("department", "")
        )
        ws_session_id = session["id"]
        task["session_id"] = ws_session_id
        task["conversation_history"] = session["messages"]

        await ws_manager.send(
            user_id, format_ws_message("status", message="Thinking…")
        )

        agent_result = await route_request(task)

        response = await process_result(
            db=db,
            user_id=user_id,
            session_id=ws_session_id,
            user_message=message,
            agent_result=agent_result,
            input_summary=task.get("input_summary", ""),
            department=user.get("department", ""),
        )

    await ws_manager.send(user_id, format_ws_message("complete", response=response))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _artifact_path_exists(file_path: Path) -> bool:
    """Check whether an artifact path exists on disk. Extracted for testability."""
    return file_path.exists()


def _read_artifact_bytes(file_path: Path) -> bytes:
    """Read raw bytes from a file path. Extracted for testability."""
    return file_path.read_bytes()


def _get_user_from_state(request: Request) -> dict:
    """Extract user payload from request.state (set by ChatGatewayMiddleware)."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def _base_task(user: dict, session_id: Optional[str], config: dict) -> dict:
    """Build the base task dict from the authenticated user context."""
    return {
        "user_id": user.get("user_id", ""),
        "email": user.get("email", ""),
        "department": user.get("department", ""),
        "role": user.get("role", ""),
        "permissions": user.get("permissions", []),
        "session_id": session_id,
        "source": "mobile",
        "attachments": [],
        "conversation_history": [],
        "_config": config,
    }


class _db_session:
    """Async context manager that provides a DB session from AsyncSessionLocal."""

    async def __aenter__(self) -> AsyncSession:
        from app.core.database import AsyncSessionLocal
        self._session = AsyncSessionLocal()
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            await self._session.rollback()
        else:
            try:
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                raise
        await self._session.close()
