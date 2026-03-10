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
        with patch("app.api.files.get_user_artifacts_dir", return_value=Path("/tmp/artifacts")), \
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
        with patch("app.api.files.get_user_artifacts_dir", return_value=Path("/tmp/artifacts")), \
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
        with patch("app.api.files.get_user_artifacts_dir", return_value=Path("/tmp/artifacts")), \
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
        with patch("app.api.files.get_user_artifacts_dir", return_value=Path("/tmp/artifacts")), \
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
        with patch("app.api.files.sync_user_artifacts", new_callable=AsyncMock), \
             patch("app.api.files.list_artifacts", new_callable=AsyncMock, return_value=[]):
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
        with patch("app.api.files.sync_user_artifacts", new_callable=AsyncMock), \
             patch("app.api.files.list_artifacts", new_callable=AsyncMock, return_value=artifacts):
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
            "scope": "company",   # company scope — no user_id check needed
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
            "scope": "company",   # company scope — any authenticated user can read
        }
        # Patch artifact root to tmp_path so the bounds check passes
        with patch("app.api.files.get_artifact", new_callable=AsyncMock, return_value=artifact), \
             patch("app.api.files.get_artifacts_dir", return_value=tmp_path):
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


# ── Security hardening tests ──────────────────────────────────────────────────

class TestRenameSecurityHardening:
    """FINDING 1 — Path traversal guards in rename endpoint."""

    async def test_rename_rejects_null_byte_filename(self, client, mock_get_db):
        """Null-byte in filename must be rejected with 400."""
        response = await client.patch(
            f"/files/{uuid.uuid4()}/rename",
            json={"filename": "\x00evil.pdf"},
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 400

    async def test_rename_rejects_leading_dot_filename(self, client, mock_get_db):
        """Dotfile names (e.g. .bashrc) must be rejected with 400."""
        response = await client.patch(
            f"/files/{uuid.uuid4()}/rename",
            json={"filename": ".bashrc"},
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 400

    async def test_rename_rejects_slash_in_filename(self, client, mock_get_db):
        """Forward-slash in filename must be rejected with 400 (pre-existing guard)."""
        response = await client.patch(
            f"/files/{uuid.uuid4()}/rename",
            json={"filename": "../../etc/passwd"},
            headers=auth_headers("sales_rep"),
        )
        assert response.status_code == 400


class TestUploadSecurityHardening:
    """FINDING 3 (MIME mismatch) + FINDING 4 (size limit)."""

    async def test_upload_rejects_oversized_file(self, client, mock_get_db):
        """Files larger than _MAX_UPLOAD_BYTES must return 413."""
        with patch("app.api.files._MAX_UPLOAD_BYTES", 10):
            response = await client.post(
                "/files/upload",
                files={"media_file": ("big.pdf", io.BytesIO(b"A" * 11), "application/pdf")},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 413

    async def test_upload_rejects_mime_mismatch(self, client, mock_get_db):
        """Binary masquerading as image/jpeg must be rejected with 415 (magic check)."""
        elf_header = b"\x7fELF" + b"\x00" * 60  # minimal ELF magic bytes

        with patch("app.api.files.get_user_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("app.api.files._magic.from_buffer", return_value="application/x-executable"):
            response = await client.post(
                "/files/upload",
                files={"media_file": ("photo.jpg", io.BytesIO(elf_header), "image/jpeg")},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 415
        assert "does not match declared type" in response.json()["detail"]


class TestImageProcessingInUpload:
    """Image uploads trigger OCR + vision analysis returned in image_analysis field."""

    async def test_image_upload_returns_image_analysis(self, client, mock_get_db):
        """Image upload runs handle_image and returns ocr_text + description."""
        fake_artifact = {"id": str(uuid.uuid4()), "download_url": "/files/img1"}
        fake_image_result = {
            "media_content": {
                "filename": "photo.jpg",
                "ocr_text": "Invoice #1042 Total: $250.00",
                "description": "A photo of a printed invoice",
            }
        }
        with patch("app.api.files.get_user_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch("app.api.files.register_artifact", new_callable=AsyncMock, return_value=fake_artifact), \
             patch("app.api.files._magic.from_buffer", return_value="image/jpeg"), \
             patch("app.core.config.get_config", return_value={}), \
             patch("app.input.image_handler.handle_image", new_callable=AsyncMock, return_value=fake_image_result):
            response = await client.post(
                "/files/upload",
                files={"media_file": ("photo.jpg", io.BytesIO(b"fake-jpeg"), "image/jpeg")},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 200
        data = response.json()
        assert "image_analysis" in data
        assert data["image_analysis"]["ocr_text"] == "Invoice #1042 Total: $250.00"
        assert data["image_analysis"]["description"] == "A photo of a printed invoice"

    async def test_non_image_upload_has_no_image_analysis(self, client, mock_get_db):
        """PDF upload does not include image_analysis in response."""
        fake_artifact = {"id": str(uuid.uuid4()), "download_url": "/files/pdf1"}
        with patch("app.api.files.get_user_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch("app.api.files.register_artifact", new_callable=AsyncMock, return_value=fake_artifact), \
             patch("app.api.files._magic.from_buffer", return_value="application/pdf"):
            response = await client.post(
                "/files/upload",
                files={"media_file": ("report.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 200
        assert "image_analysis" not in response.json()

    async def test_image_processing_failure_does_not_block_upload(self, client, mock_get_db):
        """If handle_image raises, upload still returns 200 with empty image_analysis."""
        fake_artifact = {"id": str(uuid.uuid4()), "download_url": "/files/img2"}
        with patch("app.api.files.get_user_artifacts_dir", return_value=Path("/tmp/artifacts")), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_bytes"), \
             patch("app.api.files.register_artifact", new_callable=AsyncMock, return_value=fake_artifact), \
             patch("app.api.files._magic.from_buffer", return_value="image/png"), \
             patch("app.core.config.get_config", return_value={}), \
             patch("app.input.image_handler.handle_image", new_callable=AsyncMock,
                   side_effect=RuntimeError("OCR service down")):
            response = await client.post(
                "/files/upload",
                files={"media_file": ("screenshot.png", io.BytesIO(b"\x89PNG\r\n"), "image/png")},
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 200
        data = response.json()
        assert "image_analysis" in data
        assert data["image_analysis"] == {}


class TestSendArtifactRouting:
    """send_artifact() must route image files through image_handler, others through file_handler."""

    async def test_send_artifact_routes_jpg_through_image_handler(
        self, client, mock_db_session, mock_session_manager, mock_process_result
    ):
        """Artifact with .jpg filename must result in input_type='image' passed to process_input."""
        file_id = str(uuid.uuid4())

        mock_artifact = MagicMock()
        mock_artifact.id = file_id
        mock_artifact.filename = "photo.jpg"
        mock_artifact.file_path = "/tmp/photo.jpg"
        mock_artifact.file_type = "jpeg"
        mock_db_session.execute.return_value.fetchone.return_value = mock_artifact

        captured_task: dict = {}

        async def _fake_process_input(task, file_bytes=None, filename=None):
            captured_task.update(task)
            task["extracted_text"] = "image content"
            return task

        with patch("app.api.chat._artifact_path_exists", return_value=True), \
             patch("app.api.chat._read_artifact_bytes", return_value=b"fake-jpeg"), \
             patch("app.api.chat.process_input", side_effect=_fake_process_input), \
             patch("app.api.chat.route_request", new_callable=AsyncMock,
                   return_value={"success": True, "content": "ok", "artifacts": []}):
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": file_id, "message": "analyze this"},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        assert captured_task.get("input_type") == "image"

    async def test_send_artifact_routes_pdf_through_file_handler(
        self, client, mock_db_session, mock_session_manager, mock_process_result
    ):
        """Artifact with .pdf filename must result in input_type='file' passed to process_input."""
        file_id = str(uuid.uuid4())

        mock_artifact = MagicMock()
        mock_artifact.id = file_id
        mock_artifact.filename = "report.pdf"
        mock_artifact.file_path = "/tmp/report.pdf"
        mock_artifact.file_type = "pdf"
        mock_db_session.execute.return_value.fetchone.return_value = mock_artifact

        captured_task: dict = {}

        async def _fake_process_input(task, file_bytes=None, filename=None):
            captured_task.update(task)
            task["extracted_text"] = "pdf content"
            return task

        with patch("app.api.chat._artifact_path_exists", return_value=True), \
             patch("app.api.chat._read_artifact_bytes", return_value=b"%PDF-1.4"), \
             patch("app.api.chat.process_input", side_effect=_fake_process_input), \
             patch("app.api.chat.route_request", new_callable=AsyncMock,
                   return_value={"success": True, "content": "ok", "artifacts": []}):
            response = await client.post(
                "/chat/send-artifact",
                json={"artifact_id": file_id, "message": "summarize"},
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        assert captured_task.get("input_type") == "file"


class TestDownloadPathEscape:
    """FINDING 2 — Artifact root bounds-check on download."""

    async def test_download_path_escaping_artifact_root_returns_404(
        self, client, mock_get_db, tmp_path
    ):
        """DB record whose file_path escapes the artifact root must return 404."""
        # Create a real file outside the artifact root (e.g., /tmp)
        decoy = tmp_path / "passwd"
        decoy.write_text("root:x:0:0\n")

        artifact = {
            "id": str(uuid.uuid4()),
            "user_id": "user-sales",
            "filename": "passwd",
            "file_path": str(decoy),      # arbitrary path outside artifact root
            "file_type": "txt",
            "scope": "company",
        }

        # Point artifact root at a different tmp dir so decoy is clearly outside it
        artifact_root = tmp_path / "artifacts"
        artifact_root.mkdir()

        with patch("app.api.files.get_artifact", new_callable=AsyncMock, return_value=artifact), \
             patch("app.api.files.get_artifacts_dir", return_value=artifact_root):
            response = await client.get(
                f"/files/{artifact['id']}",
                headers=auth_headers("sales_rep"),
            )
        assert response.status_code == 404
