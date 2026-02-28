"""
Shared pytest fixtures for the mz-ai-assistant test suite.

Design principles:
  - Tests are self-contained: heavy dependencies (DB, LLM, Celery, external tools)
    are mocked by default. Integration tests can opt-in via markers.
  - JWT tokens are created with a fixed test secret (JWT_SECRET env var).
  - DB fixtures use transaction rollback for isolation (no leftover test data).
  - All external HTTP calls (MS Graph, LinkedIn, Kimi) are mocked.

Fixture hierarchy:
  event_loop            → asyncio event loop (session-scoped)
  client                → httpx.AsyncClient wrapping the FastAPI app
  make_token(role)      → factory for JWT tokens per role
  mock_config           → patches get_config() with minimal test config
  mock_route_request    → patches route_request() to return a canned response
  mock_db               → patches get_db() with an in-memory async session stub
  mock_celery           → patches Celery task .delay() calls
"""

import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from httpx import AsyncClient, ASGITransport

# ── Set test env before importing app ─────────────────────────────────────────
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("JWT_ACCESS_EXPIRE_MINUTES", "60")
os.environ.setdefault("JWT_REFRESH_EXPIRE_DAYS", "7")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")   # DB 15 = test isolation
os.environ.setdefault("REDIS_RESULT_BACKEND", "redis://localhost:6379/14")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret-1234567890abcdef")
os.environ.setdefault("TEAMS_BOT_SECRET", "test-teams-bot-secret")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://mezzofy_ai:password@localhost:5432/mezzofy_ai_test"),
)

import app.tasks.tasks as _tasks_mod          # ensure submodule loaded; used by mock_celery_delay
import app.tasks.webhook_tasks as _webhook_tasks_mod  # ensure submodule loaded; used by mock_celery_delay

from app.main import app  # noqa: E402 — env must be set first
from app.core.auth import create_access_token, create_refresh_token, hash_password
from app.core.rbac import get_role_permissions  # noqa: E402
from app.core.database import get_db as _get_db_dep
from app.core.rate_limiter import rate_limit_auth as _rate_limit_auth_dep


# ── Minimal test config ───────────────────────────────────────────────────────

TEST_CONFIG = {
    "llm": {
        "default_model": "claude",
        "fallback_model": "kimi",
        "claude": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "api_key": "test-anthropic-key",
            "max_tokens": 1024,
            "temperature": 0.7,
        },
        "kimi": {
            "provider": "moonshot",
            "model": "moonshot-v1-128k",
            "api_key": "test-kimi-key",
            "base_url": "https://api.moonshot.cn/v1",
            "max_tokens": 1024,
            "temperature": 0.7,
        },
        "routing": {
            "chinese_content": "kimi",
            "apac_research": "kimi",
            "default": "claude",
        },
    },
    "server": {"host": "0.0.0.0", "port": 8000, "workers": 1, "debug": True},
    "database": {"url": os.environ["DATABASE_URL"], "pool_size": 5, "max_overflow": 5},
    "redis": {"url": os.environ["REDIS_URL"]},
    "ms365": {
        "tenant_id": "test-tenant",
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "sender_email": "assistant@mezzofy.com",
        "teams": {"sender_user_id": "test-bot-user-id", "channels": {}},
    },
    "tools": {
        "knowledge_base": {"directory": "knowledge"},
        "browser": {"headless": True, "timeout": 30},
        "data": {"directory": "data"},
    },
    "security": {
        "webhook_secret": os.environ["WEBHOOK_SECRET"],
        "teams_bot_secret": os.environ["TEAMS_BOT_SECRET"],
    },
}


# ── Canned agent response ─────────────────────────────────────────────────────

CANNED_AGENT_RESPONSE = {
    "success": True,
    "content": "Test agent response content.",
    "artifacts": [],
    "tools_called": [],
    "agent_used": "test_agent",
}


# ── User data factories ────────────────────────────────────────────────────────

def _make_user(role: str, department: str, user_id: str = None) -> dict:
    """Build a minimal user dict (matches JWT payload shape)."""
    uid = user_id or str(uuid.uuid4())
    return {
        "id": uid,
        "user_id": uid,
        "sub": uid,
        "email": f"test_{role}@mezzofy.com",
        "name": f"Test {role.replace('_', ' ').title()}",
        "department": department,
        "role": role,
        "permissions": get_role_permissions(role),
        "token_type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    }


USERS = {
    "admin":              _make_user("admin", "management"),
    "executive":          _make_user("executive", "management"),
    "finance_manager":    _make_user("finance_manager", "finance"),
    "finance_viewer":     _make_user("finance_viewer", "finance"),
    "sales_rep":          _make_user("sales_rep", "sales"),
    "sales_manager":      _make_user("sales_manager", "sales"),
    "marketing_creator":  _make_user("marketing_creator", "marketing"),
    "marketing_manager":  _make_user("marketing_manager", "marketing"),
    "support_agent":      _make_user("support_agent", "support"),
    "support_manager":    _make_user("support_manager", "support"),
}


def make_token(role: str) -> str:
    """Return a valid JWT access token for the given role."""
    return create_access_token(USERS[role])


def make_refresh_token(role: str) -> str:
    """Return a valid JWT refresh token for the given role."""
    return create_refresh_token(USERS[role])


def auth_headers(role: str) -> dict:
    """Return Authorization headers for the given role."""
    return {"Authorization": f"Bearer {make_token(role)}"}


# ── Core fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient backed by the FastAPI ASGI app (no running server needed)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_config():
    """Patch get_config() to return TEST_CONFIG (avoids config.yaml requirement)."""
    with patch("app.core.config.get_config", return_value=TEST_CONFIG), \
         patch("app.api.chat.get_config", return_value=TEST_CONFIG), \
         patch("app.api.files.get_config", return_value=TEST_CONFIG) if hasattr(app, "files") else patch("builtins.open"):
        yield TEST_CONFIG


@pytest.fixture
def mock_route_request():
    """Patch route_request() to return CANNED_AGENT_RESPONSE without real agent execution."""
    with patch("app.router.route_request", new_callable=AsyncMock, return_value=CANNED_AGENT_RESPONSE) as mock:
        yield mock


@pytest.fixture
def mock_process_result():
    """Patch process_result() to return a minimal formatted response."""
    canned = {
        "session_id": str(uuid.uuid4()),
        "message": "Test agent response content.",
        "artifacts": [],
        "agent_used": "test_agent",
        "processing_time_ms": 42,
    }
    with patch("app.api.chat.process_result", new_callable=AsyncMock, return_value=canned) as mock:
        yield mock


@pytest.fixture
def mock_session_manager():
    """Patch session_manager functions to avoid real DB access in chat tests."""
    canned_session = {
        "id": str(uuid.uuid4()),
        "user_id": USERS["sales_rep"]["user_id"],
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with patch("app.api.chat.get_or_create_session", new_callable=AsyncMock, return_value=canned_session) as mock_create, \
         patch("app.api.chat.get_session_messages", new_callable=AsyncMock, return_value=[]) as mock_msgs, \
         patch("app.api.chat.list_user_sessions", new_callable=AsyncMock, return_value=[canned_session]) as mock_list:
        yield {"session": canned_session, "create": mock_create, "messages": mock_msgs, "list": mock_list}


@pytest.fixture
def mock_db_session():
    """
    Patch _db_session() async context manager to yield a mock AsyncSession.
    Used for chat endpoint tests that call _db_session().
    """
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    # Make it work as async context manager
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.api.chat._db_session", return_value=mock_cm):
        yield mock_session


@pytest.fixture
def mock_celery_delay():
    """Patch Celery task .delay() calls to avoid actually enqueuing tasks."""
    mock_result = MagicMock()
    mock_result.id = str(uuid.uuid4())

    # Patch at source module so lazy imports inside functions pick up the mocks
    with patch.object(_tasks_mod, "process_agent_task") as mock_task, \
         patch.object(_webhook_tasks_mod, "handle_mezzofy_event") as mock_mezzofy, \
         patch.object(_webhook_tasks_mod, "handle_teams_mention") as mock_teams, \
         patch.object(_webhook_tasks_mod, "handle_custom_event") as mock_custom:
        mock_task.delay.return_value = mock_result
        mock_mezzofy.delay.return_value = mock_result
        mock_teams.delay.return_value = mock_result
        mock_custom.delay.return_value = mock_result
        yield {
            "process_agent_task": mock_task,
            "handle_mezzofy_event": mock_mezzofy,
            "handle_teams_mention": mock_teams,
            "handle_custom_event": mock_custom,
            "task_id": mock_result.id,
        }


@pytest.fixture
def mock_rate_limiter():
    """Override FastAPI rate limit dependencies to always allow requests (no real Redis)."""
    async def _allow_auth(request: Request) -> None:
        return None

    async def _allow_check(*args, **kwargs):
        return None

    # Override the FastAPI Depends()-captured function via dependency_overrides
    app.dependency_overrides[_rate_limit_auth_dep] = _allow_auth
    # Also patch direct calls in gateway middleware (not a Depends)
    with patch("app.gateway.check_rate_limit", side_effect=_allow_check):
        yield
    app.dependency_overrides.pop(_rate_limit_auth_dep, None)


@pytest.fixture
def mock_audit_log():
    """Patch audit log writes to avoid DB dependency."""
    with patch("app.core.audit.log_action", new_callable=AsyncMock):
        yield


@pytest.fixture
def mock_redis_blacklist():
    """Patch Redis blacklist checks for auth tests.

    auth.py uses local imports: `from app.core.auth import blacklist_refresh_token, is_refresh_token_blacklisted`.
    Must patch both the source module AND the local copy in app.api.auth.
    """
    with patch("app.core.auth.is_refresh_token_blacklisted", new_callable=AsyncMock, return_value=False), \
         patch("app.core.auth.blacklist_refresh_token", new_callable=AsyncMock), \
         patch("app.api.auth.is_refresh_token_blacklisted", new_callable=AsyncMock, return_value=False), \
         patch("app.api.auth.blacklist_refresh_token", new_callable=AsyncMock):
        yield


@pytest.fixture
def mock_db_get_user():
    """
    Patch _get_user_by_email to return a test user from an in-memory dict.
    Allows auth tests to run without a real database.
    """
    _test_users = {
        "sales@test.com": {
            "id": USERS["sales_rep"]["user_id"],
            "email": "sales@test.com",
            "password_hash": hash_password("password123"),
            "name": "Test Sales Rep",
            "department": "sales",
            "role": "sales_rep",
            "is_active": True,
        },
        "finance@test.com": {
            "id": USERS["finance_manager"]["user_id"],
            "email": "finance@test.com",
            "password_hash": hash_password("password123"),
            "name": "Test Finance Manager",
            "department": "finance",
            "role": "finance_manager",
            "is_active": True,
        },
        "admin@test.com": {
            "id": USERS["admin"]["user_id"],
            "email": "admin@test.com",
            "password_hash": hash_password("password123"),
            "name": "Test Admin",
            "department": "management",
            "role": "admin",
            "is_active": True,
        },
        "inactive@test.com": {
            "id": str(uuid.uuid4()),
            "email": "inactive@test.com",
            "password_hash": hash_password("password123"),
            "name": "Inactive User",
            "department": "sales",
            "role": "sales_rep",
            "is_active": False,
        },
    }

    async def _get_user(db, email: str):
        return _test_users.get(email)

    with patch("app.api.auth._get_user_by_email", side_effect=_get_user), \
         patch("app.api.auth._update_last_login", new_callable=AsyncMock):
        yield _test_users


@pytest.fixture
def mock_get_db():
    """Override the get_db FastAPI dependency with a mock AsyncSession (no real DB)."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0    # default COUNT(*) = 0
    mock_result.fetchall.return_value = []
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def _get_db_override():
        yield mock_session

    # Use app.dependency_overrides so all Depends(get_db) endpoints are mocked
    app.dependency_overrides[_get_db_dep] = _get_db_override
    yield mock_session
    app.dependency_overrides.pop(_get_db_dep, None)


@contextmanager
def db_override(mock_db=None):
    """
    Context manager to override get_db for a single test with a custom mock session.
    Use this instead of patch("...get_db") for endpoints that use Depends(get_db).

    Usage:
        with db_override(mock_db):
            response = await client.get(...)
    """
    if mock_db is None:
        mock_db = AsyncMock()
        result = MagicMock()
        result.scalar.return_value = 0
        result.fetchall.return_value = []
        result.fetchone.return_value = None
        mock_db.execute = AsyncMock(return_value=result)
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()

    async def _override():
        yield mock_db

    app.dependency_overrides[_get_db_dep] = _override
    try:
        yield mock_db
    finally:
        app.dependency_overrides.pop(_get_db_dep, None)
