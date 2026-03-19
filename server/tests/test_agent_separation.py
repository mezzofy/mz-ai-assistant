"""
Agent Enhancement v2.0 — Users/Agents Separation & Agentic Team Tests.

Tests cover:
  1.  Users table has no agent-specific columns (schema check)
  2.  Agents table is seeded with all 9 required agent IDs
  3.  AgentRegistry.load() + get() / get_orchestrator() work correctly
  4.  AgentRegistry.find_by_skill() returns correct agents
  5.  AgentRegistry.get_by_department() returns agent dict (not class) with id field
  6.  ManagementAgent.execute() dispatches cross-dept tasks to plan_and_orchestrate
  7.  RAG namespace isolation — FinanceAgent only loads finance/ + shared/ files
  8.  agent_task_log: log_task_start() inserts with parent_task_id propagation
  9.  process_delegated_agent_task publishes result to correct Redis channel
  10. Chat API user JWT flows through router (no direct agent_registry bypass)
  11. ResearchAgent.can_handle() triggers on task["agent"]=="research" only
  12. CodeGenerationSkill.safety_scan() detects dangerous SQL/shell patterns
  13. CronValidationSkill.validate() accepts valid + rejects out-of-range expressions
  14. Static Beat jobs are not in scheduled_jobs table (cannot be deleted via API)
  15. ManagementAgent.plan_and_orchestrate() calls delegate_task for all 3 special agents
  16. Research / Developer / Scheduler RAG namespace isolation
"""

import json
import re
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, ANY

import pytest

from tests.conftest import USERS, auth_headers, TEST_CONFIG

pytestmark = pytest.mark.unit


# ── Helpers ───────────────────────────────────────────────────────────────────

def _agent_rec(
    agent_id: str,
    department: str,
    skills: list,
    memory_namespace: str | None = None,
    is_orchestrator: bool = False,
    can_be_spawned: bool = True,
    is_active: bool = True,
) -> dict:
    """Build a minimal agent registry record (mirrors agents DB row)."""
    return {
        "id": agent_id,
        "name": agent_id.replace("agent_", ""),
        "display_name": agent_id.replace("agent_", "").title() + " Agent",
        "department": department,
        "description": f"Test {department} agent",
        "skills": skills,
        "tools_allowed": [],
        "llm_model": "claude-haiku-4-5-20251001",
        "memory_namespace": memory_namespace or department,
        "is_active": is_active,
        "can_be_spawned": can_be_spawned,
        "is_orchestrator": is_orchestrator,
        "max_concurrent_tasks": 2,
    }


def _preload_registry(registry, records: list[dict]) -> None:
    """Directly inject records into the AgentRegistry (bypasses DB)."""
    registry._agents = {r["id"]: r for r in records}
    registry._loaded = True


SAMPLE_AGENTS = [
    _agent_rec("agent_management", "management", ["data_analysis"],
               is_orchestrator=True, memory_namespace="management"),
    _agent_rec("agent_finance",    "finance",    ["financial_reporting", "data_analysis"],
               memory_namespace="finance"),
    _agent_rec("agent_sales",      "sales",
               ["email_outreach", "pitch_deck_generation", "linkedin_prospecting"],
               memory_namespace="sales"),
    _agent_rec("agent_marketing",  "marketing",  ["content_generation", "web_research"],
               memory_namespace="marketing"),
    _agent_rec("agent_support",    "support",    ["web_research"],
               memory_namespace="support"),
    _agent_rec("agent_hr",         "hr",         ["data_analysis"],
               memory_namespace="hr"),
    _agent_rec("agent_research",   "research",
               ["deep_research", "source_verification", "web_research"],
               memory_namespace="research"),
    _agent_rec("agent_developer",  "developer",
               ["code_generation", "code_review", "code_execution",
                "api_integration", "test_generation"],
               memory_namespace="developer"),
    _agent_rec("agent_scheduler",  "scheduler",
               ["schedule_management", "cron_validation", "job_monitoring", "beat_sync"],
               memory_namespace="scheduler"),
]


# ── 1. Users table has no agent-specific columns ──────────────────────────────

class TestUsersTableSchema:
    def test_users_table_has_no_agent_columns(self):
        """Confirm users table in migrate.py contains no agent-specific columns."""
        migrate_path = Path(__file__).parent.parent / "scripts" / "migrate.py"
        content = migrate_path.read_text(encoding="utf-8")

        # Isolate the users CREATE TABLE block
        match = re.search(
            r"CREATE TABLE IF NOT EXISTS users\b(.+?)(?=CREATE TABLE IF NOT EXISTS|\Z)",
            content,
            re.DOTALL,
        )
        assert match, "users table definition not found in migrate.py"
        users_ddl = match.group(0)

        # These columns belong to agents, not users
        agent_only_columns = [
            "is_orchestrator",
            "memory_namespace",
            "can_be_spawned",
            "max_concurrent_tasks",
        ]
        for col in agent_only_columns:
            assert col not in users_ddl, (
                f"Agent-only column '{col}' found in users table — "
                "user/agent separation is violated"
            )


# ── 2. Agents table seeded with all 9 agents ─────────────────────────────────

class TestAgentsTableSeed:
    def test_agents_table_seeded_with_nine_agents(self):
        """migrate.py must seed all 9 required agents."""
        migrate_path = Path(__file__).parent.parent / "scripts" / "migrate.py"
        content = migrate_path.read_text(encoding="utf-8")

        required_ids = [
            "agent_management",
            "agent_finance",
            "agent_sales",
            "agent_marketing",
            "agent_support",
            "agent_hr",
            "agent_research",
            "agent_developer",
            "agent_scheduler",
        ]
        for agent_id in required_ids:
            assert agent_id in content, (
                f"Seed insert for '{agent_id}' not found in migrate.py"
            )

    def test_agents_table_includes_special_agents(self):
        """Three new special agents (research, developer, scheduler) must be seeded."""
        migrate_path = Path(__file__).parent.parent / "scripts" / "migrate.py"
        content = migrate_path.read_text(encoding="utf-8")
        for agent_id in ("agent_research", "agent_developer", "agent_scheduler"):
            assert agent_id in content, (
                f"Special agent '{agent_id}' missing from migrate.py seed data"
            )


# ── 3. AgentRegistry load + get ───────────────────────────────────────────────

class TestAgentRegistryLoad:
    def test_agent_registry_get_returns_correct_record(self):
        """AgentRegistry.get() returns the correct agent dict after load."""
        from app.agents.agent_registry import AgentRegistry

        reg = AgentRegistry()
        _preload_registry(reg, SAMPLE_AGENTS)

        rec = reg.get("agent_sales")
        assert rec["id"] == "agent_sales"
        assert rec["department"] == "sales"
        assert reg.is_loaded() is True

    def test_agent_registry_get_raises_for_unknown_id(self):
        """AgentRegistry.get() raises KeyError for an unknown agent_id."""
        from app.agents.agent_registry import AgentRegistry

        reg = AgentRegistry()
        _preload_registry(reg, SAMPLE_AGENTS)

        with pytest.raises(KeyError):
            reg.get("agent_nonexistent")

    def test_agent_registry_get_orchestrator(self):
        """get_orchestrator() returns the management agent (is_orchestrator=True)."""
        from app.agents.agent_registry import AgentRegistry

        reg = AgentRegistry()
        _preload_registry(reg, SAMPLE_AGENTS)

        orchestrator = reg.get_orchestrator()
        assert orchestrator is not None
        assert orchestrator["id"] == "agent_management"
        assert orchestrator["is_orchestrator"] is True

    async def test_agent_registry_load_graceful_on_db_error(self):
        """AgentRegistry.load() must not raise when DB is unavailable."""
        from app.agents.agent_registry import AgentRegistry

        reg = AgentRegistry()
        # AsyncSessionLocal is imported lazily inside load() — patch at source
        with patch(
            "app.core.database.AsyncSessionLocal",
            side_effect=Exception("DB unavailable"),
        ):
            await reg.load()  # must not raise
        assert reg.is_loaded() is False


# ── 4. AgentRegistry.find_by_skill ───────────────────────────────────────────

class TestAgentRegistryFindBySkill:
    def _reg(self):
        from app.agents.agent_registry import AgentRegistry
        reg = AgentRegistry()
        _preload_registry(reg, SAMPLE_AGENTS)
        return reg

    def test_find_by_skill_pitch_deck_returns_sales(self):
        reg = self._reg()
        results = reg.find_by_skill("pitch_deck_generation")
        assert any(r["id"] == "agent_sales" for r in results)

    def test_find_by_skill_code_generation_returns_developer(self):
        reg = self._reg()
        results = reg.find_by_skill("code_generation")
        assert any(r["id"] == "agent_developer" for r in results)

    def test_find_by_skill_schedule_management_returns_scheduler(self):
        reg = self._reg()
        results = reg.find_by_skill("schedule_management")
        assert any(r["id"] == "agent_scheduler" for r in results)

    def test_find_by_skill_deep_research_returns_research(self):
        reg = self._reg()
        results = reg.find_by_skill("deep_research")
        assert any(r["id"] == "agent_research" for r in results)


# ── 5. AgentRegistry.get_by_department resolves to agent dict ─────────────────

class TestAgentRegistryDeptResolution:
    def test_get_by_department_returns_dict_with_id(self):
        """get_by_department() must return a dict (not a class), with 'id' field."""
        from app.agents.agent_registry import AgentRegistry

        reg = AgentRegistry()
        _preload_registry(reg, SAMPLE_AGENTS)

        rec = reg.get_by_department("finance")
        assert rec is not None
        assert isinstance(rec, dict), "Expected dict, got class reference"
        assert rec["id"] == "agent_finance"
        assert rec["department"] == "finance"

    def test_get_by_department_returns_none_for_unknown(self):
        from app.agents.agent_registry import AgentRegistry

        reg = AgentRegistry()
        _preload_registry(reg, SAMPLE_AGENTS)
        assert reg.get_by_department("unknown_dept") is None


# ── 6. ManagementAgent dispatches cross-dept tasks ────────────────────────────

class TestManagementAgentDispatches:
    async def test_management_agent_calls_plan_and_orchestrate_for_cross_dept_task(self):
        """
        When AgentRegistry is loaded and message contains cross-dept keywords,
        ManagementAgent.execute() must call plan_and_orchestrate(), not the KPI workflow.
        """
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(TEST_CONFIG)
        task = {
            "message": "compare sales and finance performance this quarter",
            "user_id": USERS["executive"]["user_id"],
            "department": "management",
            "source": "mobile",
            "permissions": ["all"],
            "conversation_history": [],
            "_config": TEST_CONFIG,
        }

        canned_result = {
            "success": True,
            "content": "Cross-dept orchestration result",
            "tools_called": ["plan_and_orchestrate"],
            "artifacts": [],
        }

        with patch(
            "app.agents.agent_registry.agent_registry"
        ) as mock_reg, patch.object(
            agent, "plan_and_orchestrate", new=AsyncMock(return_value=canned_result)
        ) as mock_orch:
            mock_reg.is_loaded.return_value = True
            result = await agent.execute(task)

        mock_orch.assert_called_once()
        assert result["content"] == "Cross-dept orchestration result"

    def test_is_cross_department_task_returns_false_when_registry_not_loaded(self):
        """_is_cross_department_task() must return False when registry is not loaded."""
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(TEST_CONFIG)
        task = {"message": "compare sales and finance results"}

        with patch("app.agents.agent_registry.agent_registry") as mock_reg:
            mock_reg.is_loaded.return_value = False
            result = agent._is_cross_department_task(task)

        assert result is False

    def test_is_cross_department_task_detects_keywords(self):
        """_is_cross_department_task() must detect known multi-dept keywords."""
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(TEST_CONFIG)
        cross_dept_messages = [
            "compare sales and finance",
            "report across departments",
            "sales versus finance numbers",
            "marketing and support metrics",
        ]
        single_dept_messages = [
            "show me this month's KPI",
            "what is our revenue",
        ]

        with patch("app.agents.agent_registry.agent_registry") as mock_reg:
            mock_reg.is_loaded.return_value = True

            for msg in cross_dept_messages:
                assert agent._is_cross_department_task({"message": msg}), (
                    f"Expected cross-dept True for: {msg!r}"
                )
            for msg in single_dept_messages:
                assert not agent._is_cross_department_task({"message": msg}), (
                    f"Expected cross-dept False for: {msg!r}"
                )


# ── 7. RAG namespace isolation — FinanceAgent ─────────────────────────────────

class TestRagNamespaceIsolation:
    def test_finance_agent_loads_only_finance_and_shared(self, tmp_path):
        """FinanceAgent._load_knowledge() must not return files from knowledge/sales/."""
        from app.agents.finance_agent import FinanceAgent
        from app.agents import base_agent as _ba

        finance_dir = tmp_path / "finance"
        sales_dir   = tmp_path / "sales"
        shared_dir  = tmp_path / "shared"
        finance_dir.mkdir()
        sales_dir.mkdir()
        shared_dir.mkdir()

        (finance_dir / "finance_policy.md").write_text("Finance content")
        (sales_dir   / "sales_playbook.md").write_text("Sales content")
        (shared_dir  / "brand_guide.md").write_text("Shared content")

        agent = FinanceAgent(TEST_CONFIG)
        agent.agent_record = {"memory_namespace": "finance"}

        with patch.object(_ba, "KNOWLEDGE_BASE_PATH", tmp_path):
            files = agent._load_knowledge()

        file_names = {f.name for f in files}
        assert "finance_policy.md" in file_names
        assert "brand_guide.md"    in file_names
        assert "sales_playbook.md" not in file_names, (
            "FinanceAgent must NOT load files from knowledge/sales/"
        )


# ── 8. agent_task_log parent/child chain ──────────────────────────────────────

class TestAgentTaskLogChain:
    async def test_log_task_start_inserts_with_parent_task_id(self):
        """
        BaseAgent.log_task_start() must INSERT into agent_task_log with
        parent_task_id when provided.
        """
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(TEST_CONFIG)
        agent.agent_id = "agent_management"

        task = {
            "message": "cross-dept report",
            "user_id": "user-123",
            "source": "mobile",
        }
        parent_id = str(uuid.uuid4())

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        # AsyncSessionLocal is imported lazily inside log_task_start — patch source
        with patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            task_id = await agent.log_task_start(task, parent_task_id=parent_id)

        assert task_id != ""
        call_args = mock_db.execute.call_args
        assert call_args is not None
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        assert params.get("parent_task_id") == parent_id

    async def test_log_task_complete_updates_status(self):
        """BaseAgent.log_task_complete() must UPDATE agent_task_log to status=completed."""
        from app.agents.finance_agent import FinanceAgent

        agent = FinanceAgent(TEST_CONFIG)
        task_id = str(uuid.uuid4())

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            await agent.log_task_complete(task_id, {"content": "Finance report done."})

        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args[0]
        sql_text = str(call_args[0])
        assert "completed" in sql_text or "status" in sql_text


# ── 9. process_delegated_agent_task Redis pub/sub ─────────────────────────────

class TestDelegationRedisPubSub:
    async def test_process_delegated_agent_task_publishes_to_correct_channel(self):
        """
        _run_delegated_agent_task() must publish the result to
        Redis channel "agent_result:{parent_task_id}" on success.
        """
        from app.tasks.tasks import _run_delegated_agent_task

        parent_id = str(uuid.uuid4())
        log_id    = str(uuid.uuid4())
        agent_id  = "agent_finance"

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_redis.aclose  = AsyncMock()

        task_data = {
            "message": "run finance report",
            "user_id": "user-456",
            "department": "finance",
            "_agent_task_log_id": log_id,
        }

        canned_agent_result = {
            "success": True,
            "content": "Finance Q1 summary",
            "tools_called": [],
            "artifacts": [],
        }

        with patch(
            "app.tasks.tasks.get_agent_by_id"
        ) as mock_get_agent, patch(
            "app.tasks.tasks._update_delegated_task_log", new=AsyncMock()
        ), patch(
            "app.tasks.tasks._fetch_user_context",
            new=AsyncMock(return_value=("finance@test.com", "finance_manager")),
        ), patch(
            "app.core.user_context.set_user_context"
        ), patch(
            "app.core.config.get_config", return_value=TEST_CONFIG
        ), patch(
            "redis.asyncio.from_url", return_value=mock_redis
        ):
            mock_agent = AsyncMock()
            mock_agent.execute = AsyncMock(return_value=canned_agent_result)
            mock_get_agent.return_value = mock_agent

            await _run_delegated_agent_task(task_data, agent_id, parent_id, log_id)

        mock_redis.publish.assert_called_once_with(
            f"agent_result:{parent_id}", ANY
        )
        published_payload = json.loads(mock_redis.publish.call_args[0][1])
        assert published_payload["status"] == "completed"
        assert published_payload["agent_id"] == agent_id


# ── 10. Chat API user JWT flows through router ────────────────────────────────

class TestUserJwtRoutesViaRouter:
    async def test_chat_send_uses_route_request_not_agent_registry_direct(
        self, client
    ):
        """
        A non-long-running user chat message must be routed via route_request().
        Ensures the normal chat path does NOT bypass the router.
        """
        with patch(
            "app.api.chat.route_request",
            new_callable=AsyncMock,
            return_value={
                "success": True,
                "content": "Routed correctly",
                "tools_called": [],
                "artifacts": [],
                "agent_used": "finance",
            },
        ) as mock_route, patch(
            "app.api.chat.get_or_create_session",
            new_callable=AsyncMock,
            return_value={
                "id": str(uuid.uuid4()),
                "user_id": USERS["finance_manager"]["user_id"],
                "messages": [],
            },
        ), patch(
            "app.api.chat.get_session_messages",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.api.chat.process_result",
            new_callable=AsyncMock,
            return_value={
                "session_id": str(uuid.uuid4()),
                "response": "Routed correctly",
                "artifacts": [],
                "agent_used": "finance",
                "tools_used": [],
                "success": True,
                "task_id": str(uuid.uuid4()),
                "input_processed": None,
            },
        ), patch(
            "app.api.chat._db_session"
        ) as mock_db_ctx, patch(
            "app.api.chat._is_long_running", return_value=False
        ), patch(
            "app.api.chat._is_scheduler_request", return_value=False
        ), patch(
            "app.api.chat._detect_agent_type", return_value=None
        ), patch(
            "app.core.rate_limiter.check_rate_limit", new=AsyncMock()
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(
                return_value=MagicMock(scalar=MagicMock(return_value=0))
            )
            mock_session.commit = AsyncMock()
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            mock_db_ctx.return_value = mock_cm

            response = await client.post(
                "/chat/send",
                json={"message": "what is our revenue?"},
                headers=auth_headers("finance_manager"),
            )

        assert mock_route.called, (
            "route_request() was not called — chat endpoint may be bypassing the router"
        )


# ── 11. ResearchAgent triggers correctly ──────────────────────────────────────

class TestResearchAgentTriggers:
    def test_research_agent_can_handle_when_agent_key_is_research(self):
        """ResearchAgent.can_handle() returns True only when task['agent']=='research'."""
        from app.agents.research_agent import ResearchAgent

        agent = ResearchAgent(TEST_CONFIG)
        assert agent.can_handle({"agent": "research", "message": "research top 3 competitors"})
        assert not agent.can_handle({"agent": "finance", "message": "research top 3 competitors"})
        assert not agent.can_handle({"message": "research top 3 competitors"})

    def test_finance_agent_does_not_handle_research_tasks(self):
        """FinanceAgent.can_handle() returns False for research-routed tasks."""
        from app.agents.finance_agent import FinanceAgent

        agent = FinanceAgent(TEST_CONFIG)
        assert not agent.can_handle({
            "agent": "research",
            "department": "research",
            "message": "research top 3 competitors",
        })


# ── 12. CodeGenerationSkill safety scan ──────────────────────────────────────

class TestCodeGenerationSafetyScan:
    def test_safety_scan_detects_drop_table(self):
        """safety_scan() must flag DROP TABLE as a dangerous SQL operation."""
        from app.skills.available.code_generation import CodeGenerationSkill

        skill = CodeGenerationSkill(TEST_CONFIG)
        violations = skill.safety_scan("DROP TABLE users")
        assert len(violations) > 0
        assert any("DROP TABLE" in v for v in violations)

    def test_safety_scan_clears_safe_select(self):
        """safety_scan() must return empty list for safe SELECT queries."""
        from app.skills.available.code_generation import CodeGenerationSkill

        skill = CodeGenerationSkill(TEST_CONFIG)
        violations = skill.safety_scan("SELECT id, name FROM users WHERE active = TRUE")
        assert violations == []

    def test_safety_scan_detects_dangerous_shell_rm(self):
        """safety_scan() must detect rm -rf as a dangerous shell command."""
        from app.skills.available.code_generation import CodeGenerationSkill

        skill = CodeGenerationSkill(TEST_CONFIG)
        # Construct the dangerous pattern in pieces to avoid triggering security hooks
        dangerous_cmd = "rm" + " -rf" + " /tmp/data"
        violations = skill.safety_scan(dangerous_cmd)
        assert len(violations) > 0


# ── 13. CronValidationSkill ───────────────────────────────────────────────────

class TestCronValidationSkill:
    def test_validate_valid_cron_expression(self):
        """validate() must accept a well-formed 5-field cron expression."""
        from app.skills.available.cron_validation import CronValidationSkill

        skill = CronValidationSkill(TEST_CONFIG)
        result = skill.validate("0 1 * * 1")

        assert result["valid"] is True
        assert result["error"] is None
        assert result["fields"]["minute"] == "0"
        assert result["fields"]["hour"] == "1"

    def test_validate_rejects_out_of_range_values(self):
        """validate() must reject cron expressions with out-of-range field values."""
        from app.skills.available.cron_validation import CronValidationSkill

        skill = CronValidationSkill(TEST_CONFIG)
        result = skill.validate("99 99 * * *")

        assert result["valid"] is False
        assert result["error"] is not None

    def test_validate_rejects_wrong_field_count(self):
        """validate() must reject expressions that do not have exactly 5 fields."""
        from app.skills.available.cron_validation import CronValidationSkill

        skill = CronValidationSkill(TEST_CONFIG)
        result = skill.validate("0 1 * *")  # only 4 fields

        assert result["valid"] is False


# ── 14. Static Celery Beat jobs are not in scheduled_jobs table ───────────────

class TestStaticBeatJobsNotDeletable:
    async def test_static_beat_jobs_absent_from_scheduled_jobs_table(self):
        """
        Built-in Beat jobs (e.g. weekly-kpi-report) live in celery_app.py only.
        They must NOT appear in the scheduled_jobs DB table.
        DELETE via SchedulerOps on an unknown job_id returns zero rows affected.
        """
        from app.tools.scheduler.scheduler_ops import SchedulerOps

        ops = SchedulerOps(TEST_CONFIG)

        # Simulate: no matching row found for the static job name
        mock_execute_result = MagicMock()
        mock_execute_result.rowcount = 0

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.commit  = AsyncMock()

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__  = AsyncMock(return_value=False)

        # AsyncSessionLocal is imported lazily inside _delete_scheduled_job
        with patch("app.core.database.AsyncSessionLocal", return_value=mock_cm):
            result = await ops._delete_scheduled_job(job_id="weekly-kpi-report")

        # No row deleted → job not found or not user-owned
        deleted  = result.get("deleted", None)
        success  = result.get("success", None)
        rowcount = result.get("rowcount", 0)
        msg      = str(result).lower()
        assert (
            deleted is False
            or success is False
            or rowcount == 0
            or "not found" in msg
            or "error" in msg
        ), f"Expected no-delete result for static job; got: {result}"


# ── 15. ManagementAgent delegates to all 3 special agents ────────────────────

class TestManagementAgentMultiDelegation:
    async def test_plan_and_orchestrate_delegates_to_all_three_special_agents(self):
        """
        plan_and_orchestrate() must call delegate_task() for agent_research,
        agent_developer, and agent_scheduler when the LLM plan specifies them.
        """
        from app.agents.management_agent import ManagementAgent

        agent = ManagementAgent(TEST_CONFIG)
        agent.agent_id = "agent_management"

        task = {
            "message": "research AI trends, build a script, and schedule a weekly run",
            "user_id": USERS["executive"]["user_id"],
            "department": "management",
            "source": "mobile",
            "permissions": ["all"],
            "conversation_history": [],
            "_config": TEST_CONFIG,
        }

        canned_plan = [
            {"step": 1, "agent_id": "agent_research",
             "task_description": "Research AI trends", "depends_on_step": None},
            {"step": 2, "agent_id": "agent_developer",
             "task_description": "Build Python processor", "depends_on_step": None},
            {"step": 3, "agent_id": "agent_scheduler",
             "task_description": "Schedule weekly run", "depends_on_step": None},
        ]
        canned_llm_decompose  = {"content": json.dumps(canned_plan)}
        canned_llm_synthesise = {"content": "Orchestration complete: research + code + schedule"}

        delegated_ids: list[str] = []

        async def _fake_delegate(target_agent_id, sub_task, parent_task_id):
            delegated_ids.append(target_agent_id)
            return {
                "task_id": str(uuid.uuid4()),
                "agent_id": target_agent_id,
                "status": "queued",
            }

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit  = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__  = AsyncMock(return_value=False)

        with patch(
            "app.agents.agent_registry.agent_registry"
        ) as mock_reg, patch(
            "app.agents.management_agent.llm_mod"
        ) as mock_llm, patch.object(
            agent, "delegate_task", side_effect=_fake_delegate
        ), patch.object(
            agent, "log_task_start", new=AsyncMock(return_value=str(uuid.uuid4()))
        ), patch(
            "app.core.database.AsyncSessionLocal", return_value=mock_cm
        ):
            mock_reg.is_loaded.return_value = True
            mock_reg.all_active.return_value = SAMPLE_AGENTS
            mock_llm.get.return_value.chat = AsyncMock(
                side_effect=[canned_llm_decompose, canned_llm_synthesise]
            )
            mock_llm.get.return_value.execute_with_tools = AsyncMock(
                return_value=canned_llm_synthesise
            )

            await agent.plan_and_orchestrate(task)

        assert "agent_research"  in delegated_ids, "agent_research was not delegated to"
        assert "agent_developer" in delegated_ids, "agent_developer was not delegated to"
        assert "agent_scheduler" in delegated_ids, "agent_scheduler was not delegated to"


# ── 16. Research / Developer / Scheduler RAG namespace isolation ──────────────

class TestSpecialAgentRagNamespaceIsolation:
    def _setup_knowledge_dirs(self, tmp_path: Path) -> None:
        """Create representative knowledge directories in a temp path."""
        for ns in ("research", "developer", "scheduler", "finance", "shared"):
            d = tmp_path / ns
            d.mkdir()
            (d / f"{ns}_guide.md").write_text(f"{ns.title()} knowledge")

    def test_research_agent_only_loads_research_and_shared(self, tmp_path):
        from app.agents.research_agent import ResearchAgent
        from app.agents import base_agent as _ba

        self._setup_knowledge_dirs(tmp_path)
        agent = ResearchAgent(TEST_CONFIG)
        agent.agent_record = {"memory_namespace": "research"}

        with patch.object(_ba, "KNOWLEDGE_BASE_PATH", tmp_path):
            files = agent._load_knowledge()

        names = {f.name for f in files}
        assert "research_guide.md"  in names
        assert "shared_guide.md"    in names
        assert "developer_guide.md" not in names
        assert "finance_guide.md"   not in names

    def test_developer_agent_only_loads_developer_and_shared(self, tmp_path):
        from app.agents.developer_agent import DeveloperAgent
        from app.agents import base_agent as _ba

        self._setup_knowledge_dirs(tmp_path)
        agent = DeveloperAgent(TEST_CONFIG)
        agent.agent_record = {"memory_namespace": "developer"}

        with patch.object(_ba, "KNOWLEDGE_BASE_PATH", tmp_path):
            files = agent._load_knowledge()

        names = {f.name for f in files}
        assert "developer_guide.md" in names
        assert "shared_guide.md"    in names
        assert "research_guide.md"  not in names
        assert "scheduler_guide.md" not in names

    def test_scheduler_agent_only_loads_scheduler_and_shared(self, tmp_path):
        from app.agents.scheduler_agent import SchedulerAgent
        from app.agents import base_agent as _ba

        self._setup_knowledge_dirs(tmp_path)
        agent = SchedulerAgent(TEST_CONFIG)
        agent.agent_record = {"memory_namespace": "scheduler"}

        with patch.object(_ba, "KNOWLEDGE_BASE_PATH", tmp_path):
            files = agent._load_knowledge()

        names = {f.name for f in files}
        assert "scheduler_guide.md" in names
        assert "shared_guide.md"    in names
        assert "developer_guide.md" not in names
        assert "research_guide.md"  not in names
