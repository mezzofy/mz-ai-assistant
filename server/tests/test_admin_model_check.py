"""
Tests for POST /admin/model-check — live AI model check endpoint.

Test cases:
  1. test_model_check_claude_success  — mock claude.chat() returns "OK"; assert status ok
  2. test_model_check_claude_api_error — mock raises AuthenticationError; assert status error
  3. test_model_check_timeout          — mock raises TimeoutError; assert status error + message
  4. test_model_check_invalid_model    — send unknown model name; assert 422
  5. test_model_check_requires_admin   — non-admin role; assert 403
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import auth_headers

pytestmark = pytest.mark.unit

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_manager(claude_chat=None, kimi_chat=None):
    """Build a mock LLM manager with mocked client .chat() methods."""
    mock_claude = MagicMock()
    mock_claude.model_name = "claude-sonnet-4-6"
    mock_claude.chat = claude_chat or AsyncMock(return_value={"content": "OK"})

    mock_kimi = MagicMock()
    mock_kimi.model_name = "moonshot-v1-128k"
    mock_kimi.chat = kimi_chat or AsyncMock(return_value={"content": "OK"})

    mgr = MagicMock()
    mgr.claude = mock_claude
    mgr.kimi = mock_kimi
    return mgr


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestModelCheckEndpoint:

    async def test_model_check_claude_success(self, client):
        """Mock claude.chat() returns 'OK' — expect status ok with latency."""
        mock_mgr = _make_mock_manager(
            claude_chat=AsyncMock(return_value={"content": "OK"})
        )
        with patch("app.llm.llm_manager.get", return_value=mock_mgr):
            response = await client.post(
                "/admin/model-check",
                json={"model": "claude"},
                headers=auth_headers("admin"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["model"] == "claude"
        assert data["model_id"] == "claude-sonnet-4-6"
        assert data["message"] == "OK"
        assert isinstance(data["latency_ms"], int)

    async def test_model_check_claude_api_error(self, client):
        """Mock claude.chat() raises an exception — expect status error."""
        mock_mgr = _make_mock_manager(
            claude_chat=AsyncMock(side_effect=Exception("AuthenticationError: Invalid API key"))
        )
        with patch("app.llm.llm_manager.get", return_value=mock_mgr):
            response = await client.post(
                "/admin/model-check",
                json={"model": "claude"},
                headers=auth_headers("admin"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "AuthenticationError" in data["message"]
        assert isinstance(data["latency_ms"], int)

    async def test_model_check_timeout(self, client):
        """Mock asyncio.wait_for raises TimeoutError — expect status error with Timeout message."""
        mock_mgr = _make_mock_manager()

        async def _raise_timeout(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch("app.llm.llm_manager.get", return_value=mock_mgr), \
             patch("app.api.admin.asyncio.wait_for", side_effect=_raise_timeout):
            response = await client.post(
                "/admin/model-check",
                json={"model": "claude"},
                headers=auth_headers("admin"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Timeout" in data["message"]

    async def test_model_check_invalid_model(self, client):
        """Sending an unknown model name should return 422 Unprocessable Entity."""
        response = await client.post(
            "/admin/model-check",
            json={"model": "gpt4"},
            headers=auth_headers("admin"),
        )
        assert response.status_code == 422

    async def test_model_check_requires_admin(self, client):
        """Non-admin role should receive 403 Forbidden."""
        response = await client.post(
            "/admin/model-check",
            json={"model": "claude"},
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 403
