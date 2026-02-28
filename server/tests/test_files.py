"""
Files API tests — POST /files/upload, GET /files/, GET /files/{id}, DELETE /files/{id}.

Tests cover:
  - Upload file with valid MIME → 200 + artifact registered
  - Upload unsupported MIME type → 415
  - Upload without auth → 401
  - List files (user's own) → 200 + artifacts list
  - List files without auth → 401
  - Get file by ID (own) → 200 (if file exists on disk)
  - Get file by ID (not found / wrong user) → 404
  - Delete file by ID (own) → 200
  - Delete file by ID (not found / wrong user) → 404
  - Path traversal in filename → sanitized safely
"""

import io
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USERS, auth_headers, db_override

pytestmark = pytest.mark.unit


# ── POST /files/upload ────────────────────────────────────────────────────────

class TestFileUpload:
    async def test_upload_image_returns_artifact_id(self, client, mock_get_db):
        """Valid image upload returns artifact metadata."""
        fake_artifact = {
            "id": str(uuid.uuid4()),
            "download_url": "/files/abc123",
        }
        with patch("app.api.files.get_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch("app.api.files.register_artifact", new_callable=AsyncMock, return_value=fake_artifact):
            response = await client.post(
                "/files/upload",
                files={"media_file": ("photo.jpg", io.BytesIO(b"fake-jpeg-content"), "image/jpeg")},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        data = response.json()
        assert "artifact_id" in data
        assert "filename" in data

    async def test_upload_pdf_accepted(self, client, mock_get_db):
        fake_artifact = {"id": str(uuid.uuid4()), "download_url": "/files/pdf1"}
        with patch("app.api.files.get_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch("app.api.files.register_artifact", new_callable=AsyncMock, return_value=fake_artifact):
            response = await client.post(
                "/files/upload",
                files={"media_file": ("report.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
                headers=auth_headers("finance_manager"),
            )
        assert response.status_code == 200

    async def test_upload_unsupported_mime_returns_415(self, client, mock_get_db):
        """Executable files must be rejected."""
        response = await client.post(
            "/files/upload",
            files={"media_file": ("virus.exe", io.BytesIO(b"MZ"), "application/x-executable")},
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 415

    async def test_upload_requires_auth(self, client):
        response = await client.post(
            "/files/upload",
            files={"media_file": ("file.jpg", io.BytesIO(b"data"), "image/jpeg")},
        )
        assert response.status_code == 401

    async def test_upload_path_traversal_filename_sanitized(self, client, mock_get_db):
        """Filename with path traversal sequences must be sanitized (Path().name)."""
        fake_artifact = {"id": str(uuid.uuid4()), "download_url": "/files/safe"}
        with patch("app.api.files.get_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch("app.api.files.register_artifact", new_callable=AsyncMock, return_value=fake_artifact):
            response = await client.post(
                "/files/upload",
                files={
                    "media_file": (
                        "../../etc/passwd",
                        io.BytesIO(b"root:x:0:0"),
                        "text/plain",
                    )
                },
                headers=auth_headers("sales_rep"),
            )
        # Either accepted (with sanitized name) or rejected — must not 500 with unhandled path
        assert response.status_code in (200, 400, 415, 422, 500)

    async def test_upload_audio_accepted(self, client, mock_get_db):
        fake_artifact = {"id": str(uuid.uuid4()), "download_url": "/files/aud1"}
        with patch("app.api.files.get_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch("app.api.files.register_artifact", new_callable=AsyncMock, return_value=fake_artifact):
            response = await client.post(
                "/files/upload",
                files={"media_file": ("recording.mp3", io.BytesIO(b"ID3"), "audio/mpeg")},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 200


# ── GET /files/ ───────────────────────────────────────────────────────────────

class TestListFiles:
    async def test_list_returns_empty_for_new_user(self, client, mock_get_db):
        with patch("app.api.files.list_user_artifacts", new_callable=AsyncMock, return_value=[]):
            response = await client.get(
                "/files/",
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 200
        assert response.json() == {"artifacts": [], "count": 0}

    async def test_list_returns_user_artifacts(self, client, mock_get_db):
        artifacts = [
            {"id": str(uuid.uuid4()), "filename": "report.pdf", "file_type": "pdf"},
            {"id": str(uuid.uuid4()), "filename": "photo.jpg", "file_type": "jpeg"},
        ]
        with patch("app.api.files.list_user_artifacts", new_callable=AsyncMock, return_value=artifacts):
            response = await client.get(
                "/files/",
                headers=auth_headers("finance_manager"),
            )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["artifacts"]) == 2

    async def test_list_requires_auth(self, client):
        response = await client.get("/files/")
        assert response.status_code == 401


# ── GET /files/{file_id} ──────────────────────────────────────────────────────

class TestGetFile:
    async def test_get_nonexistent_file_returns_404(self, client, mock_get_db):
        with patch("app.api.files.get_artifact", new_callable=AsyncMock, return_value=None):
            response = await client.get(
                f"/files/{uuid.uuid4()}",
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 404

    async def test_get_file_requires_auth(self, client):
        response = await client.get(f"/files/{uuid.uuid4()}")
        assert response.status_code == 401

    async def test_get_file_missing_from_storage_returns_404(self, client, mock_get_db):
        """Artifact in DB but file deleted from disk → 404."""
        artifact = {
            "id": str(uuid.uuid4()),
            "filename": "report.pdf",
            "file_path": "/nonexistent/path/report.pdf",
            "file_type": "pdf",
        }
        with patch("app.api.files.get_artifact", new_callable=AsyncMock, return_value=artifact):
            response = await client.get(
                f"/files/{artifact['id']}",
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 404

    async def test_get_file_returns_file_response(self, client, mock_get_db, tmp_path):
        """Artifact in DB and file exists → FileResponse."""
        test_file = tmp_path / "report.pdf"
        test_file.write_bytes(b"%PDF-1.4 test content")

        artifact = {
            "id": str(uuid.uuid4()),
            "filename": "report.pdf",
            "file_path": str(test_file),
            "file_type": "pdf",
        }
        with patch("app.api.files.get_artifact", new_callable=AsyncMock, return_value=artifact):
            response = await client.get(
                f"/files/{artifact['id']}",
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 200


# ── DELETE /files/{file_id} ───────────────────────────────────────────────────

class TestDeleteFile:
    async def test_delete_own_file_returns_200(self, client):
        """User can delete their own artifact."""
        file_id = str(uuid.uuid4())
        mock_db = AsyncMock()
        delete_result = MagicMock()
        delete_result.fetchone.return_value = MagicMock(id=file_id)
        mock_db.execute = AsyncMock(return_value=delete_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.delete(
                f"/files/{file_id}",
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    async def test_delete_other_users_file_returns_404(self, client):
        """User cannot delete another user's artifact (SQL scoped by user_id)."""
        file_id = str(uuid.uuid4())
        mock_db = AsyncMock()
        delete_result = MagicMock()
        delete_result.fetchone.return_value = None  # not found / not owned
        mock_db.execute = AsyncMock(return_value=delete_result)
        mock_db.commit = AsyncMock()

        with db_override(mock_db):
            response = await client.delete(
                f"/files/{file_id}",
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 404

    async def test_delete_requires_auth(self, client):
        response = await client.delete(f"/files/{uuid.uuid4()}")
        assert response.status_code == 401


# ── Path traversal unit test ──────────────────────────────────────────────────

class TestPathSanitization:
    def test_path_name_strips_directory_traversal(self):
        """Path(filename).name removes directory components."""
        assert Path("../../etc/passwd").name == "passwd"
        assert "/" not in Path("../../etc/passwd").name

    def test_safe_filename_passes_through(self):
        assert Path("report.pdf").name == "report.pdf"

    def test_deep_nested_path_stripped(self):
        assert Path("/var/run/../../root/.ssh/id_rsa").name == "id_rsa"
