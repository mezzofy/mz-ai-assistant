"""
FinanceAgent — Financial statements, reports, and budgets.

Handles: P&L statements, balance sheets, cash flow reports, expense reports,
financial ratios, and monthly executive summaries.

Sources:
  - mobile: User request from Finance department
  - scheduler: Monthly financial summary (1st of month, 8AM SGT)
"""

import logging
from typing import Optional

from app.agents.base_agent import BaseAgent
from app.llm import llm_manager as llm_mod

logger = logging.getLogger("mezzofy.agents.finance")

# Keywords that trigger Finance Agent
_TRIGGER_KEYWORDS = {
    "p&l", "pnl", "profit", "loss", "revenue", "expense", "balance sheet",
    "cash flow", "invoice", "budget", "financial", "statement", "fiscal",
    "quarterly", "annual", "earnings", "cost", "margin", "ebitda", "ratio",
}


class FinanceAgent(BaseAgent):
    """
    Generates financial statements and reports from the database.

    Workflow:
    1. Load financial_reporting skill
    2. Query financial data from database
    3. Format and analyze with LLM
    4. Generate PDF report
    5. Deliver via mobile response or Teams/Outlook (scheduled)
    """

    def can_handle(self, task: dict) -> bool:
        department = task.get("department", "").lower()
        if department == "finance":
            return True
        message = task.get("message", "").lower()
        return any(kw in message for kw in _TRIGGER_KEYWORDS)

    async def execute(self, task: dict) -> dict:
        source = task.get("source", "mobile")
        message = task.get("message", "")

        try:
            skill = self._load_skill("financial_reporting")
        except ValueError as e:
            return self._err(str(e))

        # Detect report type from message
        report_type = self._detect_report_type(message)
        date_bounds = self._extract_date_range(message)

        try:
            # Step 1: Query financial data
            query_result = await skill.financial_query(
                report_type=report_type,
                start_date=date_bounds["start"],
                end_date=date_bounds["end"],
                department=task.get("department"),
            )

            if not query_result.get("success"):
                return self._err(f"Financial data query failed: {query_result.get('error')}")

            data = query_result.get("output", {})

            # Step 2: LLM analyzes and summarizes
            analysis_prompt = (
                f"You are a financial analyst at Mezzofy. Analyze this {report_type} data "
                f"for {date_bounds['start']} to {date_bounds['end']} and write a concise "
                f"executive summary with key highlights, trends, and recommendations.\n\n"
                f"Data: {str(data)[:3000]}"
            )
            llm_result = await llm_mod.get().chat(
                messages=[{"role": "user", "content": analysis_prompt}],
                task_context=task,
            )
            summary = llm_result.get("content", "Analysis complete.")

            # Step 3: Generate PDF
            format_result = await skill.financial_format(data=data, format="pdf")
            artifacts = []
            if format_result.get("success") and format_result.get("output"):
                artifacts.append({
                    "name": f"financial_{report_type}_{date_bounds['start']}.pdf",
                    "path": format_result["output"],
                    "type": "pdf",
                })

            # Step 4: Deliver (scheduled = Teams + Outlook)
            if self._is_automated(task):
                await self._deliver_to_teams(
                    channel="#finance",
                    message=f"📊 Monthly Financial Summary\n\n{summary}",
                    attachments=artifacts,
                )
                cfo_email = self.config.get("notifications", {}).get("cfo_email", "")
                if cfo_email:
                    await self._send_email(
                        to=cfo_email,
                        subject=f"Monthly Financial Summary — {date_bounds['start']}",
                        body=f"<h2>Monthly Financial Summary</h2><p>{summary}</p>",
                        attachments=artifacts,
                    )

            return self._ok(
                content=summary,
                artifacts=artifacts,
                tools_called=["financial_query", "financial_format"],
            )

        except PermissionError as e:
            return self._err(str(e))
        except Exception as e:
            logger.error(f"FinanceAgent.execute failed: {e}")
            return self._err(f"Financial report generation failed: {e}")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _detect_report_type(self, message: str) -> str:
        msg = message.lower()
        if any(w in msg for w in ("p&l", "pnl", "profit", "loss", "income")):
            return "pnl"
        if any(w in msg for w in ("balance sheet", "assets", "liabilities")):
            return "balance_sheet"
        if any(w in msg for w in ("cash flow", "cashflow", "liquidity")):
            return "cash_flow"
        if any(w in msg for w in ("expense", "cost", "spending")):
            return "expenses"
        return "pnl"

    def _extract_date_range(self, message: str) -> dict:
        from datetime import date, timedelta
        today = date.today()
        msg = message.lower()
        if "last month" in msg or "monthly" in msg:
            first = today.replace(day=1) - timedelta(days=1)
            start = first.replace(day=1)
            return {"start": str(start), "end": str(first)}
        if "this quarter" in msg or "quarterly" in msg:
            return {"start": str(today - timedelta(days=90)), "end": str(today)}
        if "last year" in msg or "annual" in msg:
            return {"start": str(today.replace(year=today.year - 1)), "end": str(today)}
        return {"start": str(today - timedelta(days=30)), "end": str(today)}
