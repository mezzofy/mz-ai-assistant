"""
E2E integration test: PDF chat flow via live EC2 API.

Validates the full stack:
  JWT auth → POST /chat/send-media → Anthropic Files API → LLM analysis
  → persisted conversation → GET /chat/history

Requirements (all must be true to run):
  - Live mezzofy-api.service on localhost:8000 (run this test ON EC2)
  - PDF exists at MZ_PDF_PATH (default path covers the known artifact location)
  - MZ_TEST_ADMIN_PASSWORD env var set (never hardcoded)

Run on EC2:
    MZ_TEST_ADMIN_PASSWORD="<pass>" \\
    pytest tests/test_e2e_pdf_chat.py -v -m integration 2>&1 | \\
    tee tests/results/e2e-pdf-chat-report.md

Optional overrides:
    MZ_API_BASE_URL    — default: http://localhost:8000
    MZ_TEST_ADMIN_EMAIL — default: admin@mezzofy.com
    MZ_PDF_PATH        — default: /var/mezzofy/artifacts/.../Mezzofy Coupon RWA Exchange Whitepaper.pdf
"""

import os
from pathlib import Path

import httpx
import pytest

# ── Configuration ─────────────────────────────────────────────────────────────

PDF_PATH = os.getenv(
    "MZ_PDF_PATH",
    "/var/mezzofy/artifacts/management/admin@mezzofy.com/"
    "Mezzofy Coupon RWA Exchange Whitepaper.pdf",
)

ADMIN_EMAIL = os.getenv("MZ_TEST_ADMIN_EMAIL", "admin@mezzofy.com")
ADMIN_PASSWORD = os.getenv("MZ_TEST_ADMIN_PASSWORD")  # REQUIRED — no default
API_BASE_URL = os.getenv("MZ_API_BASE_URL", "http://localhost:8000")

_PDF_FILENAME = "Mezzofy Coupon RWA Exchange Whitepaper.pdf"
_CHAT_QUESTION = "What are the key topics covered in this document?"

# ── Module-level skip guards ──────────────────────────────────────────────────

if not ADMIN_PASSWORD:
    pytest.skip(
        "MZ_TEST_ADMIN_PASSWORD not set — cannot run E2E tests without credentials",
        allow_module_level=True,
    )

# ── Lazy call cache (avoids repeated API calls across test functions) ──────────
#
# pytest-asyncio 0.23 creates a new event loop per test by default.
# Module-scoped async fixtures require a shared event loop (complex to configure).
# Instead, we use a plain module-level dict to cache plain-Python results
# (strings, dicts) across function-scoped async fixtures.
# The first test that needs the upload triggers it; subsequent tests reuse the cache.
#
_cache: dict = {}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def admin_token() -> str:
    """Login as admin once per module run; cache the access token."""
    if "access_token" not in _cache:
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
            resp = await client.post(
                "/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            )
        assert resp.status_code == 200, (
            f"Login failed ({resp.status_code}): {resp.text}"
        )
        _cache["access_token"] = resp.json()["access_token"]
    return _cache["access_token"]


@pytest.fixture
async def pdf_upload_response(admin_token: str) -> dict:
    """
    Upload the whitepaper PDF to /chat/send-media once; cache the response body.

    Uses a sync (non-async-keyword) path: message has no long-running keywords,
    so the server returns 200 directly (not 202/Celery).
    """
    if "upload_response" not in _cache:
        pdf_bytes = Path(PDF_PATH).read_bytes()
        headers = {"Authorization": f"Bearer {admin_token}"}
        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=120.0) as client:
            resp = await client.post(
                "/chat/send-media",
                headers=headers,
                files={
                    "media_file": (_PDF_FILENAME, pdf_bytes, "application/pdf"),
                },
                data={
                    "message": _CHAT_QUESTION,
                    "input_type": "file",
                },
            )
        assert resp.status_code == 200, (
            f"PDF upload returned HTTP {resp.status_code} (expected 200 — sync path). "
            f"If 202, the message triggered an async path unexpectedly. "
            f"Body: {resp.text[:500]}"
        )
        _cache["upload_response"] = resp.json()
    return _cache["upload_response"]


# ── Test class ────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.skipif(
    not os.path.exists(PDF_PATH),
    reason=f"PDF not found at {PDF_PATH} — run this test on EC2",
)
class TestPDFChatFlowE2E:
    """
    End-to-end tests for the PDF chat flow.

    All tests call the live mezzofy-api.service on localhost:8000.
    No mocks — real Anthropic Files API, real PostgreSQL, real LLM response.
    """

    async def test_upload_pdf_returns_200_success(
        self, pdf_upload_response: dict
    ) -> None:
        """Happy path: full stack accepts the PDF and returns a non-empty LLM response."""
        body = pdf_upload_response

        assert body.get("success") is True, (
            f"success is not True. Full response: {body}"
        )

        response_text = body.get("response", "")
        assert isinstance(response_text, str) and len(response_text) > 0, (
            "response must be a non-empty string"
        )

        session_id = body.get("session_id", "")
        assert isinstance(session_id, str) and session_id, (
            "session_id must be a non-empty string"
        )

        task_id = body.get("task_id")
        assert task_id is not None and task_id != "", (
            "task_id must be set (sync path inserts a completed agent_tasks row)"
        )

    async def test_pdf_input_processed_summary(
        self, pdf_upload_response: dict
    ) -> None:
        """input_processed.summary reflects the uploaded filename or Files API reference."""
        body = pdf_upload_response

        input_processed = body.get("input_processed")
        assert input_processed is not None, (
            "input_processed must not be None for file uploads — "
            "file_handler sets this via task['input_summary']"
        )

        summary: str = input_processed.get("summary", "")
        assert summary, "input_processed.summary must be non-empty"

        # file_handler sets: "File: <filename> (uploaded via Files API)"
        has_filename = _PDF_FILENAME in summary or ".pdf" in summary.lower()
        has_files_api_ref = "Files API" in summary
        assert has_filename or has_files_api_ref, (
            f"input_processed.summary should reference the file name or Files API. "
            f"Got: {summary!r}"
        )

    async def test_session_history_contains_pdf_exchange(
        self, pdf_upload_response: dict, admin_token: str
    ) -> None:
        """Conversation is persisted: session history has user + assistant messages."""
        session_id = pdf_upload_response["session_id"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
            resp = await client.get(
                f"/chat/history/{session_id}",
                headers=headers,
            )

        assert resp.status_code == 200, (
            f"GET /chat/history/{session_id} returned {resp.status_code}: {resp.text}"
        )

        data = resp.json()
        messages = data.get("messages", [])
        assert len(messages) >= 2, (
            f"Expected ≥ 2 messages (user + assistant) in history, got {len(messages)}"
        )

        roles = [m.get("role") for m in messages]
        assert "user" in roles, "No user message found in session history"
        assert "assistant" in roles, "No assistant message found in session history"

        # User message must reference the question text or the uploaded filename
        user_content = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        has_question = _CHAT_QUESTION in user_content
        has_file_ref = ".pdf" in user_content.lower() or _PDF_FILENAME.lower() in user_content.lower()
        assert has_question or has_file_ref, (
            f"User message does not reference question or filename. "
            f"Content (first 300 chars): {user_content[:300]!r}"
        )

        # Assistant message must not be empty
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        for msg in assistant_msgs:
            assert msg.get("content"), "Assistant message content must be non-empty"

    async def test_pdf_response_mentions_document_content(
        self, pdf_upload_response: dict
    ) -> None:
        """Claude actually read the PDF — response references at least one known keyword."""
        response_text: str = pdf_upload_response.get("response", "")

        assert len(response_text) >= 50, (
            f"Response is too short ({len(response_text)} chars) to be a meaningful LLM answer"
        )

        keywords = ["mezzofy", "coupon", "rwa", "exchange", "whitepaper"]
        assert any(kw in response_text.lower() for kw in keywords), (
            f"Response does not mention any document-specific keyword from {keywords}. "
            f"First 500 chars: {response_text[:500]!r}"
        )

    async def test_unauthenticated_pdf_upload_rejected(self) -> None:
        """Auth guard is active on /chat/send-media — missing token returns 401 or 403."""
        pdf_bytes = Path(PDF_PATH).read_bytes()

        async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
            resp = await client.post(
                "/chat/send-media",
                # Deliberately omit Authorization header
                files={
                    "media_file": (_PDF_FILENAME, pdf_bytes, "application/pdf"),
                },
                data={
                    "message": _CHAT_QUESTION,
                    "input_type": "file",
                },
            )

        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403 for unauthenticated upload, got {resp.status_code}. "
            f"The auth guard on /chat/send-media may not be active."
        )
