"""
MS Token Service — Fernet-encrypted storage and auto-refresh of per-user MS OAuth tokens.

Public API:
    save_tokens(user_id, access_token, refresh_token, expires_at, ms_user_id, ms_email, scopes)
    get_valid_token(user_id) -> str   — auto-refreshes if < 5 min remaining
    delete_tokens(user_id)
    get_token_status(user_id) -> dict

Exception:
    MSNotConnectedException — raised when no token row exists for user_id
"""

import logging
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.core.database import AsyncSessionLocal

logger = logging.getLogger("mezzofy.services.ms_token")


# ── Custom exceptions ─────────────────────────────────────────────────────────

class MSNotConnectedException(Exception):
    """Raised when a user has no connected MS account."""
    pass


# ── Fernet encryption helpers ─────────────────────────────────────────────────

def _get_fernet():
    """Return a Fernet instance using MS_TOKEN_FERNET_KEY from environment."""
    from cryptography.fernet import Fernet
    key = os.getenv("MS_TOKEN_FERNET_KEY", "")
    if not key:
        raise RuntimeError(
            "MS_TOKEN_FERNET_KEY is not configured. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string using Fernet symmetric encryption."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted token string."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# ── Token persistence ─────────────────────────────────────────────────────────

async def save_tokens(
    user_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    ms_user_id: str = "",
    ms_email: str = "",
    scopes: str = "",
) -> None:
    """
    Upsert encrypted tokens for a user into ms_oauth_tokens.
    Existing rows are updated (ON CONFLICT DO UPDATE).
    """
    enc_access = encrypt_token(access_token)
    enc_refresh = encrypt_token(refresh_token)

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                INSERT INTO ms_oauth_tokens
                    (user_id, ms_user_id, ms_email, access_token, refresh_token,
                     token_expires_at, scopes, connected_at, updated_at)
                VALUES
                    (:uid, :ms_uid, :ms_email, :access_token, :refresh_token,
                     :expires_at, :scopes, NOW(), NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    ms_user_id       = EXCLUDED.ms_user_id,
                    ms_email         = EXCLUDED.ms_email,
                    access_token     = EXCLUDED.access_token,
                    refresh_token    = EXCLUDED.refresh_token,
                    token_expires_at = EXCLUDED.token_expires_at,
                    scopes           = EXCLUDED.scopes,
                    updated_at       = NOW()
            """),
            {
                "uid": user_id,
                "ms_uid": ms_user_id,
                "ms_email": ms_email,
                "access_token": enc_access,
                "refresh_token": enc_refresh,
                "expires_at": expires_at,
                "scopes": scopes,
            },
        )
        await session.commit()
    logger.info(f"Saved MS OAuth tokens for user {user_id} (ms_email={ms_email})")


async def delete_tokens(user_id: str) -> None:
    """Remove MS OAuth tokens for a user (disconnect)."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM ms_oauth_tokens WHERE user_id = :uid"),
            {"uid": user_id},
        )
        await session.commit()
    logger.info(f"Deleted MS OAuth tokens for user {user_id}")


async def get_token_status(user_id: str) -> dict:
    """Return connection status info without decrypting tokens."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT ms_email, scopes, token_expires_at, connected_at
                FROM ms_oauth_tokens
                WHERE user_id = :uid
            """),
            {"uid": user_id},
        )
        row = result.mappings().first()

    if not row:
        return {"connected": False, "ms_email": None, "scopes": [], "expires_at": None}

    scopes_list = (row["scopes"] or "").split() if row["scopes"] else []
    return {
        "connected": True,
        "ms_email": row["ms_email"],
        "scopes": scopes_list,
        "expires_at": row["token_expires_at"].isoformat() if row["token_expires_at"] else None,
    }


# ── Token retrieval with auto-refresh ─────────────────────────────────────────

async def get_valid_token(user_id: str) -> str:
    """
    Return a valid (non-expired) MS access token for the given user.

    Flow:
      1. Load encrypted row from DB — raise MSNotConnectedException if none
      2. Decrypt access_token
      3. If not expiring within 5 minutes — return as-is
      4. Otherwise refresh via MSAL using the refresh_token
      5. Save new tokens to DB and return new access_token

    Raises:
        MSNotConnectedException: No connected MS account for user
        RuntimeError: Token refresh failed
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT access_token, refresh_token, token_expires_at
                FROM ms_oauth_tokens
                WHERE user_id = :uid
            """),
            {"uid": user_id},
        )
        row = result.mappings().first()

    if not row:
        raise MSNotConnectedException(f"No MS account connected for user {user_id}")

    now = datetime.now(timezone.utc)
    expires_at = row["token_expires_at"]

    # Ensure expires_at is timezone-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    # If token still valid for > 5 minutes, return it
    if expires_at > now + timedelta(minutes=5):
        return decrypt_token(row["access_token"])

    # Token is expiring — refresh via MSAL
    logger.info(f"Refreshing MS token for user {user_id} (expires at {expires_at})")
    decrypted_refresh = decrypt_token(row["refresh_token"])
    new_access, new_refresh, new_expires_at = await _refresh_token(decrypted_refresh)

    # Update DB with new tokens
    enc_access = encrypt_token(new_access)
    enc_refresh = encrypt_token(new_refresh)
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                UPDATE ms_oauth_tokens SET
                    access_token     = :access_token,
                    refresh_token    = :refresh_token,
                    token_expires_at = :expires_at,
                    updated_at       = NOW()
                WHERE user_id = :uid
            """),
            {
                "uid": user_id,
                "access_token": enc_access,
                "refresh_token": enc_refresh,
                "expires_at": new_expires_at,
            },
        )
        await session.commit()

    logger.info(f"MS token refreshed for user {user_id}")
    return new_access


async def _refresh_token(refresh_token: str) -> tuple[str, str, datetime]:
    """
    Use MSAL to acquire a new access token via refresh token.
    Returns (access_token, refresh_token, expires_at).
    """
    import msal
    from datetime import timezone, timedelta
    from app.core.config import MS365_DELEGATED_SCOPES

    client_id = os.getenv("MS365_CLIENT_ID", "")
    client_secret = os.getenv("MS365_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise RuntimeError("MS365_CLIENT_ID and MS365_CLIENT_SECRET must be configured")

    msal_app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority="https://login.microsoftonline.com/common",
    )

    result = msal_app.acquire_token_by_refresh_token(
        refresh_token=refresh_token,
        scopes=MS365_DELEGATED_SCOPES,
    )

    if "error" in result:
        raise RuntimeError(
            f"MSAL token refresh failed: {result.get('error')} — {result.get('error_description')}"
        )

    access_token = result["access_token"]
    new_refresh = result.get("refresh_token", refresh_token)  # MSAL may return same refresh token
    expires_in = result.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    return access_token, new_refresh, expires_at
