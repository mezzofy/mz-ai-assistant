"""
SalesAgent unit tests — execute() routing.

Tests cover:
  - Priority routing: inbox/scan phrases → _daily_email_lead_report_workflow
    before the "lead" catch-all reaches _prospecting_workflow
  - Scheduler source + "follow" → _daily_followup_workflow
  - Pitch deck phrases → _pitch_deck_workflow
  - Generic "lead" keyword still routes to _prospecting_workflow
  - Unrecognised message falls back to _general_sales_workflow
"""

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_CONFIG

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_task(message="", department="sales", source="mobile", event=""):
    return {
        "message": message,
        "department": department,
        "source": source,
        "event": event,
        "_config": TEST_CONFIG,
        "conversation_history": [],
    }


def _make_sales_agent():
    from app.agents.sales_agent import SalesAgent
    return SalesAgent(TEST_CONFIG)


_CANNED = {"success": True, "content": "ok", "artifacts": [], "tools_called": []}


# ── Routing: _daily_email_lead_report_workflow ─────────────────────────────────

class TestSalesAgentEmailLeadReportRouting:
    """
    Priority routing: inbox/scan phrases must reach _daily_email_lead_report_workflow
    BEFORE the generic "lead" keyword routes to _prospecting_workflow.

    Regression guard: "Run the daily sales inbox lead scan now" was being swallowed
    by the "lead" catch-all and routed to _prospecting_workflow instead.
    """

    @pytest.mark.asyncio
    async def test_inbox_lead_scan_routes_to_email_lead_report(self):
        """'Run the daily sales inbox lead scan now' → _daily_email_lead_report_workflow."""
        agent = _make_sales_agent()
        with patch.object(agent, "_daily_email_lead_report_workflow",
                          new_callable=AsyncMock, return_value=_CANNED) as mock_report, \
             patch.object(agent, "_prospecting_workflow",
                          new_callable=AsyncMock) as mock_prospect:
            await agent.execute(_make_task("Run the daily sales inbox lead scan now"))

        mock_report.assert_called_once()
        mock_prospect.assert_not_called()

    @pytest.mark.asyncio
    async def test_lead_scan_phrase_routes_to_email_lead_report(self):
        """'lead scan' phrase → _daily_email_lead_report_workflow, not prospecting."""
        agent = _make_sales_agent()
        with patch.object(agent, "_daily_email_lead_report_workflow",
                          new_callable=AsyncMock, return_value=_CANNED) as mock_report, \
             patch.object(agent, "_prospecting_workflow",
                          new_callable=AsyncMock) as mock_prospect:
            await agent.execute(_make_task("do the daily lead scan"))

        mock_report.assert_called_once()
        mock_prospect.assert_not_called()

    @pytest.mark.asyncio
    async def test_inbox_lead_report_phrase_still_routes_correctly(self):
        """Original 'inbox lead report' phrase still routes correctly."""
        agent = _make_sales_agent()
        with patch.object(agent, "_daily_email_lead_report_workflow",
                          new_callable=AsyncMock, return_value=_CANNED) as mock_report:
            await agent.execute(_make_task("run the inbox lead report"))

        mock_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_lead_report_phrase_still_routes_correctly(self):
        """Original 'email lead report' phrase still routes correctly."""
        agent = _make_sales_agent()
        with patch.object(agent, "_daily_email_lead_report_workflow",
                          new_callable=AsyncMock, return_value=_CANNED) as mock_report:
            await agent.execute(_make_task("generate the email lead report"))

        mock_report.assert_called_once()


# ── Routing: other sub-workflows ───────────────────────────────────────────────

class TestSalesAgentOtherRouting:

    @pytest.mark.asyncio
    async def test_lead_keyword_alone_routes_to_prospecting(self):
        """Generic 'lead' message (no inbox/scan context) → _prospecting_workflow."""
        agent = _make_sales_agent()
        with patch.object(agent, "_prospecting_workflow",
                          new_callable=AsyncMock, return_value=_CANNED) as mock_prospect, \
             patch.object(agent, "_daily_email_lead_report_workflow",
                          new_callable=AsyncMock) as mock_report:
            await agent.execute(_make_task("find me new leads on LinkedIn"))

        mock_prospect.assert_called_once()
        mock_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_scheduler_follow_routes_to_daily_followup(self):
        """source=scheduler + 'follow' → _daily_followup_workflow."""
        agent = _make_sales_agent()
        with patch.object(agent, "_daily_followup_workflow",
                          new_callable=AsyncMock, return_value=_CANNED) as mock_followup:
            await agent.execute(_make_task("daily follow up on stale leads", source="scheduler"))

        mock_followup.assert_called_once()

    @pytest.mark.asyncio
    async def test_pitch_deck_keyword_routes_to_pitch_deck(self):
        """'pitch deck' → _pitch_deck_workflow."""
        agent = _make_sales_agent()
        with patch.object(agent, "_pitch_deck_workflow",
                          new_callable=AsyncMock, return_value=_CANNED) as mock_pitch:
            await agent.execute(_make_task("create a pitch deck for Acme Corp"))

        mock_pitch.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_message_falls_back_to_general_sales(self):
        """Unrecognised message → _general_sales_workflow."""
        agent = _make_sales_agent()
        with patch.object(agent, "_general_sales_workflow",
                          new_callable=AsyncMock, return_value=_CANNED) as mock_general:
            await agent.execute(_make_task("what is our Q1 revenue target?"))

        mock_general.assert_called_once()
