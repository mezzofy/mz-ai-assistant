"""
HRAgent unit and integration tests.

Tests cover:
  - can_handle() routing logic
  - execute() dispatch to correct sub-workflow
  - _payroll_query_workflow full pipeline (mock DB + LLM)
  - _weekly_hr_summary_workflow Teams + email delivery
  - Agent registry includes HRAgent
  - Router webhook events route to HRAgent
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_CONFIG, CANNED_AGENT_RESPONSE

pytestmark = pytest.mark.unit


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_task(message="", department="hr", source="mobile", event=""):
    return {
        "message": message,
        "department": department,
        "source": source,
        "event": event,
        "_config": TEST_CONFIG,
        "conversation_history": [],
    }


def _make_hr_agent():
    from app.agents.hr_agent import HRAgent
    return HRAgent(TEST_CONFIG)


# ── Unit Tests: can_handle() ──────────────────────────────────────────────────

class TestHRAgentUnit:

    def test_can_handle_hr_department_returns_true(self):
        agent = _make_hr_agent()
        assert agent.can_handle(_make_task("show me payroll")) is True

    def test_can_handle_non_hr_department_returns_false(self):
        agent = _make_hr_agent()
        task = _make_task("show me payroll", department="finance")
        assert agent.can_handle(task) is False

    def test_can_handle_empty_department_returns_false(self):
        agent = _make_hr_agent()
        assert agent.can_handle(_make_task("anything", department="")) is False

    def test_can_handle_hr_case_insensitive(self):
        agent = _make_hr_agent()
        assert agent.can_handle(_make_task("anything", department="HR")) is True
        assert agent.can_handle(_make_task("anything", department="Hr")) is True

    # ── execute() routing tests ───────────────────────────────────────────────

    async def test_execute_payroll_keyword_routes_to_payroll_workflow(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "payroll ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_payroll_query_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_p, \
             patch.object(agent, "_leave_query_workflow", new_callable=AsyncMock) as mock_l, \
             patch.object(agent, "_general_response", new_callable=AsyncMock) as mock_g:
            await agent.execute(_make_task("show me payroll summary"))
        mock_p.assert_called_once()
        mock_l.assert_not_called()
        mock_g.assert_not_called()

    async def test_execute_salary_keyword_routes_to_payroll_workflow(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_payroll_query_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_p:
            await agent.execute(_make_task("what is the salary structure?"))
        mock_p.assert_called_once()

    async def test_execute_leave_keyword_routes_to_leave_workflow(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "leave ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_leave_query_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_l, \
             patch.object(agent, "_payroll_query_workflow", new_callable=AsyncMock) as mock_p, \
             patch.object(agent, "_general_response", new_callable=AsyncMock) as mock_g:
            await agent.execute(_make_task("how many leave days do I have?"))
        mock_l.assert_called_once()
        mock_p.assert_not_called()
        mock_g.assert_not_called()

    async def test_execute_attendance_keyword_routes_to_leave_workflow(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_leave_query_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_l:
            await agent.execute(_make_task("check my attendance record"))
        mock_l.assert_called_once()

    async def test_execute_recruit_keyword_routes_to_recruitment_workflow(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "recruit ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_recruitment_query_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_r, \
             patch.object(agent, "_general_response", new_callable=AsyncMock) as mock_g:
            await agent.execute(_make_task("what is the recruit pipeline?"))
        mock_r.assert_called_once()
        mock_g.assert_not_called()

    async def test_execute_hiring_keyword_routes_to_recruitment_workflow(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_recruitment_query_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_r:
            await agent.execute(_make_task("show me the current hiring status"))
        mock_r.assert_called_once()

    async def test_execute_headcount_keyword_routes_to_recruitment_workflow(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_recruitment_query_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_r:
            await agent.execute(_make_task("what is our headcount by department?"))
        mock_r.assert_called_once()

    async def test_execute_scheduler_weekly_routes_to_weekly_summary(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "weekly ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_weekly_hr_summary_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_w, \
             patch.object(agent, "_headcount_report_workflow", new_callable=AsyncMock) as mock_h, \
             patch.object(agent, "_general_response", new_callable=AsyncMock) as mock_g:
            await agent.execute(_make_task("", source="scheduler", event="weekly_hr_summary"))
        mock_w.assert_called_once()
        mock_h.assert_not_called()
        mock_g.assert_not_called()

    async def test_execute_scheduler_monthly_routes_to_headcount(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "headcount ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_headcount_report_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_h, \
             patch.object(agent, "_weekly_hr_summary_workflow", new_callable=AsyncMock) as mock_w:
            await agent.execute(_make_task("", source="scheduler", event="monthly_headcount"))
        mock_h.assert_called_once()
        mock_w.assert_not_called()

    async def test_execute_webhook_onboarded_routes_to_onboarding(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "onboard ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_onboarding_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_on, \
             patch.object(agent, "_offboarding_workflow", new_callable=AsyncMock) as mock_off:
            await agent.execute(_make_task("", source="webhook", event="employee_onboarded"))
        mock_on.assert_called_once()
        mock_off.assert_not_called()

    async def test_execute_webhook_offboarded_routes_to_offboarding(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "offboard ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_offboarding_workflow", new_callable=AsyncMock,
                          return_value=canned) as mock_off, \
             patch.object(agent, "_onboarding_workflow", new_callable=AsyncMock) as mock_on:
            await agent.execute(_make_task("", source="webhook", event="employee_offboarded"))
        mock_off.assert_called_once()
        mock_on.assert_not_called()

    async def test_execute_general_message_falls_back_to_general_response(self):
        agent = _make_hr_agent()
        canned = {"success": True, "content": "general ok", "artifacts": [], "tools_called": []}
        with patch.object(agent, "_general_response", new_callable=AsyncMock,
                          return_value=canned) as mock_g, \
             patch.object(agent, "_payroll_query_workflow", new_callable=AsyncMock) as mock_p, \
             patch.object(agent, "_leave_query_workflow", new_callable=AsyncMock) as mock_l, \
             patch.object(agent, "_recruitment_query_workflow", new_callable=AsyncMock) as mock_r:
            await agent.execute(_make_task("what is the company culture?"))
        mock_g.assert_called_once()
        mock_p.assert_not_called()
        mock_l.assert_not_called()
        mock_r.assert_not_called()


# ── Integration Tests: full pipeline with mocked external deps ────────────────

class TestHRWorkflow:

    async def test_payroll_query_full_pipeline(self):
        """_payroll_query_workflow: mock DB + LLM → verify response content."""
        agent = _make_hr_agent()
        task = _make_task("show me payroll summary for March")

        payroll_data = {"total_payroll": 500000, "employees": 50, "month": "March 2026"}
        llm_content = "Total payroll for March 2026 is SGD 500,000 across 50 employees."

        with patch("app.tools.database.db_ops.DatabaseOps") as mock_db_cls, \
             patch("app.agents.hr_agent.llm_mod") as mock_llm:

            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(return_value={"success": True, "output": payroll_data})
            mock_db_cls.return_value = mock_db

            mock_llm.get.return_value.chat = AsyncMock(
                return_value={"content": llm_content, "usage": {}}
            )

            result = await agent._payroll_query_workflow(task)

        assert result["success"] is True
        assert result["content"] == llm_content
        assert "query_analytics" in result["tools_called"]

    async def test_payroll_prompt_injects_real_date_not_placeholder(self):
        """Date injection: LLM prompt must contain today's real date, not a placeholder."""
        from datetime import date
        agent = _make_hr_agent()
        task = _make_task("show me payroll")
        captured_prompts = []

        async def capture_chat(messages, task_context=None, stream=False):
            for m in messages:
                if "content" in m:
                    captured_prompts.append(m["content"])
            return {"content": "payroll ok", "usage": {}}

        with patch("app.tools.database.db_ops.DatabaseOps") as mock_db_cls, \
             patch("app.agents.hr_agent.llm_mod") as mock_llm:

            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(return_value={"success": True, "output": {}})
            mock_db_cls.return_value = mock_db
            mock_llm.get.return_value.chat = AsyncMock(side_effect=capture_chat)

            await agent._payroll_query_workflow(task)

        today = date.today().strftime("%B %d, %Y")
        assert any(today in p for p in captured_prompts), \
            f"Real date '{today}' not found in payroll prompt"
        assert not any("{Current Date}" in p for p in captured_prompts), \
            "Literal '{Current Date}' placeholder found — date injection failed"

    async def test_weekly_summary_delivers_to_teams(self):
        """_weekly_hr_summary_workflow: verify Teams delivery is called."""
        agent = _make_hr_agent()
        task = _make_task("", source="scheduler", event="weekly_hr_summary")

        with patch("app.tools.database.db_ops.DatabaseOps") as mock_db_cls, \
             patch("app.tools.document.pdf_ops.PDFOps") as mock_pdf_cls, \
             patch("app.agents.hr_agent.llm_mod") as mock_llm, \
             patch.object(agent, "_deliver_to_teams", new_callable=AsyncMock) as mock_teams, \
             patch.object(agent, "_send_email", new_callable=AsyncMock) as mock_email:

            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(return_value={"success": True, "output": {}})
            mock_db_cls.return_value = mock_db

            mock_pdf = AsyncMock()
            mock_pdf.execute = AsyncMock(return_value={"success": True, "output": "/tmp/hr.pdf"})
            mock_pdf_cls.return_value = mock_pdf

            mock_llm.get.return_value.chat = AsyncMock(
                return_value={"content": "Weekly HR summary content.", "usage": {}}
            )

            result = await agent._weekly_hr_summary_workflow(task)

        assert result["success"] is True
        mock_teams.assert_called_once()
        teams_call = mock_teams.call_args
        assert teams_call.kwargs["channel"] == "#hr"

    async def test_weekly_summary_sends_email_when_configured(self):
        """_weekly_hr_summary_workflow: verify email is sent when hr_manager_email is set."""
        config = {**TEST_CONFIG, "notifications": {"hr_manager_email": "hr@mezzofy.com"}}
        agent = _make_hr_agent()
        agent.config = config
        task = _make_task("", source="scheduler", event="weekly_hr_summary")

        with patch("app.tools.database.db_ops.DatabaseOps") as mock_db_cls, \
             patch("app.tools.document.pdf_ops.PDFOps") as mock_pdf_cls, \
             patch("app.agents.hr_agent.llm_mod") as mock_llm, \
             patch.object(agent, "_deliver_to_teams", new_callable=AsyncMock), \
             patch.object(agent, "_send_email", new_callable=AsyncMock) as mock_email:

            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(return_value={"success": True, "output": {}})
            mock_db_cls.return_value = mock_db

            mock_pdf = AsyncMock()
            mock_pdf.execute = AsyncMock(return_value={"success": False, "output": None})
            mock_pdf_cls.return_value = mock_pdf

            mock_llm.get.return_value.chat = AsyncMock(
                return_value={"content": "summary", "usage": {}}
            )

            await agent._weekly_hr_summary_workflow(task)

        mock_email.assert_called_once()
        email_call = mock_email.call_args
        assert email_call.kwargs["to"] == "hr@mezzofy.com"

    async def test_onboarding_workflow_delivers_to_teams(self):
        """_onboarding_workflow: Teams delivery with correct channel and employee info."""
        agent = _make_hr_agent()
        task = {
            **_make_task("", source="webhook", event="employee_onboarded"),
            "payload": {"name": "Jane Doe", "role": "Software Engineer", "department": "Engineering"},
        }

        with patch("app.tools.document.pdf_ops.PDFOps") as mock_pdf_cls, \
             patch("app.agents.hr_agent.llm_mod") as mock_llm, \
             patch.object(agent, "_deliver_to_teams", new_callable=AsyncMock) as mock_teams:

            mock_pdf = AsyncMock()
            mock_pdf.execute = AsyncMock(return_value={"success": True, "output": "/tmp/onboard.pdf"})
            mock_pdf_cls.return_value = mock_pdf

            mock_llm.get.return_value.chat = AsyncMock(
                return_value={"content": "Onboarding checklist for Jane Doe.", "usage": {}}
            )

            result = await agent._onboarding_workflow(task)

        assert result["success"] is True
        mock_teams.assert_called_once()
        teams_call = mock_teams.call_args
        assert teams_call.kwargs["channel"] == "#hr"
        assert "Jane Doe" in teams_call.kwargs["message"]

    async def test_offboarding_workflow_delivers_to_teams(self):
        """_offboarding_workflow: Teams delivery with correct channel."""
        agent = _make_hr_agent()
        task = {
            **_make_task("", source="webhook", event="employee_offboarded"),
            "payload": {"name": "John Smith", "role": "Sales Manager",
                        "department": "Sales", "last_day": "2026-03-31"},
        }

        with patch("app.tools.document.pdf_ops.PDFOps") as mock_pdf_cls, \
             patch("app.agents.hr_agent.llm_mod") as mock_llm, \
             patch.object(agent, "_deliver_to_teams", new_callable=AsyncMock) as mock_teams:

            mock_pdf = AsyncMock()
            mock_pdf.execute = AsyncMock(return_value={"success": True, "output": "/tmp/offboard.pdf"})
            mock_pdf_cls.return_value = mock_pdf

            mock_llm.get.return_value.chat = AsyncMock(
                return_value={"content": "Exit summary for John Smith.", "usage": {}}
            )

            result = await agent._offboarding_workflow(task)

        assert result["success"] is True
        mock_teams.assert_called_once()
        teams_call = mock_teams.call_args
        assert teams_call.kwargs["channel"] == "#hr"
        assert "John Smith" in teams_call.kwargs["message"]


# ── Registry tests ─────────────────────────────────────────────────────────────

class TestHRAgentRegistry:

    def test_hr_registered_in_agent_map(self):
        from app.agents.agent_registry import AGENT_MAP
        from app.agents.hr_agent import HRAgent
        assert "hr" in AGENT_MAP
        assert AGENT_MAP["hr"] is HRAgent

    def test_get_agent_for_task_returns_hr_agent_for_hr_dept(self):
        from app.agents.agent_registry import get_agent_for_task
        from app.agents.hr_agent import HRAgent
        task = {"department": "hr", "role": "hr_manager", "permissions": [], "message": "payroll"}
        agent = get_agent_for_task(task, TEST_CONFIG)
        assert isinstance(agent, HRAgent)

    def test_get_all_agent_names_includes_hr(self):
        from app.agents.agent_registry import get_all_agent_names
        assert "hr" in get_all_agent_names()


# ── Router webhook routing tests ───────────────────────────────────────────────

class TestHRRouterWebhooks:

    async def test_employee_onboarded_webhook_routes_to_hr(self):
        from app.router import route_request
        mock_instance = AsyncMock()
        mock_instance.__class__.__name__ = "HRAgent"
        mock_instance.execute = AsyncMock(return_value={**CANNED_AGENT_RESPONSE, "agent_used": "hr"})
        MockHRClass = MagicMock(return_value=mock_instance)

        with patch("app.router.AGENT_MAP", {"hr": MockHRClass}):
            result = await route_request({
                "source": "webhook",
                "event": "employee_onboarded",
                "message": "",
                "_config": TEST_CONFIG,
            })

        assert result["success"] is True
        MockHRClass.assert_called_once_with(TEST_CONFIG)

    async def test_employee_offboarded_webhook_routes_to_hr(self):
        from app.router import route_request
        mock_instance = AsyncMock()
        mock_instance.__class__.__name__ = "HRAgent"
        mock_instance.execute = AsyncMock(return_value={**CANNED_AGENT_RESPONSE, "agent_used": "hr"})
        MockHRClass = MagicMock(return_value=mock_instance)

        with patch("app.router.AGENT_MAP", {"hr": MockHRClass}):
            result = await route_request({
                "source": "webhook",
                "event": "employee_offboarded",
                "message": "",
                "_config": TEST_CONFIG,
            })

        assert result["success"] is True
        MockHRClass.assert_called_once_with(TEST_CONFIG)

    async def test_leave_request_submitted_webhook_routes_to_hr(self):
        from app.router import route_request
        mock_instance = AsyncMock()
        mock_instance.__class__.__name__ = "HRAgent"
        mock_instance.execute = AsyncMock(return_value={**CANNED_AGENT_RESPONSE, "agent_used": "hr"})
        MockHRClass = MagicMock(return_value=mock_instance)

        with patch("app.router.AGENT_MAP", {"hr": MockHRClass}):
            result = await route_request({
                "source": "webhook",
                "event": "leave_request_submitted",
                "message": "",
                "_config": TEST_CONFIG,
            })

        assert result["success"] is True
        MockHRClass.assert_called_once_with(TEST_CONFIG)
