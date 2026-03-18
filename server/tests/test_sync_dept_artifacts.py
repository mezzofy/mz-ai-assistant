"""
Tests for sync_dept_artifacts() and its integration with GET /files/?scope=department.

Tests cover:
  - Disk files not in DB → registered after GET /files/?scope=department
  - Files already in DB → not double-registered
  - .md files → skipped (system marker files)
  - Non-allowed extensions → skipped
  - Management user with ?dept=sales → syncs sales shared dir
  - Non-management user → syncs their own dept's shared dir
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from tests.conftest import USERS, auth_headers, db_override

pytestmark = pytest.mark.unit


# ── Unit tests for sync_dept_artifacts() ──────────────────────────────────────

class TestSyncDeptArtifacts:
    """Direct unit tests for the sync_dept_artifacts() helper."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def test_registers_new_allowed_file(self, mock_db, tmp_path):
        """A .txt file on disk not in DB gets registered."""
        dept_dir = tmp_path / "sales" / "shared"
        dept_dir.mkdir(parents=True)
        (dept_dir / "Leads_160326.txt").write_text("lead data")

        # DB returns no registered files
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        with patch("app.context.artifact_manager.get_dept_artifacts_dir", return_value=dept_dir), \
             patch("app.context.artifact_manager.register_artifact", new_callable=AsyncMock) as mock_reg:
            from app.context.artifact_manager import sync_dept_artifacts
            count = await sync_dept_artifacts(mock_db, "user-123", "sales")

        assert count == 1
        mock_reg.assert_called_once()
        call_kwargs = mock_reg.call_args.kwargs
        assert call_kwargs["filename"] == "Leads_160326.txt"
        assert call_kwargs["scope"] == "department"
        assert call_kwargs["department"] == "sales"
        assert call_kwargs["file_type"] == "txt"
        mock_db.commit.assert_called_once()

    async def test_does_not_double_register_existing_file(self, mock_db, tmp_path):
        """File already in DB → not registered again."""
        dept_dir = tmp_path / "sales" / "shared"
        dept_dir.mkdir(parents=True)
        (dept_dir / "Leads_160326.txt").write_text("lead data")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("Leads_160326.txt",)]
        mock_db.execute.return_value = mock_result

        with patch("app.context.artifact_manager.get_dept_artifacts_dir", return_value=dept_dir), \
             patch("app.context.artifact_manager.register_artifact", new_callable=AsyncMock) as mock_reg:
            from app.context.artifact_manager import sync_dept_artifacts
            count = await sync_dept_artifacts(mock_db, "user-123", "sales")

        assert count == 0
        mock_reg.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_skips_md_files(self, mock_db, tmp_path):
        """.md files are system marker files — must be skipped."""
        dept_dir = tmp_path / "sales" / "shared"
        dept_dir.mkdir(parents=True)
        (dept_dir / "notes.md").write_text("agent notes")
        (dept_dir / "Leads.txt").write_text("leads")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        with patch("app.context.artifact_manager.get_dept_artifacts_dir", return_value=dept_dir), \
             patch("app.context.artifact_manager.register_artifact", new_callable=AsyncMock) as mock_reg:
            from app.context.artifact_manager import sync_dept_artifacts
            count = await sync_dept_artifacts(mock_db, "user-123", "sales")

        assert count == 1
        filenames = [c.kwargs["filename"] for c in mock_reg.call_args_list]
        assert "notes.md" not in filenames
        assert "Leads.txt" in filenames

    async def test_skips_non_allowed_extensions(self, mock_db, tmp_path):
        """Files with unknown extensions (e.g., .exe, .sh) must be skipped."""
        dept_dir = tmp_path / "sales" / "shared"
        dept_dir.mkdir(parents=True)
        (dept_dir / "script.sh").write_text("#!/bin/bash")
        (dept_dir / "report.pdf").write_bytes(b"%PDF-1.4")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        with patch("app.context.artifact_manager.get_dept_artifacts_dir", return_value=dept_dir), \
             patch("app.context.artifact_manager.register_artifact", new_callable=AsyncMock) as mock_reg:
            from app.context.artifact_manager import sync_dept_artifacts
            count = await sync_dept_artifacts(mock_db, "user-123", "sales")

        assert count == 1
        filenames = [c.kwargs["filename"] for c in mock_reg.call_args_list]
        assert "script.sh" not in filenames
        assert "report.pdf" in filenames

    async def test_returns_zero_when_dir_missing(self, mock_db, tmp_path):
        """Non-existent dept dir → returns 0, no DB queries."""
        nonexistent = tmp_path / "ghost" / "shared"

        with patch("app.context.artifact_manager.get_dept_artifacts_dir", return_value=nonexistent):
            from app.context.artifact_manager import sync_dept_artifacts
            count = await sync_dept_artifacts(mock_db, "user-123", "ghost")

        assert count == 0
        mock_db.execute.assert_not_called()

    async def test_registers_multiple_allowed_files(self, mock_db, tmp_path):
        """Multiple new files on disk → all registered in one commit."""
        dept_dir = tmp_path / "finance" / "shared"
        dept_dir.mkdir(parents=True)
        (dept_dir / "Q1.xlsx").write_bytes(b"xlsx-data")
        (dept_dir / "Budget.csv").write_text("col1,col2")
        (dept_dir / "Presentation.pptx").write_bytes(b"pptx-data")

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        with patch("app.context.artifact_manager.get_dept_artifacts_dir", return_value=dept_dir), \
             patch("app.context.artifact_manager.register_artifact", new_callable=AsyncMock) as mock_reg:
            from app.context.artifact_manager import sync_dept_artifacts
            count = await sync_dept_artifacts(mock_db, "user-456", "finance")

        assert count == 3
        assert mock_reg.call_count == 3
        mock_db.commit.assert_called_once()


# ── Integration tests via GET /files/?scope=department ────────────────────────

class TestListFilesDepartmentSync:
    """Tests for sync_dept_artifacts trigger in GET /files/?scope=department."""

    async def test_department_scope_triggers_dept_sync(self, client, mock_get_db):
        """GET /files/?scope=department calls sync_dept_artifacts (not sync_user_artifacts)."""
        with patch("app.api.files.sync_dept_artifacts", new_callable=AsyncMock) as mock_dept_sync, \
             patch("app.api.files.sync_user_artifacts", new_callable=AsyncMock) as mock_user_sync, \
             patch("app.api.files.list_artifacts", new_callable=AsyncMock, return_value=[]):
            response = await client.get(
                "/files/?scope=department",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        mock_dept_sync.assert_called_once()
        mock_user_sync.assert_not_called()

    async def test_personal_scope_triggers_user_sync_not_dept_sync(self, client, mock_get_db):
        """GET /files/?scope=personal calls sync_user_artifacts, not sync_dept_artifacts."""
        with patch("app.api.files.sync_dept_artifacts", new_callable=AsyncMock) as mock_dept_sync, \
             patch("app.api.files.sync_user_artifacts", new_callable=AsyncMock) as mock_user_sync, \
             patch("app.api.files.list_artifacts", new_callable=AsyncMock, return_value=[]):
            response = await client.get(
                "/files/",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        mock_user_sync.assert_called_once()
        mock_dept_sync.assert_not_called()

    async def test_management_user_dept_param_syncs_target_dept(self, client, mock_get_db):
        """Management user with ?dept=sales → sync_dept_artifacts called with 'sales'."""
        with patch("app.api.files.sync_dept_artifacts", new_callable=AsyncMock) as mock_dept_sync, \
             patch("app.api.files.list_artifacts", new_callable=AsyncMock, return_value=[]):
            response = await client.get(
                "/files/?scope=department&dept=sales",
                headers=auth_headers("admin"),
            )

        assert response.status_code == 200
        mock_dept_sync.assert_called_once()
        # Third positional arg (or kwarg dept) should be 'sales'
        args, kwargs = mock_dept_sync.call_args
        effective_dept = kwargs.get("dept") or args[2]
        assert effective_dept == "sales"

    async def test_non_management_dept_param_ignored_syncs_own_dept(self, client, mock_get_db):
        """Non-management user: ?dept= param is silently ignored, syncs their own dept."""
        with patch("app.api.files.sync_dept_artifacts", new_callable=AsyncMock) as mock_dept_sync, \
             patch("app.api.files.list_artifacts", new_callable=AsyncMock, return_value=[]):
            response = await client.get(
                "/files/?scope=department&dept=management",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        mock_dept_sync.assert_called_once()
        args, kwargs = mock_dept_sync.call_args
        effective_dept = kwargs.get("dept") or args[2]
        # sales_rep's own dept is 'sales', not 'management'
        assert effective_dept == "sales"

    async def test_department_scope_with_folder_id_skips_sync(self, client, mock_get_db):
        """folder_id present → no sync (browsing inside a folder)."""
        folder_id = str(uuid.uuid4())
        with patch("app.api.files.sync_dept_artifacts", new_callable=AsyncMock) as mock_dept_sync, \
             patch("app.api.files.list_artifacts", new_callable=AsyncMock, return_value=[]):
            response = await client.get(
                f"/files/?scope=department&folder_id={folder_id}",
                headers=auth_headers("sales_rep"),
            )

        assert response.status_code == 200
        mock_dept_sync.assert_not_called()

    async def test_department_files_returned_after_sync(self, client, mock_get_db):
        """After sync, listed artifacts are returned in response."""
        artifacts = [
            {"id": str(uuid.uuid4()), "filename": "Leads_160326.txt", "file_type": "txt", "scope": "department"},
        ]
        with patch("app.api.files.sync_dept_artifacts", new_callable=AsyncMock), \
             patch("app.api.files.list_artifacts", new_callable=AsyncMock, return_value=artifacts):
            response = await client.get(
                "/files/?scope=department",
                headers=auth_headers("sales_manager"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["artifacts"][0]["filename"] == "Leads_160326.txt"
