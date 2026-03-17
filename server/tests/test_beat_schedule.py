"""
Unit tests for DatabaseScheduler dynamic DB reload logic.

Covers:
  1. _reload_db_jobs() adds new DB jobs to self.schedule
  2. _reload_db_jobs() removes jobs deleted/deactivated from DB
  3. tick() triggers reload when _DB_RELOAD_INTERVAL has elapsed
  4. tick() does NOT call load_db_jobs when interval has not elapsed
  5. _reload_db_jobs() is a no-op (no sync) when DB jobs are unchanged
"""

import time
from unittest.mock import MagicMock, patch, call

import pytest

from app.tasks.beat_schedule import DatabaseScheduler

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_scheduler():
    """
    Return a DatabaseScheduler instance with all Celery internals stubbed out.
    We skip setup_schedule() entirely so tests control self.schedule directly.
    """
    scheduler = DatabaseScheduler.__new__(DatabaseScheduler)

    # Minimal stubs required by PersistentScheduler internals
    scheduler.app = MagicMock()
    scheduler.app.conf.beat_schedule = {}
    scheduler._last_db_reload = 0.0

    # PersistentScheduler.schedule is a property: getter returns _store['entries']
    # Initialize _store directly so schedule reads/writes work without a real shelve file
    scheduler._store = {"entries": {}}

    # Stub persistence methods
    scheduler.sync = MagicMock()
    scheduler.update_from_dict = MagicMock()

    return scheduler


def _make_beat_entry(job_id: str) -> dict:
    """Minimal Celery Beat entry dict for a DB job."""
    from celery.schedules import crontab
    return {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=1, minute=0),
        "args": [{"agent": "sales", "message": "test", "_job_id": job_id}],
    }


# ── 1. _reload_db_jobs adds new jobs ──────────────────────────────────────────

class TestReloadDbJobsAddsNewJobs:
    def test_new_job_added_to_schedule(self):
        scheduler = _make_scheduler()
        new_entry = _make_beat_entry("abc-123")

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            return_value={"db-job-abc-123": new_entry},
        ):
            scheduler._reload_db_jobs()

        scheduler.update_from_dict.assert_called_once_with(
            {"db-job-abc-123": new_entry}
        )

    def test_new_job_triggers_sync(self):
        scheduler = _make_scheduler()
        new_entry = _make_beat_entry("abc-123")

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            return_value={"db-job-abc-123": new_entry},
        ):
            scheduler._reload_db_jobs()

        scheduler.sync.assert_called_once()

    def test_multiple_new_jobs_all_added(self):
        scheduler = _make_scheduler()
        entries = {
            "db-job-1": _make_beat_entry("1"),
            "db-job-2": _make_beat_entry("2"),
        }

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            return_value=entries,
        ):
            scheduler._reload_db_jobs()

        called_dict = scheduler.update_from_dict.call_args[0][0]
        assert set(called_dict.keys()) == {"db-job-1", "db-job-2"}


# ── 2. _reload_db_jobs removes deleted/inactive jobs ─────────────────────────

class TestReloadDbJobsRemovesJobs:
    def test_removed_job_deleted_from_schedule(self):
        scheduler = _make_scheduler()
        # Simulate a job that was in the schedule but is now gone from DB
        scheduler.schedule["db-job-old-999"] = MagicMock()
        scheduler.app.conf.beat_schedule["db-job-old-999"] = MagicMock()

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            return_value={},  # DB returns no active jobs
        ):
            scheduler._reload_db_jobs()

        assert "db-job-old-999" not in scheduler.schedule
        assert "db-job-old-999" not in scheduler.app.conf.beat_schedule

    def test_removed_job_triggers_sync(self):
        scheduler = _make_scheduler()
        scheduler.schedule["db-job-old-999"] = MagicMock()
        scheduler.app.conf.beat_schedule["db-job-old-999"] = MagicMock()

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            return_value={},
        ):
            scheduler._reload_db_jobs()

        scheduler.sync.assert_called_once()

    def test_static_jobs_not_removed(self):
        """Static jobs (no 'db-job-' prefix) must never be touched."""
        scheduler = _make_scheduler()
        scheduler.schedule["system-health-check"] = MagicMock()
        scheduler.app.conf.beat_schedule["system-health-check"] = MagicMock()

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            return_value={},
        ):
            scheduler._reload_db_jobs()

        # Static job should still be present
        assert "system-health-check" in scheduler.schedule


# ── 3. tick() triggers reload when interval has elapsed ──────────────────────

class TestTickTriggersReload:
    def test_tick_calls_reload_when_interval_elapsed(self):
        scheduler = _make_scheduler()
        # Set last reload far in the past
        scheduler._last_db_reload = time.monotonic() - 120

        with patch.object(scheduler, "_reload_db_jobs") as mock_reload, \
             patch(
                 "app.tasks.beat_schedule.PersistentScheduler.tick",
                 return_value=1.0,
             ):
            scheduler.tick()

        mock_reload.assert_called_once()

    def test_tick_updates_last_db_reload_timestamp(self):
        scheduler = _make_scheduler()
        scheduler._last_db_reload = time.monotonic() - 120
        before = time.monotonic()

        with patch.object(scheduler, "_reload_db_jobs"), \
             patch(
                 "app.tasks.beat_schedule.PersistentScheduler.tick",
                 return_value=1.0,
             ):
            scheduler.tick()

        assert scheduler._last_db_reload >= before


# ── 4. tick() does NOT reload when interval has not elapsed ──────────────────

class TestTickSkipsReloadWhenIntervalNotElapsed:
    def test_tick_does_not_reload_within_interval(self):
        scheduler = _make_scheduler()
        # Set last reload to just now — interval not elapsed
        scheduler._last_db_reload = time.monotonic()

        with patch.object(scheduler, "_reload_db_jobs") as mock_reload, \
             patch(
                 "app.tasks.beat_schedule.PersistentScheduler.tick",
                 return_value=1.0,
             ):
            scheduler.tick()

        mock_reload.assert_not_called()


# ── 5. _reload_db_jobs is a no-op when nothing changed ───────────────────────

class TestReloadDbJobsNoOp:
    def test_no_sync_when_db_unchanged(self):
        scheduler = _make_scheduler()
        # Existing job already in schedule
        scheduler.schedule["db-job-existing"] = MagicMock()

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            return_value={"db-job-existing": _make_beat_entry("existing")},
        ):
            scheduler._reload_db_jobs()

        # No adds, no removes → sync must NOT be called
        scheduler.sync.assert_not_called()
        scheduler.update_from_dict.assert_not_called()

    def test_no_op_when_no_db_jobs_and_schedule_is_empty(self):
        scheduler = _make_scheduler()

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            return_value={},
        ):
            scheduler._reload_db_jobs()

        scheduler.sync.assert_not_called()
        scheduler.update_from_dict.assert_not_called()


# ── 6. _reload_db_jobs handles DB errors gracefully ──────────────────────────

class TestReloadDbJobsErrorHandling:
    def test_exception_does_not_propagate(self):
        scheduler = _make_scheduler()

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            side_effect=Exception("DB connection lost"),
        ):
            # Must not raise — Beat process must continue running
            scheduler._reload_db_jobs()

    def test_exception_does_not_call_sync(self):
        scheduler = _make_scheduler()

        with patch(
            "app.tasks.beat_schedule.load_db_jobs",
            side_effect=Exception("DB connection lost"),
        ):
            scheduler._reload_db_jobs()

        scheduler.sync.assert_not_called()
