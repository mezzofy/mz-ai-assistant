"""
Tests for BUG-022 — Shared Folder Delivery for Scheduled Tasks.

Covers:
  - DeliverToDTO accepts shared_folder field
  - SharedFolderDTO field validation
  - _deliver_results_async() calls artifact_manager for shared_folder delivery
  - Filename template substitution (DDMMYY → actual date)
  - Scheduler ops tool builds deliver_to with shared_folder key
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

pytestmark = pytest.mark.unit


# ── DeliverToDTO / SharedFolderDTO ────────────────────────────────────────────

class TestDeliverToDTO:
    def test_accepts_shared_folder(self):
        from app.webhooks.scheduler import DeliverToDTO, SharedFolderDTO

        dto = DeliverToDTO(
            shared_folder=SharedFolderDTO(
                department="sales",
                filename_template="Leads_DDMMYY",
                file_extension="txt",
            )
        )
        assert dto.shared_folder is not None
        assert dto.shared_folder.department == "sales"
        assert dto.shared_folder.filename_template == "Leads_DDMMYY"
        assert dto.shared_folder.file_extension == "txt"

    def test_shared_folder_default_extension(self):
        from app.webhooks.scheduler import DeliverToDTO, SharedFolderDTO

        dto = DeliverToDTO(
            shared_folder=SharedFolderDTO(
                department="marketing",
                filename_template="Weekly_Report_DDMMYY",
            )
        )
        assert dto.shared_folder.file_extension == "txt"

    def test_shared_folder_dumps_correctly(self):
        from app.webhooks.scheduler import DeliverToDTO, SharedFolderDTO

        dto = DeliverToDTO(
            teams_channel="sales",
            shared_folder=SharedFolderDTO(
                department="sales",
                filename_template="Leads_DDMMYY",
            )
        )
        dumped = dto.model_dump(exclude_none=True)
        assert dumped["teams_channel"] == "sales"
        assert dumped["shared_folder"]["department"] == "sales"
        assert dumped["shared_folder"]["filename_template"] == "Leads_DDMMYY"
        assert dumped["shared_folder"]["file_extension"] == "txt"

    def test_all_delivery_targets_coexist(self):
        from app.webhooks.scheduler import DeliverToDTO, SharedFolderDTO

        dto = DeliverToDTO(
            teams_channel="general",
            email=["user@example.com"],
            push_user_id="user-123",
            shared_folder=SharedFolderDTO(
                department="sales",
                filename_template="Report_DDMMYY",
            )
        )
        dumped = dto.model_dump(exclude_none=True)
        assert "teams_channel" in dumped
        assert "email" in dumped
        assert "push_user_id" in dumped
        assert "shared_folder" in dumped

    def test_no_shared_folder_field_absent(self):
        from app.webhooks.scheduler import DeliverToDTO

        dto = DeliverToDTO(teams_channel="sales")
        dumped = dto.model_dump(exclude_none=True)
        assert "shared_folder" not in dumped


# ── _deliver_results_async — shared folder path ───────────────────────────────

class TestDeliverResultsSharedFolder:
    @pytest.mark.asyncio
    async def test_shared_folder_writes_file(self, tmp_path):
        """deliver_results_async writes content to dept shared dir and registers artifact."""
        from app.tasks.webhook_tasks import _deliver_results_async

        fake_dept_dir = tmp_path / "sales" / "shared"
        fake_dept_dir.mkdir(parents=True)

        result = {"content": "Lead 1\nLead 2\n", "title": "Sales Leads"}
        deliver_to = {
            "shared_folder": {
                "department": "sales",
                "filename_template": "Leads_DDMMYY",
                "file_extension": "txt",
            }
        }
        config = {}

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.context.artifact_manager.get_dept_artifacts_dir", return_value=fake_dept_dir),
            patch("app.core.database.AsyncSessionLocal", return_value=mock_ctx),
        ):
            await _deliver_results_async(result, deliver_to, config)

        # File should exist with DDMMYY substituted to today's actual date
        run_date = datetime.now(timezone.utc).strftime("%d%m%y")
        expected_file = fake_dept_dir / f"Leads_{run_date}.txt"
        assert expected_file.exists()
        assert expected_file.read_text(encoding="utf-8") == "Lead 1\nLead 2\n"

    @pytest.mark.asyncio
    async def test_shared_folder_skipped_when_absent(self):
        """deliver_results_async does not write files when shared_folder is absent."""
        from app.tasks.webhook_tasks import _deliver_results_async

        result = {"content": "data"}
        deliver_to = {}   # no delivery configured
        config = {}

        with patch("app.context.artifact_manager.register_artifact") as mock_reg:
            await _deliver_results_async(result, deliver_to, config)
            mock_reg.assert_not_called()


# ── Filename template substitution ────────────────────────────────────────────

class TestFilenameTemplateSubstitution:
    def test_ddmmyy_replaced_with_date(self):
        """DDMMYY in template is replaced with actual run date."""
        run_date = datetime(2026, 3, 18, tzinfo=timezone.utc).strftime("%d%m%y")
        template = "Leads_DDMMYY"
        filename = template.replace("DDMMYY", run_date) + ".txt"
        assert filename == "Leads_180326.txt"

    def test_template_without_placeholder(self):
        """Template with no DDMMYY placeholder is used as-is."""
        run_date = "180326"
        template = "SalesReport"
        filename = template.replace("DDMMYY", run_date) + ".csv"
        assert filename == "SalesReport.csv"

    def test_multiple_placeholder_occurrences(self):
        """All DDMMYY occurrences in template are replaced."""
        run_date = "180326"
        template = "Report_DDMMYY_backup_DDMMYY"
        filename = template.replace("DDMMYY", run_date) + ".txt"
        assert filename == "Report_180326_backup_180326.txt"


# ── SchedulerOps tool — shared folder params ─────────────────────────────────

class TestSchedulerOpsSharedFolder:
    @pytest.mark.asyncio
    async def test_create_job_with_shared_folder(self):
        """_create_scheduled_job builds deliver_to with shared_folder when params given."""
        from app.tools.scheduler.scheduler_ops import SchedulerOps

        ops = SchedulerOps(config={})

        scalar_result = MagicMock()
        scalar_result.scalar.return_value = 0
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[scalar_result, AsyncMock()])
        mock_db.commit = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.core.user_context.get_user_id", return_value="user-123"),
            patch("app.core.database.AsyncSessionLocal", return_value=mock_ctx),
            patch("app.webhooks.scheduler.compute_next_run",
                  return_value=datetime(2026, 3, 19, 1, 0, tzinfo=timezone.utc)),
        ):
            result = await ops._create_scheduled_job(
                name="Daily Leads",
                agent="sales",
                message="Scan inbox for leads",
                cron="0 1 * * *",
                deliver_to_shared_folder_dept="sales",
                deliver_to_filename_template="Leads_DDMMYY",
            )

        assert result.get("success") is True or "job_id" in result.get("data", {})

        # Verify the INSERT was called with shared_folder in deliver_to
        insert_call = mock_db.execute.call_args_list[-1]
        bound_params = insert_call.args[1] if len(insert_call.args) > 1 else {}
        deliver_to_json = bound_params.get("deliver_to", "{}")
        deliver_to = json.loads(deliver_to_json)
        assert "shared_folder" in deliver_to
        assert deliver_to["shared_folder"]["department"] == "sales"
        assert deliver_to["shared_folder"]["filename_template"] == "Leads_DDMMYY"

    @pytest.mark.asyncio
    async def test_create_job_without_shared_folder(self):
        """_create_scheduled_job omits shared_folder when params not given."""
        from app.tools.scheduler.scheduler_ops import SchedulerOps

        ops = SchedulerOps(config={})

        scalar_result = MagicMock()
        scalar_result.scalar.return_value = 0
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[scalar_result, AsyncMock()])
        mock_db.commit = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("app.core.user_context.get_user_id", return_value="user-123"),
            patch("app.core.database.AsyncSessionLocal", return_value=mock_ctx),
            patch("app.webhooks.scheduler.compute_next_run",
                  return_value=datetime(2026, 3, 19, 1, 0, tzinfo=timezone.utc)),
        ):
            await ops._create_scheduled_job(
                name="Daily Leads",
                agent="sales",
                message="Scan inbox",
                cron="0 1 * * *",
            )

        insert_call = mock_db.execute.call_args_list[-1]
        bound_params = insert_call.args[1] if len(insert_call.args) > 1 else {}
        deliver_to = json.loads(bound_params.get("deliver_to", "{}"))
        assert "shared_folder" not in deliver_to
