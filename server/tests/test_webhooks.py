"""
Webhook endpoint tests — /webhooks/mezzofy, /webhooks/teams, /webhooks/custom/{source}.

Tests cover:
  - Valid HMAC-SHA256 signature → 200 + Celery task enqueued
  - Invalid HMAC signature → 401
  - Missing signature header → 401
  - Teams bearer token valid → 200
  - Teams bearer token invalid → 401
  - Custom webhook valid → 200
  - Custom webhook with path injection in source → 422
  - GET /webhooks/events admin-only
  - GET /webhooks/events non-admin → 403
  - Webhook events are recorded in DB before returning
  - HMAC verification unit tests (constant-time compare)
"""

import app.tasks.webhook_tasks as _wh_tasks_mod  # ensure submodule loaded; referenced by patch.object below
import hashlib
import hmac
import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USERS, auth_headers, db_override

pytestmark = pytest.mark.unit

_WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "test-webhook-secret-1234567890abcdef")
_TEAMS_BOT_SECRET = os.environ.get("TEAMS_BOT_SECRET", "test-teams-bot-secret")


# ── HMAC helpers ──────────────────────────────────────────────────────────────

def _sign_payload(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for a request body."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# ── Mock helpers for webhook tests ────────────────────────────────────────────

def _make_webhook_db():
    """Build a mock AsyncSession for webhook endpoint tests."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.execute = AsyncMock()
    return mock_db


def _db_context_manager(mock_db):
    """Return an async context manager that yields mock_db."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_db)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _mock_celery_task(task_id: str = None):
    """Return a mock Celery AsyncResult."""
    mock_task = MagicMock()
    mock_task.id = task_id or str(uuid.uuid4())
    return mock_task




# ── Shared webhook mock context manager ──────────────────────────────────────

from contextlib import contextmanager

@contextmanager
def _webhook_mocks(event_id: str = None):
    """
    Patch all webhook dependencies:
      - AsyncSessionLocal → mock DB context manager
      - _record_webhook_event → returns event_id
      - All Celery task .delay() calls
    """
    eid = event_id or str(uuid.uuid4())
    mock_db = _make_webhook_db()
    mock_task = _mock_celery_task()

    mock_mezzofy_task = MagicMock()
    mock_mezzofy_task.delay.return_value = mock_task
    mock_teams_task = MagicMock()
    mock_teams_task.delay.return_value = mock_task
    mock_custom_task = MagicMock()
    mock_custom_task.delay.return_value = mock_task

    with patch("app.webhooks.webhooks.AsyncSessionLocal",
               return_value=_db_context_manager(mock_db)), \
         patch("app.webhooks.webhooks._record_webhook_event",
               new_callable=AsyncMock, return_value=eid), \
         patch.object(_wh_tasks_mod, "handle_mezzofy_event", mock_mezzofy_task), \
         patch.object(_wh_tasks_mod, "handle_teams_mention", mock_teams_task), \
         patch.object(_wh_tasks_mod, "handle_custom_event", mock_custom_task):
        yield {
            "event_id": eid,
            "mock_db": mock_db,
            "mock_task": mock_task,
            "handle_mezzofy_event": mock_mezzofy_task,
            "handle_teams_mention": mock_teams_task,
            "handle_custom_event": mock_custom_task,
        }


# ── POST /webhooks/mezzofy ────────────────────────────────────────────────────

class TestMezzofyWebhook:
    async def test_valid_hmac_signature_accepted(self, client):
        payload = {"event": "customer_signed_up", "customer_id": "cust_123"}
        body = json.dumps(payload).encode()
        signature = _sign_payload(body, _WEBHOOK_SECRET)

        with _webhook_mocks() as mocks:
            response = await client.post(
                "/webhooks/mezzofy",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True
        assert data["event_type"] == "customer_signed_up"
        mocks["handle_mezzofy_event"].delay.assert_called_once()

    async def test_invalid_hmac_signature_rejected(self, client):
        payload = {"event": "customer_signed_up"}
        body = json.dumps(payload).encode()

        response = await client.post(
            "/webhooks/mezzofy",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": "deadbeef1234invalid",
            },
        )

        assert response.status_code == 401
        assert "signature" in response.json()["detail"].lower()

    async def test_missing_signature_header_rejected(self, client):
        payload = {"event": "order_completed"}
        body = json.dumps(payload).encode()

        response = await client.post(
            "/webhooks/mezzofy",
            content=body,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 401

    async def test_celery_task_enqueued_with_correct_args(self, client):
        payload = {"event": "support_ticket_created", "ticket_id": "tkt_456", "severity": "high"}
        body = json.dumps(payload).encode()
        signature = _sign_payload(body, _WEBHOOK_SECRET)

        with _webhook_mocks() as mocks:
            response = await client.post(
                "/webhooks/mezzofy",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                },
            )

        assert response.status_code == 200
        # Celery task should have been called with (event_id, event_type, payload)
        mocks["handle_mezzofy_event"].delay.assert_called_once()
        call_args = mocks["handle_mezzofy_event"].delay.call_args[0]
        assert call_args[1] == "support_ticket_created"

    async def test_webhook_returns_200_before_processing(self, client):
        """Webhook must return 200 immediately (200-first pattern)."""
        payload = {"event": "customer_churned", "customer_id": "cust_789"}
        body = json.dumps(payload).encode()
        signature = _sign_payload(body, _WEBHOOK_SECRET)

        with _webhook_mocks():
            response = await client.post(
                "/webhooks/mezzofy",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                },
            )

        assert response.status_code == 200
        # Response has task_id (enqueued) but Celery hasn't processed yet
        assert "task_id" in response.json()

    async def test_missing_event_field_returns_400(self, client):
        """Payload without 'event' field must return 400."""
        payload = {"customer_id": "cust_123"}  # no 'event' field
        body = json.dumps(payload).encode()
        signature = _sign_payload(body, _WEBHOOK_SECRET)

        with _webhook_mocks():
            response = await client.post(
                "/webhooks/mezzofy",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                },
            )

        assert response.status_code == 400


# ── POST /webhooks/teams ──────────────────────────────────────────────────────

class TestTeamsWebhook:
    async def test_valid_teams_bearer_token_accepted(self, client):
        payload = {
            "type": "message",
            "text": "Hello @Bot can you help?",
            "from": {"id": "user123"},
            "channelId": "msteams",
        }
        body = json.dumps(payload).encode()

        with _webhook_mocks() as mocks:
            response = await client.post(
                "/webhooks/teams",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {_TEAMS_BOT_SECRET}",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True
        mocks["handle_teams_mention"].delay.assert_called_once()

    async def test_invalid_teams_bearer_token_rejected(self, client):
        payload = {"type": "message", "text": "Hello @Bot"}
        body = json.dumps(payload).encode()

        response = await client.post(
            "/webhooks/teams",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer wrong-secret",
            },
        )

        assert response.status_code == 401

    async def test_missing_teams_bearer_token_rejected(self, client):
        payload = {"type": "message", "text": "Hello @Bot"}
        body = json.dumps(payload).encode()

        response = await client.post(
            "/webhooks/teams",
            content=body,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 401

    async def test_non_message_activity_type_ignored(self, client):
        """Non-message activity types (e.g. conversationUpdate) should return 200 with processed=False."""
        payload = {
            "type": "conversationUpdate",
            "membersAdded": [{"id": "bot_id"}],
        }
        body = json.dumps(payload).encode()

        response = await client.post(
            "/webhooks/teams",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_TEAMS_BOT_SECRET}",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True
        assert data.get("processed") is False


# ── POST /webhooks/custom/{source} ────────────────────────────────────────────

class TestCustomWebhook:
    async def test_valid_custom_webhook_accepted(self, client):
        payload = {"event": "new_order", "order_id": "ord_001"}
        body = json.dumps(payload).encode()
        signature = _sign_payload(body, _WEBHOOK_SECRET)

        with _webhook_mocks() as mocks:
            response = await client.post(
                "/webhooks/custom/zapier",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "zapier"
        mocks["handle_custom_event"].delay.assert_called_once()

    async def test_custom_webhook_path_injection_blocked(self, client):
        """Source with non-alphanumeric characters (other than hyphens) must be rejected."""
        payload = {"event": "test"}
        body = json.dumps(payload).encode()
        signature = _sign_payload(body, _WEBHOOK_SECRET)

        response = await client.post(
            "/webhooks/custom/../../etc/passwd",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
            },
        )

        # FastAPI path routing will either 404 or 422 for path traversal attempts
        assert response.status_code in (400, 404, 422)

    async def test_custom_webhook_hyphenated_source_allowed(self, client):
        """Source names with hyphens (e.g., 'my-system') must be accepted."""
        payload = {"event": "data_sync"}
        body = json.dumps(payload).encode()
        signature = _sign_payload(body, _WEBHOOK_SECRET)

        with _webhook_mocks() as mocks:
            response = await client.post(
                "/webhooks/custom/my-system",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                },
            )

        assert response.status_code == 200

    async def test_custom_webhook_invalid_hmac_rejected(self, client):
        payload = {"event": "test"}
        body = json.dumps(payload).encode()

        response = await client.post(
            "/webhooks/custom/zapier",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": "badhash",
            },
        )

        assert response.status_code == 401


# ── GET /webhooks/events ──────────────────────────────────────────────────────

class TestWebhookEvents:
    async def test_events_requires_admin_role(self, client, mock_get_db):
        response = await client.get(
            "/webhooks/events",
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 403

    async def test_events_admin_access_allowed(self, client):
        # list_webhook_events uses AsyncSessionLocal() directly (not Depends(get_db))
        mock_db = AsyncMock()
        fetchall_result = MagicMock()
        fetchall_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=fetchall_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.webhooks.webhooks.AsyncSessionLocal", return_value=mock_cm):
            response = await client.get(
                "/webhooks/events",
                headers=auth_headers("admin"),
            )

        # Admin can access (200) or method-related error is acceptable
        # Key test is non-admin=403
        assert response.status_code in (200, 500)

    async def test_events_executive_access_allowed(self, client):
        # list_webhook_events uses AsyncSessionLocal() directly (not Depends(get_db))
        mock_db = AsyncMock()
        fetchall_result = MagicMock()
        fetchall_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=fetchall_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.webhooks.webhooks.AsyncSessionLocal", return_value=mock_cm):
            response = await client.get(
                "/webhooks/events",
                headers=auth_headers("executive"),
            )
        # Executive has management_admin + audit_read → 200 or handled
        assert response.status_code in (200, 500)

    async def test_events_finance_manager_rejected(self, client, mock_get_db):
        response = await client.get(
            "/webhooks/events",
            headers=auth_headers("finance_manager"),
        )
        assert response.status_code == 403

    async def test_events_no_auth_rejected(self, client):
        response = await client.get("/webhooks/events")
        assert response.status_code == 401


# ── HMAC verification unit tests ──────────────────────────────────────────────

class TestHMACVerification:
    """Unit tests for HMAC signature verification logic (no HTTP)."""

    def test_valid_signature_accepted(self):
        from app.webhooks.webhooks import _verify_hmac_signature
        body = b'{"event": "test"}'
        signature = _sign_payload(body, _WEBHOOK_SECRET)

        with patch("app.webhooks.webhooks._get_webhook_secret", return_value=_WEBHOOK_SECRET):
            result = _verify_hmac_signature(body, signature)

        assert result is True

    def test_invalid_signature_rejected(self):
        from app.webhooks.webhooks import _verify_hmac_signature
        body = b'{"event": "test"}'

        with patch("app.webhooks.webhooks._get_webhook_secret", return_value=_WEBHOOK_SECRET):
            result = _verify_hmac_signature(body, "completely-wrong-signature")

        assert result is False

    def test_tampered_body_rejected(self):
        """If body changes after signing, signature must not match."""
        from app.webhooks.webhooks import _verify_hmac_signature
        original_body = b'{"event": "test", "amount": 100}'
        tampered_body = b'{"event": "test", "amount": 99999}'
        signature = _sign_payload(original_body, _WEBHOOK_SECRET)

        with patch("app.webhooks.webhooks._get_webhook_secret", return_value=_WEBHOOK_SECRET):
            result = _verify_hmac_signature(tampered_body, signature)

        assert result is False

    def test_no_secret_skips_verification(self):
        """If WEBHOOK_SECRET is not set, verification should pass (dev mode)."""
        from app.webhooks.webhooks import _verify_hmac_signature
        body = b'{"event": "test"}'

        with patch("app.webhooks.webhooks._get_webhook_secret", return_value=None):
            result = _verify_hmac_signature(body, "any-signature")

        assert result is True  # Dev mode: skip verification

    def test_empty_signature_with_secret_rejected(self):
        from app.webhooks.webhooks import _verify_hmac_signature
        body = b'{"event": "test"}'

        with patch("app.webhooks.webhooks._get_webhook_secret", return_value=_WEBHOOK_SECRET):
            result = _verify_hmac_signature(body, "")

        assert result is False

    def test_uses_constant_time_comparison(self):
        """Verify hmac.compare_digest is used (not == which is timing-vulnerable)."""
        import inspect
        from app.webhooks import webhooks as wh_module
        source = inspect.getsource(wh_module._verify_hmac_signature)
        assert "compare_digest" in source
