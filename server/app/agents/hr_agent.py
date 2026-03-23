"""
HRAgent — HR operations, workforce management, and people analytics.

Handles: payroll queries, headcount reports, leave/attendance tracking,
recruitment pipeline, onboarding/offboarding workflows, and performance reviews.

Sources:
  - mobile: User request from HR department
  - scheduler: Weekly HR summary (Friday 5PM SGT), Monthly headcount (1st of month, 9AM SGT)
  - webhook: employee_onboarded, employee_offboarded, leave_request_submitted
"""

import logging
from datetime import date

from app.agents.base_agent import BaseAgent
from app.llm import llm_manager as llm_mod

logger = logging.getLogger("mezzofy.agents.hr")

# Keywords that trigger HR Agent (for cross-department routing)
_TRIGGER_KEYWORDS = {
    "hr", "payroll", "salary", "leave", "attendance", "headcount", "employee",
    "staff", "recruit", "hiring", "onboard", "offboard", "performance review",
    "appraisal", "resignation", "termination", "workforce", "people ops",
}


class HRAgent(BaseAgent):
    """
    Manages HR operations: workforce data, payroll, leave, and recruitment.

    Key workflows:
    - Payroll/salary queries on demand (mobile)
    - Leave and attendance lookups (mobile)
    - Recruitment pipeline summaries (mobile)
    - Automated weekly HR summary (Friday 5PM SGT via scheduler)
    - Automated monthly headcount report (1st of month, 9AM SGT via scheduler)
    - Employee onboarding checklist (webhook: employee_onboarded)
    - Employee offboarding summary (webhook: employee_offboarded)
    """

    def can_handle(self, task: dict) -> bool:
        return task.get("department", "").lower() == "hr"

    async def execute(self, task: dict) -> dict:
        source = task.get("source", "mobile")
        event = task.get("event", "")
        msg = task.get("message", "").lower()

        # Scheduler paths
        if source == "scheduler":
            if "weekly_hr_summary" in event:
                return await self._weekly_hr_summary_workflow(task)
            if "monthly_headcount" in event:
                return await self._headcount_report_workflow(task)

        # Webhook paths
        if source == "webhook":
            if event == "employee_onboarded":
                return await self._onboarding_workflow(task)
            if event == "employee_offboarded":
                return await self._offboarding_workflow(task)

        # Mobile/Teams keyword routing
        if any(kw in msg for kw in ("payroll", "salary")):
            return await self._payroll_query_workflow(task)
        if any(kw in msg for kw in ("leave", "attendance")):
            return await self._leave_query_workflow(task)
        if any(kw in msg for kw in ("recruit", "hiring", "headcount")):
            return await self._recruitment_query_workflow(task)

        return await self._general_response(task)

    # ── Mobile workflows ───────────────────────────────────────────────────────

    async def _payroll_query_workflow(self, task: dict) -> dict:
        """Mobile: answer payroll/salary queries using DB data + LLM."""
        from app.tools.database.db_ops import DatabaseOps
        db = DatabaseOps(self.config)

        tools_called = []
        today = date.today().strftime("%B %d, %Y")

        db_result = await db.execute(
            "query_analytics",
            metric="payroll_summary",
            start_date=None,
            end_date=None,
        )
        tools_called.append("query_analytics")
        payroll_data = db_result.get("output", {}) if db_result.get("success") else {}

        user_context = task.get("extracted_text") or task.get("message", "")
        prompt = (
            f"You are an HR analyst at Mezzofy. Answer the following payroll/salary query "
            f"using the data provided. Be concise and accurate.\n\n"
            f"Date: {today}\n"
            f"Query: {user_context}\n"
            f"Payroll data: {str(payroll_data)[:3000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            task_context=task,
        )
        content = llm_result.get("content", "Payroll information retrieved.")

        return self._ok(content=content, tools_called=tools_called)

    async def _leave_query_workflow(self, task: dict) -> dict:
        """Mobile: answer leave/attendance queries using DB data + LLM."""
        from app.tools.database.db_ops import DatabaseOps
        db = DatabaseOps(self.config)

        tools_called = []
        today = date.today().strftime("%B %d, %Y")

        db_result = await db.execute(
            "query_analytics",
            metric="leave_attendance",
            start_date=None,
            end_date=None,
        )
        tools_called.append("query_analytics")
        leave_data = db_result.get("output", {}) if db_result.get("success") else {}

        user_context = task.get("extracted_text") or task.get("message", "")
        prompt = (
            f"You are an HR analyst at Mezzofy. Answer the following leave/attendance query "
            f"accurately. Highlight any anomalies or pending approvals.\n\n"
            f"Date: {today}\n"
            f"Query: {user_context}\n"
            f"Leave and attendance data: {str(leave_data)[:3000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            task_context=task,
        )
        content = llm_result.get("content", "Leave and attendance information retrieved.")

        return self._ok(content=content, tools_called=tools_called)

    async def _recruitment_query_workflow(self, task: dict) -> dict:
        """Mobile: summarize recruitment pipeline or headcount data."""
        from app.tools.database.db_ops import DatabaseOps
        db = DatabaseOps(self.config)

        tools_called = []
        today = date.today().strftime("%B %d, %Y")

        db_result = await db.execute(
            "query_analytics",
            metric="recruitment_pipeline",
            start_date=None,
            end_date=None,
        )
        tools_called.append("query_analytics")
        pipeline_data = db_result.get("output", {}) if db_result.get("success") else {}

        user_context = task.get("extracted_text") or task.get("message", "")
        prompt = (
            f"You are an HR analyst at Mezzofy. Summarize the current recruitment pipeline "
            f"and headcount status. Include open roles, candidates in progress, and key metrics.\n\n"
            f"Date: {today}\n"
            f"Query: {user_context}\n"
            f"Pipeline data: {str(pipeline_data)[:3000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            task_context=task,
        )
        content = llm_result.get("content", "Recruitment pipeline summary generated.")

        return self._ok(content=content, tools_called=tools_called)

    # ── Scheduler workflows ────────────────────────────────────────────────────

    async def _weekly_hr_summary_workflow(self, task: dict) -> dict:
        """Scheduler (Friday 5PM SGT): weekly HR summary → Teams #hr + HR manager email."""
        from app.tools.database.db_ops import DatabaseOps

        db = DatabaseOps(self.config)
        tools_called = []
        today = date.today().strftime("%B %d, %Y")

        # Gather weekly HR metrics
        metrics = {}
        for metric in ("leave_attendance", "recruitment_pipeline", "payroll_summary"):
            result = await db.execute(
                "query_analytics", metric=metric, start_date=None, end_date=None
            )
            tools_called.append("query_analytics")
            if result.get("success"):
                metrics[metric] = result.get("output", {})

        prompt = (
            f"You are the HR Director at Mezzofy. Write the weekly HR summary report "
            f"covering the past 7 days. Include:\n"
            f"1. Headcount changes (new hires, departures)\n"
            f"2. Leave and attendance highlights\n"
            f"3. Recruitment pipeline status (open roles, interviews, offers)\n"
            f"4. Payroll processing status\n"
            f"5. Key action items for next week\n\n"
            f"Generated: {today}\n"
            f"Data: {str(metrics)[:4000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            task_context=task,
        )
        summary = llm_result.get("content", "Weekly HR summary generated.")

        # Generate PDF report
        artifacts = []
        title = "Weekly HR Summary"
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
                    "name": f"weekly_hr_summary_{date.today().strftime('%Y%m%d')}.pdf",
                    "path": pdf_result["output"],
                    "type": "pdf",
                })

        # Deliver to Teams and HR manager email
        await self._deliver_to_teams(
            channel="#hr",
            message=f"📋 Weekly HR Summary\n\n{summary[:500]}...",
            attachments=artifacts,
        )

        hr_manager_email = self.config.get("notifications", {}).get("hr_manager_email", "")
        if hr_manager_email:
            await self._send_email(
                to=hr_manager_email,
                subject=f"Weekly HR Summary — {today}",
                body=f"<h2>Weekly HR Summary</h2><p>{summary}</p>",
                attachments=artifacts,
            )

        return self._ok(content=summary, artifacts=artifacts, tools_called=tools_called)

    async def _headcount_report_workflow(self, task: dict) -> dict:
        """Scheduler (1st of month, 9AM SGT): monthly headcount report → email."""
        from app.tools.database.db_ops import DatabaseOps

        db = DatabaseOps(self.config)
        tools_called = []
        today = date.today().strftime("%B %d, %Y")

        db_result = await db.execute(
            "query_analytics",
            metric="headcount_monthly",
            start_date=None,
            end_date=None,
        )
        tools_called.append("query_analytics")
        headcount_data = db_result.get("output", {}) if db_result.get("success") else {}

        prompt = (
            f"You are the HR Director at Mezzofy. Write the monthly headcount report. Include:\n"
            f"1. Total headcount by department\n"
            f"2. Month-over-month changes (hires, departures, transfers)\n"
            f"3. Attrition rate and key observations\n"
            f"4. Upcoming planned headcount changes\n\n"
            f"Generated: {today}\n"
            f"Data: {str(headcount_data)[:4000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            task_context=task,
        )
        summary = llm_result.get("content", "Monthly headcount report generated.")

        artifacts = []
        title = "Monthly Headcount Report"
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
                    "name": f"headcount_report_{date.today().strftime('%Y%m')}.pdf",
                    "path": pdf_result["output"],
                    "type": "pdf",
                })

        hr_manager_email = self.config.get("notifications", {}).get("hr_manager_email", "")
        if hr_manager_email:
            await self._send_email(
                to=hr_manager_email,
                subject=f"Monthly Headcount Report — {today}",
                body=f"<h2>Monthly Headcount Report</h2><p>{summary}</p>",
                attachments=artifacts,
            )

        return self._ok(content=summary, artifacts=artifacts, tools_called=tools_called)

    # ── Webhook workflows ──────────────────────────────────────────────────────

    async def _onboarding_workflow(self, task: dict) -> dict:
        """Webhook (employee_onboarded): generate onboarding checklist → Teams #hr."""
        tools_called = []
        today = date.today().strftime("%B %d, %Y")

        employee_data = task.get("payload", {})
        employee_name = employee_data.get("name", "New Employee")
        employee_role = employee_data.get("role", "")
        employee_dept = employee_data.get("department", "")

        prompt = (
            f"You are the HR Director at Mezzofy. Generate a detailed onboarding checklist "
            f"for a new employee joining the team. Be thorough and actionable.\n\n"
            f"Date: {today}\n"
            f"Employee: {employee_name}\n"
            f"Role: {employee_role}\n"
            f"Department: {employee_dept}\n\n"
            f"Include: IT setup, access provisioning, team introductions, "
            f"training schedule, and 30/60/90-day milestones."
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            task_context=task,
        )
        checklist = llm_result.get("content", "Onboarding checklist generated.")

        artifacts = []
        title = f"Onboarding Checklist — {employee_name}"
        skill_ok = False
        try:
            skill_result = await llm_mod.get().generate_document_with_skill(
                skill_id="pdf",
                prompt=checklist,
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
                content=checklist,
                title=title,
            )
            tools_called.append("create_pdf")
            if pdf_result.get("success") and pdf_result.get("output"):
                artifacts.append({
                    "name": f"onboarding_checklist_{employee_name.replace(' ', '_').lower()}.pdf",
                    "path": pdf_result["output"],
                    "type": "pdf",
                })

        await self._deliver_to_teams(
            channel="#hr",
            message=(
                f"👋 Welcome {employee_name}!\n\n"
                f"Onboarding checklist has been generated for {employee_name} "
                f"({employee_role}, {employee_dept})."
            ),
            attachments=artifacts,
        )

        return self._ok(content=checklist, artifacts=artifacts, tools_called=tools_called)

    async def _offboarding_workflow(self, task: dict) -> dict:
        """Webhook (employee_offboarded): generate exit summary → Teams #hr."""
        tools_called = []
        today = date.today().strftime("%B %d, %Y")

        employee_data = task.get("payload", {})
        employee_name = employee_data.get("name", "Employee")
        employee_role = employee_data.get("role", "")
        employee_dept = employee_data.get("department", "")
        last_day = employee_data.get("last_day", today)

        prompt = (
            f"You are the HR Director at Mezzofy. Generate a comprehensive offboarding "
            f"summary and checklist for a departing employee.\n\n"
            f"Date: {today}\n"
            f"Employee: {employee_name}\n"
            f"Role: {employee_role}\n"
            f"Department: {employee_dept}\n"
            f"Last Day: {last_day}\n\n"
            f"Include: knowledge transfer steps, access revocation checklist, "
            f"equipment return, final payroll notes, and exit interview scheduling."
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            task_context=task,
        )
        exit_summary = llm_result.get("content", "Exit summary generated.")

        artifacts = []
        title = f"Offboarding Summary — {employee_name}"
        skill_ok = False
        try:
            skill_result = await llm_mod.get().generate_document_with_skill(
                skill_id="pdf",
                prompt=exit_summary,
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
                content=exit_summary,
                title=title,
            )
            tools_called.append("create_pdf")
            if pdf_result.get("success") and pdf_result.get("output"):
                artifacts.append({
                    "name": f"offboarding_summary_{employee_name.replace(' ', '_').lower()}.pdf",
                    "path": pdf_result["output"],
                    "type": "pdf",
                })

        await self._deliver_to_teams(
            channel="#hr",
            message=(
                f"📋 Offboarding: {employee_name}\n\n"
                f"Exit summary generated for {employee_name} ({employee_role}, {employee_dept}). "
                f"Last day: {last_day}."
            ),
            attachments=artifacts,
        )

        return self._ok(content=exit_summary, artifacts=artifacts, tools_called=tools_called)
