"""
ManagementAgent — Cross-department KPI dashboards and executive reporting.

Handles: KPI dashboards across all departments, LLM usage cost reports,
team activity summaries, audit log review, and financial overviews.

Sources:
  - mobile: User request from Management department
  - scheduler: Weekly KPI report (Monday 9AM SGT)
"""

import logging
from datetime import date

from app.agents.base_agent import BaseAgent
from app.llm import llm_manager as llm_mod

logger = logging.getLogger("mezzofy.agents.management")

_TRIGGER_KEYWORDS = {
    "kpi", "dashboard", "report", "overview", "performance", "cross-department",
    "audit", "cost", "usage", "management", "executive", "ceo", "summary",
    "all departments", "company-wide", "metrics", "revenue", "team",
    "linkedin",
}

# Subset of keywords that indicate an explicit KPI/dashboard request in execute().
# Keep this list SPECIFIC — generic words like "summary", "report", "usage",
# "weekly" must NOT appear here or they will intercept unrelated tasks (e.g.
# "email summary", "expense report", "LLM usage stats") and wrongly trigger
# the KPI dashboard workflow instead of _general_response.
_KPI_KEYWORDS = {
    "kpi", "dashboard", "performance", "metrics", "executive",
    "audit", "cross-department", "all departments", "company-wide",
    "revenue",
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
        is_management = task.get("department", "").lower() == "management"
        message = task.get("message", "").lower()
        has_keyword = any(kw in message for kw in _TRIGGER_KEYWORDS)
        return is_management and has_keyword

    async def execute(self, task: dict) -> dict:
        source = task.get("source", "mobile")
        event = task.get("event", "")
        message = task.get("message", "").lower()

        # v2.0: Cross-department orchestration — check BEFORE any single-agent routing
        # Only active when AgentRegistry is loaded (agents table must exist)
        if self._is_cross_department_task(task):
            return await self.plan_and_orchestrate(task)

        # Scheduler: weekly KPI report
        if source == "scheduler" and "kpi_report" in event:
            return await self._weekly_kpi_workflow(task)

        # File or image attached → analysis takes priority over keyword matching
        if task.get("anthropic_file_id") or task.get("input_type") in ("file", "image"):
            return await self._general_response(task)

        # Mobile/Teams: only run KPI workflow if message is clearly about KPIs
        if any(kw in message for kw in _KPI_KEYWORDS):
            return await self._kpi_dashboard_workflow(task)

        # LinkedIn prospecting workflow — only when "linkedin" is explicitly mentioned
        if "linkedin" in message:
            return await self._prospecting_workflow(task)

        # General question — respond directly via LLM without KPI workflow
        return await self._general_response(task)

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
        today = date.today().strftime("%B %d, %Y")
        llm_prompt = (
            f"You are the COO of Mezzofy. Write an executive KPI dashboard summary "
            f"covering all departments. Include:\n"
            f"1. Sales: pipeline, leads, deals closed\n"
            f"2. Support: tickets, SLA compliance, top issues\n"
            f"3. Finance: revenue, expenses, key ratios\n"
            f"4. AI usage: tokens consumed, estimated cost\n"
            f"5. Overall health assessment and top 3 recommendations\n\n"
            f"Generated: {today}\n"
            f"Data: {str(department_data)[:4000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": llm_prompt}],
            task_context=task,
        )
        summary = llm_result.get("content", "KPI dashboard generated.")

        # Generate PDF
        artifacts = []
        title = "KPI Dashboard"
        skill_ok = False
        try:
            skill_result = await llm_mod.get().generate_document_with_skill(
                skill_id="pdf",
                prompt=summary,
                context_data=None,
                task_context=task,
            )
            if skill_result.get("success") and skill_result.get("file_ids"):
                from app.context.artifact_manager import download_from_anthropic
                artifact = await download_from_anthropic(
                    db=task["db"],
                    file_id=skill_result["file_ids"][0],
                    user_id=task["user_id"],
                    session_id=task["session_id"],
                    skill_id="pdf",
                    suggested_name=title,
                )
                artifacts.append(artifact)
                tools_called.append("create_pdf")
                skill_ok = True
        except Exception as e:
            logger.warning(f"Skill generation failed (exception): {e}")

        if not skill_ok:
            logger.warning(f"Skill generation failed, falling back to PDFOps")
            from app.tools.document.pdf_ops import PDFOps
            pdf = PDFOps(self.config)
            pdf_result = await pdf.execute(
                "create_pdf",
                content=summary,
                title=title,
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
        title = "Weekly KPI Report"
        skill_ok = False
        try:
            skill_result = await llm_mod.get().generate_document_with_skill(
                skill_id="pdf",
                prompt=summary,
                context_data=None,
                task_context=task,
            )
            if skill_result.get("success") and skill_result.get("file_ids"):
                from app.context.artifact_manager import download_from_anthropic
                artifact = await download_from_anthropic(
                    db=task["db"],
                    file_id=skill_result["file_ids"][0],
                    user_id=task["user_id"],
                    session_id=task["session_id"],
                    skill_id="pdf",
                    suggested_name=title,
                )
                artifacts.append(artifact)
                tools_called.append("create_pdf")
                skill_ok = True
        except Exception as e:
            logger.warning(f"Skill generation failed (exception): {e}")

        if not skill_ok:
            logger.warning(f"Skill generation failed, falling back to PDFOps")
            from app.tools.document.pdf_ops import PDFOps
            pdf = PDFOps(self.config)
            pdf_result = await pdf.execute("create_pdf", content=summary, title=title)
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

    async def _prospecting_workflow(self, task: dict) -> dict:
        """LinkedIn search → CRM save → compose + send intro emails."""
        try:
            li_skill = self._load_skill("linkedin_prospecting")
            email_skill = self._load_skill("email_outreach")
        except ValueError as e:
            return self._err(str(e))

        message = task.get("message", "")
        tools_called = []

        # Step 1: LinkedIn search
        li_result = await li_skill.search_linkedin(
            query=message,
            search_type="company",
            max_results=10,
        )
        tools_called.append("linkedin_search")
        if not li_result.get("success"):
            return self._err(f"LinkedIn search failed: {li_result.get('error')}")

        # LinkedIn tool returns {"results": [...], "count": N, "query": "..."}
        leads = li_result.get("output", {}).get("results", [])
        if not isinstance(leads, list):
            leads = []

        # Step 2: Save to CRM
        from app.tools.database.crm_ops import CRMOps
        crm = CRMOps(self.config)
        saved_count = 0
        user_id = task.get("user_id", "system")
        for lead in leads[:10]:
            crm_result = await crm.execute(
                "create_lead",
                company_name=str(lead.get("name", "Unknown")),
                contact_name=str(lead.get("name", "Unknown")),
                contact_email="",
                industry="",
                source="linkedin",
                assigned_to=user_id,
                notes=str(lead.get("subtitle", ""))[:500],
                source_ref=str(lead.get("url", "")),
            )
            if crm_result.get("success"):
                saved_count += 1
        tools_called.append("create_lead")

        # Step 3: Compose and send intro emails (skip gracefully if no permission)
        sent_count = 0
        try:
            self._require_permission(task, "email_send")
            for lead in leads[:5]:
                email_addr = lead.get("email", "")
                if not email_addr:
                    continue
                compose_result = await email_skill.compose_email(
                    template="intro",
                    recipient_name=str(lead.get("name", "there")),
                    recipient_email=str(email_addr),
                    company_name=str(lead.get("name", "")),
                )
                if compose_result.get("success"):
                    composed = compose_result["output"]
                    send_result = await email_skill.send_email(
                        to=str(email_addr),
                        subject=composed["subject"],
                        body_html=composed["body_html"],
                    )
                    if send_result.get("success"):
                        sent_count += 1
            tools_called.extend(["compose_email", "send_email"])
        except PermissionError:
            pass  # Email outreach skipped — user lacks email_send permission

        summary = (
            f"LinkedIn prospecting complete:\n"
            f"- Found {len(leads)} leads\n"
            f"- Saved {saved_count} to CRM\n"
            f"- Sent {sent_count} intro emails"
        )
        return self._ok(content=summary, tools_called=tools_called)

    # ── v2.0: Orchestration ────────────────────────────────────────────────────

    def _is_cross_department_task(self, task: dict) -> bool:
        """
        Return True if the task requires skills from more than one agent.

        Heuristics:
        - Explicit multi-department keywords: "and sales", "and finance", etc.
        - Comparison keywords: "compare", "vs", "versus", "across departments"
        - Cross-department phrases that signal multiple specialists needed
        - AgentRegistry must be loaded — if not, returns False (safe fallback)
        """
        from app.agents.agent_registry import agent_registry as _registry
        if not _registry.is_loaded():
            return False  # Registry not available — fall through to existing logic

        message = task.get("message", "").lower()
        _CROSS_DEPT_KEYWORDS = {
            # Comparison signals
            "compare", "versus", " vs ", "compared to", "comparison between",
            # Explicit multi-department phrases
            "across departments", "all departments", "every department",
            "cross-department", "cross department", "multiple departments",
            "both departments", "combined report",
            # Explicit "and <dept>" / "<dept> and" pairs (existing agents)
            "and sales", "and finance", "and marketing", "and support", "and hr",
            "sales and", "finance and", "marketing and", "support and", "hr and",
            # Agent names added in v2.0 (research, developer, legal)
            "and research", "and developer", "and legal",
            "research and", "developer and", "legal and",
            "research & ", "developer & ", "legal & ",
            " & research", " & developer", " & legal",
            # Natural conjunction patterns
            "sales & finance", "sales & support", "sales & marketing", "sales & hr",
            "finance & sales", "finance & support", "finance & marketing", "finance & hr",
            "support & sales", "support & finance", "support & marketing", "support & hr",
            "from hr and", "from finance and", "from sales and", "from support and",
            "from marketing and",
            "hr and finance", "hr and sales", "hr and support", "hr and marketing",
            # Whole-company / all-teams requests
            "each department", "each team", "every team", "all teams",
            "whole company", "entire company", "entire organization", "whole organization",
            "full company", "across the company", "across the organization", "across teams",
            "business overview", "company overview", "company-wide", "org-wide",
            "all agents", "each agent",
            # Implicit multi-agent signals
            "coordinate", "collaborate", "full picture", "big picture",
            "consolidated", "combined view", "360 view", "360-degree",
        }
        return any(kw in message for kw in _CROSS_DEPT_KEYWORDS)

    async def plan_and_orchestrate(self, task: dict) -> dict:
        """
        v2.5: Thin dispatcher — delegates full orchestration to PlanManager +
        orchestrator_tasks Celery pipeline.

        Creates an ExecutionPlan via PlanManager (Claude API decomposes the goal),
        fires execute_plan_task.delay() and returns immediately. The user receives
        WebSocket progress notifications as each step completes, and a final
        synthesised response when all steps are done.
        """
        from app.orchestrator.plan_manager import plan_manager
        from app.agents.agent_registry import agent_registry as _registry

        active_agents = _registry.all_active()
        if not active_agents:
            logger.error(
                "plan_and_orchestrate: AgentRegistry has no agents — cannot create plan. "
                "Check if agents table exists in DB (run scripts/migrate.py)."
            )
            return self._ok(
                content=(
                    "I need to coordinate multiple teams for this request, but my agent "
                    "roster isn't loaded. Please ask an administrator to verify the agents "
                    "database table exists (run scripts/migrate.py on the server)."
                ),
                tools_called=["plan_and_orchestrate"],
            )

        plan = await plan_manager.create_plan(
            goal=task.get("message", ""),
            user_id=task.get("user_id", ""),
            session_id=task.get("session_id", ""),
            task=task,
            available_agents=active_agents,
        )

        # Fire-and-forget: Celery takes over the full PLAN→DELEGATE→AGGREGATE cycle
        from app.tasks.orchestrator_tasks import execute_plan_task
        execute_plan_task.delay(plan.plan_id)

        # Return immediately — user will receive WS updates as steps complete
        return self._ok(
            content=(
                f"I'm working on that. I'll send you updates as each step completes. "
                f"Plan ID: {plan.plan_id}"
            ),
            tools_called=["plan_and_orchestrate"],
        )

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
