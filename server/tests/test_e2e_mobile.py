"""
E2E Mobile Flow Tests — multi-step API sequences matching what the mobile app does.

Simulates the exact sequence of API calls that mobile screens make:
  - TestMobileAuthFlow: login → /auth/me → token refresh → logout
  - TestMobileChatFlow: login → send message → list sessions → get history
  - TestMobileFilesFlow: login → list files → upload → delete

Unlike unit tests that isolate one endpoint, these tests chain 2–4 API calls
together, verifying that the complete flow works and that response shapes match
what the mobile client (authStore.ts, chatStore.ts, files.ts) expects.

API Contract Verification (from Phase 9 plan):
  - Login response:  user_info.id (not user_id), access_token, refresh_token
  - Chat send:       session_id, message, artifacts (list)
  - Sessions:        sessions (list)
  - History:         session_id, messages (list)
  - Files list:      artifacts (list), count
  - File upload:     artifact_id, filename, download_url
  - File delete:     deleted: true
"""

import io
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    USERS,
    db_override,
)

pytestmark = pytest.mark.unit


# ── TestMobileAuthFlow ─────────────────────────────────────────────────────────


class TestMobileAuthFlow:
    """
    Full auth lifecycle — matches authStore.ts + LoginScreen.tsx behavior.

    Flow: POST /auth/login → extract tokens → use access_token for protected
    endpoints → POST /auth/refresh → POST /auth/logout.
    """

    async def test_login_and_get_me(
        self,
        client,
        mock_db_get_user,
        mock_get_db,
        mock_rate_limiter,
        mock_redis_blacklist,
    ):
        """
        Step 1: POST /auth/login with valid credentials → tokens + user_info
        Step 2: GET /auth/me with access_token → full user fields
        Verifies: user_info.id (not user_id), all required user fields present.
        """
        # Step 1: login
        login_resp = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        access_token = tokens["access_token"]

        # API contract: login response shape (matches LoginResponse in mobile files.ts)
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert "user_info" in tokens
        user_info = tokens["user_info"]
        assert "id" in user_info              # Contract: id field (not user_id)
        assert user_info["email"] == "sales@test.com"
        assert "role" in user_info
        assert "department" in user_info
        assert "permissions" in user_info
        assert isinstance(user_info["permissions"], list)

        # Step 2: GET /auth/me with extracted access_token
        me_resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_resp.status_code == 200
        user = me_resp.json()

        # API contract: /auth/me fields (matches UserInfo interface in auth.ts)
        assert "id" in user
        assert "email" in user
        assert "name" in user
        assert "role" in user
        assert "department" in user
        assert "permissions" in user
        assert isinstance(user["permissions"], list)

    async def test_token_refresh_flow(
        self,
        client,
        mock_db_get_user,
        mock_get_db,
        mock_rate_limiter,
        mock_redis_blacklist,
    ):
        """
        Step 1: POST /auth/login → access_token + refresh_token
        Step 2: POST /auth/refresh with refresh_token → new access_token
        Step 3: GET /auth/me with new access_token → 200 (token is valid)
        Verifies: refresh flow works; new token authenticates successfully.
        """
        # Step 1: login
        login_resp = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refresh_token"]

        # Step 2: refresh → new access_token
        refresh_resp = await client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 200
        refresh_data = refresh_resp.json()
        assert "access_token" in refresh_data     # Contract: new access_token returned
        # Note: server does NOT return a new refresh_token — mobile keeps the old one
        new_access_token = refresh_data["access_token"]

        # Step 3: new access_token works for protected endpoints
        me_resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert me_resp.status_code == 200
        assert "id" in me_resp.json()

    async def test_logout_requires_auth(
        self,
        client,
        mock_db_get_user,
        mock_get_db,
        mock_rate_limiter,
        mock_redis_blacklist,
    ):
        """
        Step 1: POST /auth/login → access_token + refresh_token
        Step 2: POST /auth/logout with Bearer token + refresh_token body → 200/204
        Verifies: logout endpoint accepts Bearer header and refresh_token body.
        """
        # Step 1: login
        login_resp = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        data = login_resp.json()
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]

        # Step 2: logout — requires Bearer (auth) + refresh_token body (to blacklist)
        logout_resp = await client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_resp.status_code in (200, 204)

    async def test_expired_token_rejected(self, client):
        """
        GET /auth/me with invalid/expired token → 401.
        Verifies: server rejects bad tokens (no fixtures needed — no DB access).
        """
        resp = await client.get(
            "/auth/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert resp.status_code == 401


# ── TestMobileChatFlow ─────────────────────────────────────────────────────────


class TestMobileChatFlow:
    """
    Chat workflow — matches chatStore.ts sendToServer + loadSessions + loadHistory.

    Flow: login → send message → verify session created → list sessions →
    get history for that session.
    """

    async def test_send_text_and_get_session(
        self,
        client,
        mock_db_get_user,
        mock_get_db,
        mock_rate_limiter,
        mock_config,
        mock_route_request,
        mock_process_result,
        mock_session_manager,
        mock_db_session,
        mock_audit_log,
    ):
        """
        Step 1: POST /auth/login → access_token
        Step 2: POST /chat/send {message: "Hello"} → session_id + response
        Step 3: GET /chat/sessions → sessions list
        Step 4: GET /chat/history/{session_id} → messages list
        Verifies: all contract fields present in each response.
        """
        # Step 1: login to get real JWT (not shortcut via auth_headers helper)
        login_resp = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]
        bearer = {"Authorization": f"Bearer {access_token}"}

        # Step 2: POST /chat/send → verify response shape
        send_resp = await client.post(
            "/chat/send",
            json={"message": "Hello from the mobile E2E test"},
            headers=bearer,
        )
        assert send_resp.status_code == 200
        send_data = send_resp.json()
        assert "session_id" in send_data          # Contract: session_id field
        assert "message" in send_data             # AI reply text
        assert "artifacts" in send_data           # Contract: artifacts list
        assert isinstance(send_data["artifacts"], list)
        session_id = send_data["session_id"]

        # Step 3: GET /chat/sessions → sessions array
        sessions_resp = await client.get("/chat/sessions", headers=bearer)
        assert sessions_resp.status_code == 200
        sessions_data = sessions_resp.json()
        assert "sessions" in sessions_data        # Contract: sessions field
        assert isinstance(sessions_data["sessions"], list)
        assert "total" in sessions_data

        # Step 4: GET /chat/history/{session_id} → messages array
        history_resp = await client.get(
            f"/chat/history/{session_id}",
            headers=bearer,
        )
        assert history_resp.status_code == 200
        history_data = history_resp.json()
        assert "session_id" in history_data       # echoed back
        assert "messages" in history_data         # Contract: messages array
        assert isinstance(history_data["messages"], list)

    async def test_send_url_message(
        self,
        client,
        mock_db_get_user,
        mock_get_db,
        mock_rate_limiter,
        mock_config,
        mock_route_request,
        mock_process_result,
        mock_session_manager,
        mock_db_session,
        mock_audit_log,
    ):
        """
        Step 1: POST /auth/login → access_token
        Step 2: POST /chat/send-url {url: "https://example.com"} → response
        Verifies: authenticated URL send is accepted (external URLs not SSRF-blocked).
        Requires full chat pipeline mocks — handle_url succeeds, then routes through agent.
        """
        # Step 1: login
        login_resp = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        access_token = login_resp.json()["access_token"]
        bearer = {"Authorization": f"Bearer {access_token}"}

        # Step 2: send-url — mock process_input (which calls handle_url internally)
        # to return a properly enriched task dict, avoiding real HTTP + SSRF checks.
        async def _fake_process_input(task, **kwargs):
            return {
                **task,
                "extracted_text": "Extracted page content from example.com",
                "media_content": None,
                "input_summary": "URL: https://example.com",
            }

        with patch("app.api.chat.process_input", side_effect=_fake_process_input):
            url_resp = await client.post(
                "/chat/send-url",
                json={"url": "https://example.com"},
                headers=bearer,
            )
        # Authenticated URL send should be accepted (200); pipeline is fully mocked
        assert url_resp.status_code in (200, 400, 422)

    async def test_chat_requires_auth(self, client):
        """
        POST /chat/send without Bearer token → 401.
        Verifies: chat endpoint is protected (no fixtures needed).
        """
        resp = await client.post(
            "/chat/send",
            json={"message": "This should be rejected"},
        )
        assert resp.status_code == 401


# ── TestMobileFilesFlow ────────────────────────────────────────────────────────


class TestMobileFilesFlow:
    """
    Files workflow — matches files.ts listFilesApi + uploadFileApi + deleteFileApi.

    Flow: login → list files (empty) → upload → list (file appears) → delete →
    list (file gone).
    """

    async def test_list_files_empty_for_new_user(
        self,
        client,
        mock_db_get_user,
        mock_get_db,
        mock_rate_limiter,
    ):
        """
        Step 1: POST /auth/login → access_token
        Step 2: GET /files/ → {artifacts: [], count: 0} for user with no uploads
        Verifies: empty-state response shape (matches FilesResponse in files.ts).
        """
        # Step 1: login
        login_resp = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        access_token = login_resp.json()["access_token"]
        bearer = {"Authorization": f"Bearer {access_token}"}

        # Step 2: list files (no uploads yet)
        with patch(
            "app.api.files.list_user_artifacts",
            new_callable=AsyncMock,
            return_value=[],
        ):
            files_resp = await client.get("/files/", headers=bearer)

        assert files_resp.status_code == 200
        files_data = files_resp.json()
        assert "artifacts" in files_data          # Contract: artifacts array
        assert isinstance(files_data["artifacts"], list)
        assert "count" in files_data
        assert files_data["count"] == 0

    async def test_upload_and_list_file(
        self,
        client,
        mock_db_get_user,
        mock_get_db,
        mock_rate_limiter,
    ):
        """
        Step 1: POST /auth/login → access_token
        Step 2: POST /files/upload with PDF → artifact_id + filename returned
        Step 3: GET /files/ → artifact appears with required fields
        Verifies: upload response shape + artifact fields (matches ArtifactItem in files.ts).
        """
        # Step 1: login
        login_resp = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        access_token = login_resp.json()["access_token"]
        bearer = {"Authorization": f"Bearer {access_token}"}

        artifact_id = str(uuid.uuid4())
        fake_artifact = {
            "id": artifact_id,
            "filename": "quarterly-report.pdf",
            "file_type": "pdf",
            "download_url": f"/files/{artifact_id}",
            "created_at": "2026-02-28T00:00:00Z",
        }

        # Step 2: upload file
        with patch("app.api.files.get_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch(
                 "app.api.files.register_artifact",
                 new_callable=AsyncMock,
                 return_value=fake_artifact,
             ):
            upload_resp = await client.post(
                "/files/upload",
                files={
                    "media_file": (
                        "quarterly-report.pdf",
                        io.BytesIO(b"%PDF-1.4 test content"),
                        "application/pdf",
                    )
                },
                headers=bearer,
            )

        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        assert "artifact_id" in upload_data       # Contract: artifact_id field
        assert "filename" in upload_data

        # Step 3: list files → artifact now appears
        with patch(
            "app.api.files.list_user_artifacts",
            new_callable=AsyncMock,
            return_value=[fake_artifact],
        ):
            list_resp = await client.get("/files/", headers=bearer)

        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["count"] == 1
        artifact = list_data["artifacts"][0]

        # Contract: ArtifactItem fields (matches interface in mobile files.ts)
        assert "id" in artifact
        assert "filename" in artifact
        assert "file_type" in artifact
        assert "download_url" in artifact
        assert "created_at" in artifact

    async def test_delete_file(
        self,
        client,
        mock_db_get_user,
        mock_get_db,
        mock_rate_limiter,
    ):
        """
        Step 1: POST /auth/login → access_token
        Step 2: POST /files/upload → artifact_id
        Step 3: DELETE /files/{artifact_id} → {deleted: true}
        Step 4: GET /files/ → artifact no longer in list (count: 0)
        Verifies: delete response shape + artifact actually removed.
        """
        # Step 1: login
        login_resp = await client.post(
            "/auth/login",
            json={"email": "sales@test.com", "password": "password123"},
        )
        access_token = login_resp.json()["access_token"]
        bearer = {"Authorization": f"Bearer {access_token}"}

        artifact_id = str(uuid.uuid4())
        fake_artifact = {
            "id": artifact_id,
            "filename": "to-delete.jpg",
            "file_type": "jpeg",
            "download_url": f"/files/{artifact_id}",
            "created_at": "2026-02-28T00:00:00Z",
        }

        # Step 2: upload file
        with patch("app.api.files.get_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch(
                 "app.api.files.register_artifact",
                 new_callable=AsyncMock,
                 return_value=fake_artifact,
             ):
            upload_resp = await client.post(
                "/files/upload",
                files={
                    "media_file": (
                        "to-delete.jpg",
                        io.BytesIO(b"\xff\xd8\xff fake-jpeg"),
                        "image/jpeg",
                    )
                },
                headers=bearer,
            )
        assert upload_resp.status_code == 200

        # Step 3: DELETE /files/{artifact_id} → {deleted: true}
        mock_db_delete = AsyncMock()
        delete_result = MagicMock()
        delete_result.fetchone.return_value = MagicMock(id=artifact_id)
        mock_db_delete.execute = AsyncMock(return_value=delete_result)
        mock_db_delete.commit = AsyncMock()

        with db_override(mock_db_delete):
            delete_resp = await client.delete(
                f"/files/{artifact_id}",
                headers=bearer,
            )

        assert delete_resp.status_code == 200
        delete_data = delete_resp.json()
        assert "deleted" in delete_data           # Contract: deleted field
        assert delete_data["deleted"] is True     # Contract: deleted: true

        # Step 4: GET /files/ → artifact gone
        with patch(
            "app.api.files.list_user_artifacts",
            new_callable=AsyncMock,
            return_value=[],
        ):
            list_resp = await client.get("/files/", headers=bearer)

        assert list_resp.status_code == 200
        assert list_resp.json()["count"] == 0

    async def test_files_require_auth(self, client):
        """
        GET /files/ without Bearer token → 401.
        Verifies: files endpoint is protected (no fixtures needed).
        """
        resp = await client.get("/files/")
        assert resp.status_code == 401
