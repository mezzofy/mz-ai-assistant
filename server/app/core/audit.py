"""
Audit Logger — async INSERT into audit_log table.

Every meaningful action (tool calls, logins, file ops, admin changes) is
recorded here for 90-day compliance retention.

Schema (from migrate.py):
    audit_log(id, user_id, session_id, action, resource, details, ip_address,
              user_agent, success, error_message, duration_ms, created_at)

Usage:
    await log_action(
        db=db,
        user_id="user-uuid",
        action="email_sent",
        resource="outlook",
        details={"to": "...", "subject": "..."},
        ip="1.2.3.4",
        success=True,
    )
"""

import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def log_action(
    db: AsyncSession,
    user_id: str,
    action: str,
    resource: str,
    details: Optional[dict] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    session_id: Optional[str] = None,
) -> None:
    """
    Insert an audit log entry asynchronously.

    Never raises — audit failures must not break the main request.
    Silently swallows all exceptions to avoid impacting users.

    Args:
        db:            SQLAlchemy async session (from get_db dependency)
        user_id:       UUID string of the acting user
        action:        Short action name, e.g. "email_sent", "file_created", "login"
        resource:      Tool/resource name, e.g. "outlook", "pdf", "auth"
        details:       Additional JSON context (redact PII before passing)
        ip:            Client IP address
        user_agent:    HTTP User-Agent header
        success:       Whether the action succeeded
        error_message: Error description if success=False
        duration_ms:   How long the action took (optional)
        session_id:    Chat session UUID if applicable
    """
    try:
        import json
        details_json = json.dumps(details) if details else None

        await db.execute(
            text("""
                INSERT INTO audit_log
                    (user_id, session_id, action, resource, details,
                     ip_address, user_agent, success, error_message, duration_ms)
                VALUES
                    (:user_id, :session_id, :action, :resource, :details::jsonb,
                     :ip, :user_agent, :success, :error_message, :duration_ms)
            """),
            {
                "user_id": user_id,
                "session_id": session_id,
                "action": action,
                "resource": resource,
                "details": details_json,
                "ip": ip,
                "user_agent": user_agent,
                "success": success,
                "error_message": error_message,
                "duration_ms": duration_ms,
            },
        )
        await db.commit()
    except Exception:
        # Audit failures are non-fatal — never propagate
        pass


class AuditTimer:
    """
    Context manager that measures elapsed time for audit logging.

    Usage:
        with AuditTimer() as timer:
            result = await do_something()
        await log_action(..., duration_ms=timer.elapsed_ms)
    """

    def __init__(self):
        self._start: float = 0.0
        self.elapsed_ms: int = 0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.monotonic() - self._start) * 1000)
