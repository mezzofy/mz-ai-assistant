"""
SupportAgent — Ticket analysis, knowledge base, and escalation management.

Handles: support ticket summarization, pattern detection, knowledge base
search, customer response drafting, and escalation recommendations.

Sources:
  - mobile: User request from Support department
  - scheduler: Weekly support summary (Friday 5PM SGT)
  - webhook: New support ticket created in Mezzofy product
"""

import logging

from app.agents.base_agent import BaseAgent
from app.llm import llm_manager as llm_mod

logger = logging.getLogger("mezzofy.agents.support")

_TRIGGER_KEYWORDS = {
    "ticket", "issue", "bug", "complaint", "problem", "escalat", "sla",
    "resolution", "support", "customer complaint", "help desk", "resolve",
    "recurring", "pattern", "response", "knowledge base",
}


class SupportAgent(BaseAgent):
    """
    Analyzes support tickets and generates actionable reports.

    Key workflows:
    - Summarize weekly tickets with pattern detection
    - Automated weekly report delivered to Teams + Outlook
    - New ticket triage via webhook
    """

    def can_handle(self, task: dict) -> bool:
        return task.get("department", "").lower() == "support"

    async def execute(self, task: dict) -> dict:
        source = task.get("source", "mobile")
        event = task.get("event", "")
        message = task.get("message", "")

        if source == "scheduler" and "support_summary" in event:
            return await self._weekly_summary_workflow(task)
        if source == "webhook" and "support_ticket_created" in event:
            return await self._ticket_triage_workflow(task)
        # Only run ticket workflow if message has support/ticket intent.
        if any(kw in message.lower() for kw in _TRIGGER_KEYWORDS):
            return await self._ticket_analysis_workflow(task)
        return await self._general_response(task)

    # ── Sub-workflows ─────────────────────────────────────────────────────────

    async def _ticket_analysis_workflow(self, task: dict) -> dict:
        """Mobile: analyze tickets and return summary."""
        try:
            skill = self._load_skill("data_analysis")
        except ValueError as e:
            return self._err(str(e))

        message = task.get("message", "")
        date_range = self._extract_date_range(message)
        tools_called = []

        # Step 1: Fetch ticket data
        analysis_result = await skill.analyze_data(
            query="support_tickets",
            analysis_type="summary",
            date_range=date_range,
        )
        tools_called.append("analyze_data")

        if not analysis_result.get("success"):
            return self._err(f"Ticket query failed: {analysis_result.get('error')}")

        data = analysis_result.get("output", {})

        # Step 2: LLM identifies patterns and recommendations
        user_context = task.get("extracted_text") or task.get("message", "")
        llm_prompt = (
            f"You are a support manager at Mezzofy. Analyze these support ticket statistics "
            f"and identify:\n"
            f"1. Top recurring issues (top 3)\n"
            f"2. SLA compliance rate\n"
            f"3. Recommended actions to reduce tickets\n\n"
            f"Data: {str(data)[:3000]}"
            + (f"\n\nUser request: {user_context}" if user_context else "")
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": llm_prompt}],
            task_context=task,
        )
        summary = llm_result.get("content", "Analysis complete.")

        # Step 3: Generate PDF report
        artifacts = []
        title = "Support Ticket Analysis"
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
                    "name": "support_analysis.pdf",
                    "path": pdf_result["output"],
                    "type": "pdf",
                })

        return self._ok(content=summary, artifacts=artifacts, tools_called=tools_called)

    async def _weekly_summary_workflow(self, task: dict) -> dict:
        """Scheduler: weekly support summary → Teams + Outlook."""
        try:
            skill = self._load_skill("data_analysis")
        except ValueError as e:
            return self._err(str(e))

        tools_called = []

        analysis_result = await skill.analyze_data(
            query="support_tickets",
            analysis_type="summary",
            date_range="last_7_days",
        )
        tools_called.append("analyze_data")

        data = analysis_result.get("output", {})

        llm_prompt = (
            f"Write a weekly support summary for the Mezzofy support team. "
            f"Include: total tickets, categories, SLA compliance, top issues, and actions.\n\n"
            f"Data: {str(data)[:3000]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": llm_prompt}],
            task_context=task,
        )
        summary = llm_result.get("content", "Weekly summary complete.")

        artifacts = []
        title = "Weekly Support Summary"
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
                    "name": "weekly_support_summary.pdf",
                    "path": pdf_result["output"],
                    "type": "pdf",
                })

        await self._deliver_to_teams(
            channel="#support",
            message=f"📊 Weekly Support Summary\n\n{summary[:500]}...",
            attachments=artifacts,
        )
        mgr_email = self.config.get("notifications", {}).get("support_manager_email", "")
        if mgr_email:
            await self._send_email(
                to=mgr_email,
                subject="Weekly Support Summary",
                body=f"<h2>Weekly Support Summary</h2><p>{summary}</p>",
                attachments=artifacts,
            )

        return self._ok(content=summary, artifacts=artifacts, tools_called=tools_called)

    async def _ticket_triage_workflow(self, task: dict) -> dict:
        """Webhook: new ticket created → classify + alert."""
        payload = task.get("payload", {})
        ticket_id = payload.get("ticket_id", "unknown")
        subject = payload.get("subject", "")
        body = payload.get("body", "")
        tools_called = []

        # LLM classifies severity
        classify_prompt = (
            f"Classify this support ticket. Reply with JSON: "
            f'{{\"severity\": \"low|medium|high|critical\", \"category\": \"billing|technical|feature|other\"}}\n\n'
            f"Subject: {subject}\nBody: {body[:500]}"
        )
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": classify_prompt}],
            task_context=task,
        )
        classification_text = llm_result.get("content", "")

        # Search knowledge base for solution
        try:
            from app.tools.mezzofy.knowledge_ops import KnowledgeOps
            kb = KnowledgeOps(self.config)
            kb_result = await kb.execute("search_knowledge", query=subject)
            tools_called.append("search_knowledge")
            kb_suggestion = kb_result.get("output", "") if kb_result.get("success") else ""
        except Exception:
            kb_suggestion = ""

        # Alert Teams
        severity = "high" if "high" in classification_text or "critical" in classification_text else "normal"
        icon = "🚨" if severity == "high" else "🎫"
        await self._deliver_to_teams(
            channel="#support",
            message=(
                f"{icon} New Ticket #{ticket_id}: {subject}\n"
                f"Classification: {classification_text[:200]}\n"
                f"KB suggestion: {str(kb_suggestion)[:200]}"
            ),
        )

        # Escalate critical tickets
        if severity == "high":
            mgr_email = self.config.get("notifications", {}).get("support_manager_email", "")
            if mgr_email:
                await self._send_email(
                    to=mgr_email,
                    subject=f"[ESCALATION] Ticket #{ticket_id}: {subject}",
                    body=(
                        f"<h2>High-Priority Support Ticket</h2>"
                        f"<p><b>Ticket ID:</b> {ticket_id}</p>"
                        f"<p><b>Subject:</b> {subject}</p>"
                        f"<p><b>Classification:</b> {classification_text}</p>"
                        f"<p><b>Body:</b> {body[:1000]}</p>"
                    ),
                )

        return self._ok(
            content=f"Ticket #{ticket_id} triaged: {classification_text[:200]}",
            tools_called=tools_called,
        )

    def _extract_date_range(self, message: str) -> str:
        msg = message.lower()
        if "this week" in msg or "weekly" in msg:
            return "last_7_days"
        if "last month" in msg or "monthly" in msg:
            return "last_month"
        return "last_7_days"
