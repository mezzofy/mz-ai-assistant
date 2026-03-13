"""
LinkedIn Status API — read-only visibility into the server's LinkedIn session state.

Endpoints:
    GET /linkedin/status — Returns cookie configuration status and session usage counter

The LinkedIn session cookie is server-admin managed (configured via LINKEDIN_COOKIE env var
and loaded into LinkedInOps at startup). This endpoint is read-only — no connect/disconnect
flow exists. Any authenticated user may call it.
"""

import logging
import os

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user

logger = logging.getLogger("mezzofy.api.linkedin")

router = APIRouter(tags=["linkedin"])


@router.get("/status")
async def get_linkedin_status(
    current_user: dict = Depends(get_current_user),
):
    """
    Return the server's LinkedIn session configuration and usage counter.

    - configured: True if LINKEDIN_COOKIE env var is set and non-empty
    - session_preview: last 4 chars of the cookie, masked as ****xxxx (or null)
    - rate_limit: max profile loads per session (from config, default 50)
    - session_uses: number of profile loads used this session (resets on restart)
    """
    from app.tools.web import linkedin_ops as li_mod

    cookie = os.getenv("LINKEDIN_COOKIE", "").strip()
    configured = bool(cookie)

    session_preview: str | None = None
    if configured and len(cookie) >= 4:
        session_preview = "****" + cookie[-4:]
    elif configured:
        session_preview = "****"

    # Read rate limit from config
    try:
        from app.core.config import load_config
        config = load_config()
        rate_limit: int = config.get("tools", {}).get("linkedin", {}).get("rate_limit_per_session", 50)
    except Exception:
        rate_limit = 50

    # Read live session counter from the module-level variable
    session_uses: int = li_mod._session_counter

    logger.debug(
        f"LinkedIn status requested by user {current_user.get('user_id')} — "
        f"configured={configured}, uses={session_uses}/{rate_limit}"
    )

    return {
        "configured": configured,
        "session_preview": session_preview,
        "rate_limit": rate_limit,
        "session_uses": session_uses,
    }
