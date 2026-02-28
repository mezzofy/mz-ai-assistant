"""
Session Manager — conversation history stored in PostgreSQL.

A session is a single conversation thread between one user and the AI.
Uses the `conversations` table (created in Phase 0 migrate.py):
  id, user_id, department, messages (JSON), created_at, updated_at

messages is a JSON array of:
  {"role": "user"|"assistant", "content": str, "timestamp": ISO-8601}

Keeps last MAX_HISTORY_MESSAGES per session to bound context window growth.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mezzofy.context.session")

MAX_HISTORY_MESSAGES = 20


async def get_or_create_session(
    db: AsyncSession,
    user_id: str,
    session_id: Optional[str],
    department: str = "",
) -> dict:
    """
    Get an existing session or create a new one.

    Args:
        db:         Active DB session.
        user_id:    Authenticated user ID.
        session_id: Existing session ID (None → always create new).
        department: User's department (stored on new sessions).

    Returns:
        {"id": str, "messages": list}
    """
    if session_id:
        existing = await _fetch_session(db, session_id, user_id)
        if existing is not None:
            return existing

    # Create new session
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            """
            INSERT INTO conversations
              (id, user_id, department, messages, created_at, updated_at)
            VALUES
              (:id, :user_id, :dept, :msgs, :now, :now)
            """
        ),
        {
            "id": new_id,
            "user_id": user_id,
            "dept": department,
            "msgs": json.dumps([]),
            "now": now,
        },
    )
    logger.debug(f"Created session {new_id} for user {user_id}")
    return {"id": new_id, "messages": []}


async def append_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
) -> None:
    """
    Append one message to the session's message array.

    Args:
        db:         Active DB session.
        session_id: Session to update.
        role:       "user" or "assistant".
        content:    Message text.
    """
    result = await db.execute(
        text("SELECT messages FROM conversations WHERE id = :id"),
        {"id": session_id},
    )
    row = result.fetchone()
    if row is None:
        logger.warning(f"append_message: session {session_id} not found")
        return

    messages = _parse_messages(row.messages)
    messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Trim to bound size
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]

    await db.execute(
        text(
            "UPDATE conversations SET messages = :msgs, updated_at = :now WHERE id = :id"
        ),
        {
            "msgs": json.dumps(messages),
            "now": datetime.now(timezone.utc),
            "id": session_id,
        },
    )


async def get_session_messages(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> list:
    """Return message list for a session. Empty list if not found / wrong owner."""
    session = await _fetch_session(db, session_id, user_id)
    return session["messages"] if session else []


async def list_user_sessions(
    db: AsyncSession,
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> list:
    """
    List all conversation sessions for a user (most recent first).

    Returns list of session summaries:
      {session_id, message_count, last_message, created_at, updated_at}
    """
    result = await db.execute(
        text(
            """
            SELECT id, messages, created_at, updated_at
            FROM conversations
            WHERE user_id = :uid
            ORDER BY updated_at DESC
            LIMIT :lim OFFSET :off
            """
        ),
        {"uid": user_id, "lim": limit, "off": offset},
    )
    rows = result.fetchall()
    sessions = []
    for row in rows:
        msgs = _parse_messages(row.messages)
        sessions.append({
            "session_id": row.id,
            "message_count": len(msgs),
            "last_message": msgs[-1] if msgs else None,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        })
    return sessions


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_session(
    db: AsyncSession, session_id: str, user_id: str
) -> Optional[dict]:
    result = await db.execute(
        text(
            "SELECT id, messages FROM conversations WHERE id = :id AND user_id = :uid"
        ),
        {"id": session_id, "uid": user_id},
    )
    row = result.fetchone()
    if row is None:
        return None
    return {"id": row.id, "messages": _parse_messages(row.messages)}


def _parse_messages(raw) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return []


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)
