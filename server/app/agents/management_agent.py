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
    "linkedin", "prospect", "lead", "find",
}

# Subset of keywords that indicate an explicit KPI/dashboard request in execute()
_KPI_KEYWORDS = {
    "kpi", "dashboard", "report", "overview", "performance", "metrics", "executive",
    "audit", "cost", "usage", "cross-department", "all departments", "company-wide",
    "revenue", "summary", "weekly",
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

        # LinkedIn prospecting workflow
        if any(w in message for w in ("linkedin", "prospect", "lead", "find")):
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
        except Exception as e:
            logger.warning(f"Skill generation failed, falling back to PDFOps: {e}")
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
        except Exception as e:
            logger.warning(f"Skill generation failed, falling back to PDFOps: {e}")
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
            "compare", "versus", " vs ", "across departments", "all departments",
            "cross-department", "cross department",
            "and sales", "and finance", "and marketing", "and support", "and hr",
            "sales and", "finance and", "marketing and", "support and", "hr and",
            "both departments", "multiple departments", "every department",
        }
        return any(kw in message for kw in _CROSS_DEPT_KEYWORDS)

    async def plan_and_orchestrate(self, task: dict) -> dict:
        """
        Orchestrate a multi-agent task plan.

        Step 1 — Plan decomposition: LLM breaks down the task into sub-tasks,
                  each assigned to the most capable specialist agent.
        Step 2 — Log the plan in agent_task_log.
        Step 3 — Execute plan: parallel steps fire-and-forget; sequential
                  steps are awaited before the next step runs.
        Step 4 — Synthesise: collect all sub-task result_summaries via LLM.
        Step 5 — Deliver: Teams #management + email to requestor.

        Returns the synthesised executive summary.
        """
        from app.agents.agent_registry import agent_registry as _registry
        message = task.get("message", "")
        user_id = task.get("user_id", "")

        # ── Step 1: LLM decomposes task ───────────────────────────────────────
        active_agents = _registry.all_active()
        agent_summary = [
            {"id": a["id"], "department": a["department"],
             "skills": a.get("skills", [])}
            for a in active_agents
        ]

        today = date.today().strftime("%Y-%m-%d")
        decompose_prompt = (
            f"You are the Management Agent (orchestrator) for Mezzofy.\n"
            f"Today is {today}.\n\n"
            f"Break down this task into sub-tasks, each assigned to exactly one "
            f"specialist agent. Return ONLY valid JSON — an array of objects:\n"
            f'[{{"step": 1, "agent_id": "agent_sales", "task_description": "...", '
            f'"depends_on_step": null}}, ...]\n\n'
            f"Available agents:\n{agent_summary}\n\n"
            f"Task: {message}"
        )

        plan_json = []
        try:
            llm_result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": decompose_prompt}],
                task_context=task,
            )
            import json as _json
            raw = llm_result.get("content", "[]")
            # Extract JSON array from the response
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                plan_json = _json.loads(raw[start:end])
        except Exception as e:
            logger.warning(f"plan_and_orchestrate: LLM decomposition failed: {e}")
            # Fallback: return as KPI dashboard workflow
            return await self._kpi_dashboard_workflow(task)

        if not plan_json or not isinstance(plan_json, list):
            logger.info("plan_and_orchestrate: empty plan, falling back to KPI workflow")
            return await self._kpi_dashboard_workflow(task)

        # ── Step 2: Log the plan ──────────────────────────────────────────────
        orchestration_task_id = await self.log_task_start(task)
        if orchestration_task_id:
            try:
                import json as _json2
                from app.core.database import AsyncSessionLocal
                from sqlalchemy import text
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        text("""
                            UPDATE agent_task_log
                            SET task_plan = :plan::jsonb
                            WHERE id = :id
                        """),
                        {"plan": _json2.dumps(plan_json), "id": orchestration_task_id},
                    )
                    await db.commit()
            except Exception as e:
                logger.warning(f"plan_and_orchestrate: failed to save task_plan: {e}")

        # ── Step 3: Execute plan ──────────────────────────────────────────────
        step_results: dict[int, dict] = {}
        for step in sorted(plan_json, key=lambda s: s.get("step", 0)):
            step_num = step.get("step", 0)
            target_agent_id = step.get("agent_id", "")
            task_desc = step.get("task_description", message)
            depends_on = step.get("depends_on_step")

            # Build sub-task
            sub_task = {
                **{k: v for k, v in task.items()
                   if k not in ("_config", "_progress_callback")},
                "message": task_desc,
                "source": "agent_delegation",
                "_requesting_agent_id": "agent_management",
                "_parent_task_id": orchestration_task_id,
            }

            if depends_on is not None:
                # Sequential — await the dependency's delegation result
                prior = step_results.get(depends_on, {})
                prior_summary = prior.get("result_summary", "")
                if prior_summary:
                    sub_task["message"] = (
                        f"{task_desc}\n\nContext from prior step: {prior_summary[:500]}"
                    )
                delegation = await self.delegate_task(
                    target_agent_id, sub_task, orchestration_task_id
                )
                if delegation.get("task_id"):
                    awaited = await self.await_delegation(
                        delegation["task_id"], timeout_seconds=180
                    )
                    step_results[step_num] = awaited
            else:
                # Parallel — fire and forget (no await)
                delegation = await self.delegate_task(
                    target_agent_id, sub_task, orchestration_task_id
                )
                step_results[step_num] = {"task_id": delegation.get("task_id", ""), "status": "queued"}

        # ── Step 4: Synthesise results ────────────────────────────────────────
        completed_summaries = [
            f"Step {k}: {v.get('result_summary', '(in progress)')}"
            for k, v in sorted(step_results.items())
            if v.get("result_summary")
        ]
        synthesis_content = ""
        if completed_summaries:
            synthesis_prompt = (
                f"You are the COO of Mezzofy. Synthesise these sub-task results "
                f"into a single executive summary (max 500 words):\n\n"
                + "\n".join(completed_summaries)
            )
            try:
                synth_result = await llm_mod.get().chat(
                    messages=[{"role": "user", "content": synthesis_prompt}],
                    task_context=task,
                )
                synthesis_content = synth_result.get("content", "")
            except Exception as e:
                logger.warning(f"plan_and_orchestrate: synthesis LLM failed: {e}")
                synthesis_content = "\n".join(completed_summaries)
        else:
            synthesis_content = (
                f"Orchestration plan dispatched to {len(plan_json)} specialist agents. "
                f"Results will be delivered when sub-tasks complete."
            )

        # ── Step 5: Deliver ───────────────────────────────────────────────────
        try:
            await self._deliver_to_teams(
                channel="#management",
                message=f"🤖 Orchestrated Task Complete\n\n{synthesis_content[:500]}",
            )
        except Exception as e:
            logger.warning(f"plan_and_orchestrate: Teams delivery failed: {e}")

        # Update log: completed
        if orchestration_task_id:
            await self.log_task_complete(
                orchestration_task_id,
                {"content": synthesis_content, "artifacts": []},
            )

        return self._ok(
            content=synthesis_content,
            tools_called=["plan_and_orchestrate", "delegate_task"],
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
