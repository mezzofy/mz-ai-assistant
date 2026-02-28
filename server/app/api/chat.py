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

import json
import logging
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
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_config
from app.core.database import get_db
from app.core.auth import decode_access_token
from app.input.input_router import process_input
from app.context.session_manager import (
    get_or_create_session,
    get_session_messages,
    list_user_sessions,
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


class SendURLRequest(BaseModel):
    url: str
    message: Optional[str] = None
    session_id: Optional[str] = None


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

    # Build base task
    task = _base_task(user, body.session_id, config)
    task.update({
        "message": body.message,
        "input_type": "text",
    })

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

        # Route to agent
        agent_result = await route_request(task)

        # Process result (save to DB, register artifacts)
        response = await process_result(
            db=db,
            user_id=user["user_id"],
            session_id=session_id,
            user_message=body.message,
            agent_result=agent_result,
            input_summary=task.get("input_summary", ""),
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
        )

    return response


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


# ── REST: DELETE /chat/session/{session_id} ───────────────────────────────────

@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    request: Request,
):
    """Clear all messages from a session (soft reset — keeps session record)."""
    user = _get_user_from_state(request)

    from sqlalchemy import text
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
        await ws_manager.disconnect(user_id)


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
        )

    await ws_manager.send(user_id, format_ws_message("complete", response=response))


# ── Helpers ───────────────────────────────────────────────────────────────────

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
