"""
ManagementAgent — Cross-department KPI dashboards and executive reporting.

Handles: KPI dashboards across all departments, LLM usage cost reports,
team activity summaries, audit log review, and financial overviews.

Sources:
  - mobile: User request from Management department
  - scheduler: Weekly KPI report (Monday 9AM SGT)
"""

import logging

from app.agents.base_agent import BaseAgent
from app.llm import llm_manager as llm_mod

logger = logging.getLogger("mezzofy.agents.management")

_TRIGGER_KEYWORDS = {
    "kpi", "dashboard", "report", "overview", "performance", "cross-department",
    "audit", "cost", "usage", "management", "executive", "ceo", "summary",
    "all departments", "company-wide", "metrics", "revenue", "team",
}


class ManagementAgent(BaseAgent):
    """
    Aggregates cross-department data into executive dashboards and KPI reports.

    Can handle any department's data since management has read-all access.
    Generates branded PDF reports and delivers via Teams + Outlook.

    Key workflows:
    - Cross-department KPI dashboard on demand
    - Automated weekly KPI report (Monday 9AM SGT via scheduler)
    """

    def can_handle(self, task: dict) -> bool:
        department = task.get("department", "").lower()
        if department == "management":
            return True
        message = task.get("message", "").lower()
        return any(kw in message for kw in _TRIGGER_KEYWORDS)

    async def execute(self, task: dict) -> dict:
        source = task.get("source", "mobile")
        event = task.get("event", "")

        if source == "scheduler" and "kpi_report" in event:
            return await self._weekly_kpi_workflow(task)
        return await self._kpi_dashboard_workflow(task)

    # ── Sub-workflows ─────────────────────────────────────────────────────────

    async def _kpi_dashboard_workflow(self, task: dict) -> dict:
        """Mobile: generate cross-department KPI dashboard."""
        try:
            skill = self._load_skill("data_analysis")
        except ValueError as e:
            return self._err(str(e))

        message = task.get("message", "")
        date_range = self._extract_date_range(message)
        tools_called = []
        department_data: dict = {}

        # Query each department's metrics
        for dept in ("sales", "support", "finance"):
            result = await skill.analyze_data(
                query=dept,
                analysis_type="summary",
                date_range=date_range,
            )
            tools_called.append("analyze_data")
            if result.get("success"):
                department_data[dept] = result.get("output", {})

        # LLM usage costs
        from app.tools.database.db_ops import DatabaseOps
        db = DatabaseOps(self.config)
        usage_result = await db.execute(
            "query_analytics",
            metric="llm_usage",
            start_date=None,
            end_date=None,
        )
        tools_called.append("query_analytics")
        if usage_result.get("success"):
            department_data["llm_usage"] = usage_result.get("output", {})

        # LLM synthesizes into executive summary
        llm_prompt = (
            f"You are the COO of Mezzofy. Write an executive KPI dashboard summary "
            f"covering all departments. Include:\n"
            f"1. Sales: pipeline, leads, deals closed\n"
            f"2. Support: tickets, SLA compliance, top issues\n"
            f"3. Finance: revenue, expenses, key ratios\n"
            f"4. AI usage: tokens consumed, estimated cost\n"
            f"5. Overall health assessment and top 3 recommendations\n\n"
            f"Data: {str(department_data)[:4000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": llm_prompt}],
            task_context=task,
        )
        summary = llm_result.get("content", "KPI dashboard generated.")

        # Generate PDF
        artifacts = []
        from app.tools.document.pdf_ops import PDFOps
        pdf = PDFOps(self.config)
        pdf_result = await pdf.execute(
            "create_pdf",
            content=summary,
            title="KPI Dashboard",
        )
        tools_called.append("create_pdf")
        if pdf_result.get("success") and pdf_result.get("output"):
            artifacts.append({
                "name": "kpi_dashboard.pdf",
                "path": pdf_result["output"],
                "type": "pdf",
            })

        return self._ok(content=summary, artifacts=artifacts, tools_called=tools_called)

    async def _weekly_kpi_workflow(self, task: dict) -> dict:
        """Scheduler: weekly KPI report → Teams + CEO/COO email."""
        try:
            skill = self._load_skill("data_analysis")
        except ValueError as e:
            return self._err(str(e))

        tools_called = []
        department_data: dict = {}

        for dept in ("sales", "support", "finance"):
            result = await skill.analyze_data(
                query=dept,
                analysis_type="summary",
                date_range="last_7_days",
            )
            tools_called.append("analyze_data")
            if result.get("success"):
                department_data[dept] = result.get("output", {})

        llm_prompt = (
            f"Write the weekly Mezzofy KPI report for the executive team. "
            f"Include all departments, highlight wins and concerns, "
            f"provide 3 recommended actions for next week.\n\n"
            f"Data: {str(department_data)[:4000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": llm_prompt}],
            task_context=task,
        )
        summary = llm_result.get("content", "Weekly KPI report generated.")

        artifacts = []
        from app.tools.document.pdf_ops import PDFOps
        pdf = PDFOps(self.config)
        pdf_result = await pdf.execute("create_pdf", content=summary, title="Weekly KPI Report")
        tools_called.append("create_pdf")
        if pdf_result.get("success") and pdf_result.get("output"):
            artifacts.append({
                "name": "weekly_kpi_report.pdf",
                "path": pdf_result["output"],
                "type": "pdf",
            })

        # Deliver to Teams and email leadership
        await self._deliver_to_teams(
            channel="#management",
            message=f"📊 Weekly KPI Report\n\n{summary[:500]}...",
            attachments=artifacts,
        )

        notifications = self.config.get("notifications", {})
        for recipient_key in ("ceo_email", "coo_email"):
            email = notifications.get(recipient_key, "")
            if email:
                await self._send_email(
                    to=email,
                    subject="Weekly KPI Report — Mezzofy",
                    body=f"<h2>Weekly KPI Report</h2><p>{summary}</p>",
                    attachments=artifacts,
                )

        return self._ok(content=summary, artifacts=artifacts, tools_called=tools_called)

    def _extract_date_range(self, message: str) -> str:
        msg = message.lower()
        if "this month" in msg or "monthly" in msg:
            return "this_month"
        if "last month" in msg:
            return "last_month"
        if "this quarter" in msg or "quarterly" in msg:
            return "last_quarter"
        if "this year" in msg or "annual" in msg:
            return "last_year"
        return "last_7_days"
