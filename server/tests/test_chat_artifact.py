"""
Tests for POST /chat/send-artifact endpoint.

Covers:
  - HTTP status codes: success 200, missing artifact 404, wrong user 404,
    file missing from disk 404, OSError on read 500, unauthenticated 401,
    empty message allowed 200
  - Ownership: WHERE clause uses both artifact_id AND user_id; 404 (not 403)
  - Pipeline: process_input called with file_bytes + filename; input_type="file"
    in task; user_message in DB includes [file: filename]
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    USERS, auth_headers, CANNED_AGENT_RESPONSE,
)

pytestmark = pytest.mark.unit

# ── Shared test data ──────────────────────────────────────────────────────────

ARTIFACT_ID = str(uuid.uuid4())
FILE_BYTES = b"fake pdf content for testing"
FILENAME = "quarterly_report.pdf"
FILE_PATH = f"/data/uploads/personal/{FILENAME}"

# Patch targets — safe helpers in chat.py (avoids patching Path class-wide,
# which breaks pytest's assertion rewriter via Path.read_bytes)
_EXISTS = "app.api.chat._artifact_path_exists"
_READ = "app.api.chat._read_artifact_bytes"


def _make_artifact_row(
    filename: str = FILENAME,
    file_path: str = FILE_PATH,
    file_type: str = "pdf",
):
    """Return a mock row as returned by db.execute().fetchone()."""
    row = MagicMock()
    row.id = ARTIFACT_ID
    row.filename = filename
    row.file_path = file_path
    row.file_type = file_type
    return row


def _make_db_session_cm(artifact_row):
    """Build a mock _db_session async context manager that yields a mock session."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = artifact_row
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm, mock_session


def _canned_process_result():
    return {
        "session_id": str(uuid.uuid4()),
        "response": "Here is the summary of your quarterly report.",
        "artifacts": [],
        "agent_used": "test_agent",
        "tools_used": [],
        "input_processed": {"summary": "PDF file processed"},
        "success": True,
    }


# ── TestSendArtifact ──────────────────────────────────────────────────────────

class TestSendArtifact:
    """HTTP status codes and basic request/response shape."""

    async def test_send_artifact_success_200(self, client, mock_config, mock_audit_log):
        """Happy path: artifact found, file readable, AI responds."""
        artifact_row = _make_artifact_row()
        mock_cm, _ = _make_db_session_cm(artifact_row)
        session_val = {"id": str(uuid.uuid4()), "user_id": USERS["sales_rep"]["user_id"], "messages": []}

        with patch("app.api.chat._db_session", return_value=mock_cm), \
             patch(_EXISTS, return_value=True), \
             patch(_READ, return_value=FILE_BYTES), \
             patch("app.api.chat.process_input", new_callable=AsyncMock,
                   side_effect=lambda task, **kw: {**task, "input_summary": "PDF processed"}), \
             patch("app.api.chat.route_request", new_callable=AsyncMock,
                   return_value=CANNED_AGENT_RESPONSE), \
             patch("app.api.chat.process_result", new_callable=AsyncMock,
                   return_value=_canned_process_result()), \
             patch("app.api.chat.get_or_create_session", new_callable=AsyncMock,
                   return_value=session_val):
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": ARTIFACT_ID, "message": "summarize in 100 words"},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "response" in data

    async def test_send_artifact_empty_message_allowed_200(self, client, mock_config, mock_audit_log):
        """Empty message is valid — AI describes the file without a user prompt."""
        artifact_row = _make_artifact_row()
        mock_cm, _ = _make_db_session_cm(artifact_row)
        session_val = {"id": str(uuid.uuid4()), "user_id": USERS["sales_rep"]["user_id"], "messages": []}

        with patch("app.api.chat._db_session", return_value=mock_cm), \
             patch(_EXISTS, return_value=True), \
             patch(_READ, return_value=FILE_BYTES), \
             patch("app.api.chat.process_input", new_callable=AsyncMock,
                   side_effect=lambda task, **kw: task), \
             patch("app.api.chat.route_request", new_callable=AsyncMock,
                   return_value=CANNED_AGENT_RESPONSE), \
             patch("app.api.chat.process_result", new_callable=AsyncMock,
                   return_value=_canned_process_result()), \
             patch("app.api.chat.get_or_create_session", new_callable=AsyncMock,
                   return_value=session_val):
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": ARTIFACT_ID, "message": ""},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200

    async def test_send_artifact_unauthenticated_401(self, client):
        """No Authorization header → 401."""
        response = await client.post(
            "/chat/send-artifact",
            json={"artifact_id": ARTIFACT_ID, "message": "summarize"},
        )
        assert response.status_code == 401

    async def test_send_artifact_missing_artifact_404(self, client, mock_config, mock_audit_log):
        """artifact_id not found in DB → 404."""
        mock_cm, _ = _make_db_session_cm(artifact_row=None)  # fetchone returns None

        with patch("app.api.chat._db_session", return_value=mock_cm):
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": str(uuid.uuid4()), "message": "summarize"},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 404
        assert "Artifact not found" in response.json()["detail"]

    async def test_send_artifact_file_missing_from_disk_404(self, client, mock_config, mock_audit_log):
        """Artifact found in DB but file deleted from disk → 404."""
        artifact_row = _make_artifact_row()
        mock_cm, _ = _make_db_session_cm(artifact_row)

        with patch("app.api.chat._db_session", return_value=mock_cm), \
             patch(_EXISTS, return_value=False):
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": ARTIFACT_ID, "message": "summarize"},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 404
        assert "removed from storage" in response.json()["detail"]

    async def test_send_artifact_oserror_on_read_500(self, client, mock_config, mock_audit_log):
        """OSError when reading file bytes → 500."""
        artifact_row = _make_artifact_row()
        mock_cm, _ = _make_db_session_cm(artifact_row)

        with patch("app.api.chat._db_session", return_value=mock_cm), \
             patch(_EXISTS, return_value=True), \
             patch(_READ, side_effect=OSError("permission denied")):
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": ARTIFACT_ID, "message": "summarize"},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 500
        assert "Failed to read file" in response.json()["detail"]


# ── TestSendArtifactOwnership ─────────────────────────────────────────────────

class TestSendArtifactOwnership:
    """WHERE clause uses both artifact_id AND user_id; 404 (not 403) to prevent info leakage."""

    async def test_wrong_user_gets_404_not_403(self, client, mock_config, mock_audit_log):
        """Another user's artifact_id → 404 (not 403 — no info leakage)."""
        # fetchone returns None because user_id doesn't match in WHERE clause
        mock_cm, _ = _make_db_session_cm(artifact_row=None)

        with patch("app.api.chat._db_session", return_value=mock_cm):
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": ARTIFACT_ID, "message": "summarize"},
                headers=auth_headers("finance_manager"),  # different user
            )

        assert response.status_code == 404
        assert response.status_code != 403  # no 403 — attacker learns nothing

    async def test_sql_query_uses_both_artifact_id_and_user_id(
        self, client, mock_config, mock_audit_log
    ):
        """Verify the DB query filters on BOTH id AND user_id."""
        artifact_row = _make_artifact_row()
        mock_cm, mock_session = _make_db_session_cm(artifact_row)
        session_val = {"id": str(uuid.uuid4()), "user_id": USERS["sales_rep"]["user_id"], "messages": []}

        with patch("app.api.chat._db_session", return_value=mock_cm), \
             patch(_EXISTS, return_value=True), \
             patch(_READ, return_value=FILE_BYTES), \
             patch("app.api.chat.process_input", new_callable=AsyncMock,
                   side_effect=lambda task, **kw: task), \
             patch("app.api.chat.route_request", new_callable=AsyncMock,
                   return_value=CANNED_AGENT_RESPONSE), \
             patch("app.api.chat.process_result", new_callable=AsyncMock,
                   return_value=_canned_process_result()), \
             patch("app.api.chat.get_or_create_session", new_callable=AsyncMock,
                   return_value=session_val):
            await client.post(
                "/chat/send-artifact",
                json={"artifact_id": ARTIFACT_ID, "message": "summarize"},
                headers=auth_headers("sales_rep"),
            )

        # The first execute call is the artifact ownership lookup
        execute_call_str = str(mock_session.execute.call_args_list[0])
        assert "aid" in execute_call_str or ARTIFACT_ID in execute_call_str
        assert "uid" in execute_call_str or USERS["sales_rep"]["user_id"] in execute_call_str


# ── TestSendArtifactPipeline ──────────────────────────────────────────────────

class TestSendArtifactPipeline:
    """Verify the correct calls are made through the processing pipeline."""

    async def _call_send_artifact(
        self, client, mock_process_input, mock_route_request,
        mock_process_result_fn, session_val, artifact_row, message="summarize this",
    ):
        mock_cm, _ = _make_db_session_cm(artifact_row)
        with patch("app.api.chat._db_session", return_value=mock_cm), \
             patch(_EXISTS, return_value=True), \
             patch(_READ, return_value=FILE_BYTES), \
             patch("app.api.chat.process_input", mock_process_input), \
             patch("app.api.chat.route_request", mock_route_request), \
             patch("app.api.chat.process_result", mock_process_result_fn), \
             patch("app.api.chat.get_or_create_session", new_callable=AsyncMock,
                   return_value=session_val):
            return await client.post(
                "/chat/send-artifact",
                json={"artifact_id": ARTIFACT_ID, "message": message},
                headers=auth_headers("sales_rep"),
            )

    async def test_process_input_called_with_file_bytes_and_filename(
        self, client, mock_config, mock_audit_log
    ):
        """process_input must receive file_bytes= and filename= kwargs."""
        artifact_row = _make_artifact_row()
        session_val = {"id": str(uuid.uuid4()), "user_id": USERS["sales_rep"]["user_id"], "messages": []}

        mock_pi = AsyncMock(side_effect=lambda task, **kw: {**task, "input_summary": "ok"})
        mock_rr = AsyncMock(return_value=CANNED_AGENT_RESPONSE)
        mock_pr = AsyncMock(return_value=_canned_process_result())

        await self._call_send_artifact(client, mock_pi, mock_rr, mock_pr, session_val, artifact_row)

        mock_pi.assert_called_once()
        _, kwargs = mock_pi.call_args
        assert kwargs.get("file_bytes") == FILE_BYTES
        assert kwargs.get("filename") == FILENAME

    async def test_task_input_type_is_file(self, client, mock_config, mock_audit_log):
        """The task dict passed to process_input must have input_type='file'."""
        artifact_row = _make_artifact_row()
        session_val = {"id": str(uuid.uuid4()), "user_id": USERS["sales_rep"]["user_id"], "messages": []}
        captured_task = {}

        async def capture_pi(task, **kw):
            captured_task.update(task)
            return {**task, "input_summary": "ok"}

        mock_rr = AsyncMock(return_value=CANNED_AGENT_RESPONSE)
        mock_pr = AsyncMock(return_value=_canned_process_result())

        await self._call_send_artifact(
            client, AsyncMock(side_effect=capture_pi), mock_rr, mock_pr, session_val, artifact_row
        )

        assert captured_task.get("input_type") == "file"

    async def test_user_message_includes_file_label(self, client, mock_config, mock_audit_log):
        """process_result user_message must include '[file: filename]'."""
        artifact_row = _make_artifact_row()
        session_val = {"id": str(uuid.uuid4()), "user_id": USERS["sales_rep"]["user_id"], "messages": []}

        mock_pi = AsyncMock(side_effect=lambda task, **kw: {**task, "input_summary": "ok"})
        mock_rr = AsyncMock(return_value=CANNED_AGENT_RESPONSE)
        mock_pr = AsyncMock(return_value=_canned_process_result())

        await self._call_send_artifact(
            client, mock_pi, mock_rr, mock_pr, session_val, artifact_row,
            message="give me a summary"
        )

        mock_pr.assert_called_once()
        call_kwargs = mock_pr.call_args[1]
        user_message = call_kwargs.get("user_message", "")
        assert f"[file: {FILENAME}]" in user_message

    async def test_route_request_called_once(self, client, mock_config, mock_audit_log):
        """route_request must be called exactly once per send-artifact request."""
        artifact_row = _make_artifact_row()
        session_val = {"id": str(uuid.uuid4()), "user_id": USERS["sales_rep"]["user_id"], "messages": []}

        mock_pi = AsyncMock(side_effect=lambda task, **kw: {**task, "input_summary": "ok"})
        mock_rr = AsyncMock(return_value=CANNED_AGENT_RESPONSE)
        mock_pr = AsyncMock(return_value=_canned_process_result())

        await self._call_send_artifact(client, mock_pi, mock_rr, mock_pr, session_val, artifact_row)

        mock_rr.assert_called_once()

    async def test_session_id_passed_through(self, client, mock_config, mock_audit_log):
        """Optional session_id in request is passed to get_or_create_session."""
        artifact_row = _make_artifact_row()
        existing_session_id = str(uuid.uuid4())
        session_val = {"id": existing_session_id, "user_id": USERS["sales_rep"]["user_id"], "messages": []}

        mock_pi = AsyncMock(side_effect=lambda task, **kw: {**task, "input_summary": "ok"})
        mock_rr = AsyncMock(return_value=CANNED_AGENT_RESPONSE)
        mock_pr = AsyncMock(return_value=_canned_process_result())
        mock_cm, _ = _make_db_session_cm(artifact_row)

        with patch("app.api.chat._db_session", return_value=mock_cm), \
             patch(_EXISTS, return_value=True), \
             patch(_READ, return_value=FILE_BYTES), \
             patch("app.api.chat.process_input", mock_pi), \
             patch("app.api.chat.route_request", mock_rr), \
             patch("app.api.chat.process_result", mock_pr), \
             patch("app.api.chat.get_or_create_session", new_callable=AsyncMock,
                   return_value=session_val) as mock_gocs:
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": ARTIFACT_ID, "message": "summarize",
                      "session_id": existing_session_id},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        mock_gocs.assert_called_once()
        # session_id is the 3rd positional arg to get_or_create_session
        call_args = mock_gocs.call_args[0]
        assert call_args[2] == existing_session_id
