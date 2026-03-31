"""
FinanceAgent — Senior financial controller AI assistant.

Handles: double-entry bookkeeping, multi-currency transactions, invoices/quotes,
AR/AP management, bank reconciliation, expense approval, tax compliance (GST F5),
financial reporting (P&L, Balance Sheet, Cash Flow), group consolidation, and
financial analysis/KPI monitoring.

Sources:
  - mobile: User request from Finance department
  - scheduler: Daily overdue check, weekly AR/AP summary, monthly close reminder,
               quarterly GST reminder, monthly financial statements (2nd of month)
"""

import logging
from datetime import date

from app.agents.base_agent import BaseAgent
from app.llm import llm_manager as llm_mod

logger = logging.getLogger("mezzofy.agents.finance")

# Keywords that trigger Finance Agent (for cross-department routing)
_TRIGGER_KEYWORDS = {
    "invoice", "invoices", "bill", "bills", "payment", "payments",
    "expense", "expenses", "journal", "ledger", "account", "accounts",
    "finance", "financial", "revenue", "profit", "loss", "balance sheet",
    "cash flow", "ar", "ap", "receivable", "payable", "tax", "gst",
    "vendor", "customer", "quote", "quotes", "report", "p&l",
    "overdue", "outstanding", "shareholder", "equity", "bank",
    "period close", "fiscal", "audit trail",
    # Legacy keywords from previous stub
    "pnl", "budget", "statement", "quarterly", "annual", "earnings",
    "cost", "margin", "ebitda", "ratio",
}

# Roles authorised to use the Finance Agent
_FINANCE_ROLES = {"finance_manager", "finance_viewer", "executive", "admin", "cfo", "ceo"}

_SYSTEM_PROMPT_TEMPLATE = """You are the Mezzofy Finance Agent — a senior financial controller AI assistant.
Today's date is {today}.

You help the Finance Manager manage all aspects of Mezzofy's financial operations including:
- Double-entry bookkeeping and journal entries
- Multi-currency transactions across SG, HK, MY, CN entities
- Invoice and quote management (shared with Sales)
- Accounts Receivable and Payable management
- Bank account management and reconciliation
- Expense management and approval workflows
- Shareholder and equity register
- Tax compliance (GST F5, corporate tax, withholding tax)
- Comprehensive financial reporting (P&L, Balance Sheet, Cash Flow, etc.)
- Group consolidation across holding and subsidiary entities
- Financial analysis and KPI monitoring

Guidelines:
- Always confirm destructive operations (posting, period close, void) before executing
- For report generation, default to current fiscal period unless specified
- When amounts are mentioned without currency, default to SGD (or entity base currency)
- Flag any entries that would cause the trial balance to be unbalanced
- For overdue invoice queries, use today's date as the reference point
- Never fabricate financial data — only report what exists in the database
"""


class FinanceAgent(BaseAgent):
    """
    Manages full-cycle financial operations: bookkeeping, reporting, AR/AP,
    tax compliance, bank reconciliation, and expense management.

    Key workflows:
    - Journal entry creation from natural language (mobile)
    - Invoice creation and management (mobile)
    - Financial report generation: P&L, BS, CF, AR aging, AP aging, trial balance (mobile)
    - AR follow-up for overdue invoices (mobile + scheduled daily)
    - Expense approval workflow (mobile)
    - GST F5 data preparation (mobile + scheduled quarterly)
    - Finance analysis and KPIs (mobile)
    - Bank reconciliation (mobile)
    - Automated daily overdue invoice check (scheduler)
    - Automated weekly AR/AP aging summary (scheduler)
    - Automated monthly close reminder on 25th (scheduler)
    - Automated quarterly GST filing reminder (scheduler)
    - Automated monthly financial statements on 2nd (scheduler)
    """

    def can_handle(self, task: dict) -> bool:
        role = task.get("role", "").lower()
        dept = task.get("department", "").lower()

        # Primary: department match
        if dept == "finance":
            return True

        # Secondary: finance role + keyword (cross-department access)
        if role in _FINANCE_ROLES:
            msg = task.get("message", "").lower()
            return any(kw in msg for kw in _TRIGGER_KEYWORDS)

        return False

    async def execute(self, task: dict) -> dict:
        source = task.get("source", "mobile")
        event = task.get("event", "")
        msg = task.get("message", "").lower()

        # ── Scheduler paths ───────────────────────────────────────────────────
        if source == "scheduler":
            if "overdue" in event or "overdue" in msg:
                return await self.handle_ar_followup(task)
            if "ar_ap" in event or "ar/ap" in msg or "aging" in msg:
                return await self._ar_ap_summary_workflow(task)
            if "month_close" in event or "close reminder" in msg:
                return await self._month_close_reminder_workflow(task)
            if "gst" in event or "gst" in msg:
                return await self.handle_tax_preparation(task)
            if "monthly_statements" in event or "monthly financial" in msg:
                return await self.handle_report_generation(task)
            # Default for other scheduled finance tasks
            return await self.handle_report_generation(task)

        # ── Mobile/Teams keyword routing ──────────────────────────────────────
        if any(kw in msg for kw in ("journal", "ledger", "debit", "credit", "post entry")):
            return await self.handle_journal_entry(task)

        if any(kw in msg for kw in ("create invoice", "new invoice", "raise invoice",
                                     "create quote", "new quote", "raise quote")):
            return await self.handle_invoice_creation(task)

        if any(kw in msg for kw in ("p&l", "pnl", "profit", "loss", "balance sheet",
                                     "cash flow", "trial balance", "ar aging", "ap aging",
                                     "report", "statement", "financial report")):
            return await self.handle_report_generation(task)

        if any(kw in msg for kw in ("overdue", "outstanding invoice", "ar follow",
                                     "collections", "receivable follow")):
            return await self.handle_ar_followup(task)

        if any(kw in msg for kw in ("approve expense", "reject expense", "pending expense",
                                     "expense claim", "expense approval")):
            return await self.handle_expense_approval(task)

        if any(kw in msg for kw in ("gst", "tax", "withholding", "corporate tax",
                                     "gst f5", "tax filing", "iras")):
            return await self.handle_tax_preparation(task)

        if any(kw in msg for kw in ("kpi", "analysis", "ratio", "margin", "ebitda",
                                     "dso", "dpo", "working capital", "liquidity",
                                     "financial health", "finance analysis")):
            return await self.handle_finance_analysis(task)

        if any(kw in msg for kw in ("bank reconcil", "reconcile", "bank statement",
                                     "match transactions", "unreconciled")):
            return await self.handle_bank_reconciliation(task)

        return await self._general_response(task)

    # ── Workflow handlers ─────────────────────────────────────────────────────

    async def handle_journal_entry(self, task: dict) -> dict:
        """Natural language → create journal entry via Finance API tool calls."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"The user wants to create a journal entry. Parse the request and use the "
            f"create_journal_entry tool to record it. Confirm the entry details with the user "
            f"before posting unless they explicitly say to post immediately.\n\n"
            f"Request: {user_context}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.append("create_journal_entry")
        content = llm_result.get("content", "Journal entry processed.")
        return self._ok(content=content, tools_called=tools_called)

    async def handle_invoice_creation(self, task: dict) -> dict:
        """Create invoice or quote from natural language description."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"The user wants to create an invoice or quote. Extract the details (customer, "
            f"line items, amounts, due date) and use the create_invoice tool.\n\n"
            f"Request: {user_context}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.append("create_invoice")
        content = llm_result.get("content", "Invoice created successfully.")
        return self._ok(content=content, tools_called=tools_called)

    async def handle_report_generation(self, task: dict) -> dict:
        """Generate financial report: P&L, Balance Sheet, Cash Flow, AR/AP aging, etc."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")
        source = task.get("source", "mobile")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"The user wants a financial report. Detect the report type from the request "
            f"(pnl, balance_sheet, cash_flow, ar_aging, ap_aging, trial_balance, tax_summary, "
            f"analysis, or consolidated) and use the get_financial_report tool to fetch the data. "
            f"Then provide a concise executive summary with key highlights and trends.\n\n"
            f"Request: {user_context}\n"
            f"Date: {today_str}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.append("get_financial_report")
        summary = llm_result.get("content", "Financial report generated.")

        # Generate PDF artifact
        artifacts = []
        pdf_title = "Financial Report"
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
                    suggested_name=pdf_title,
                )
                artifacts.append(artifact)
                tools_called.append("create_pdf")
                skill_ok = True
        except Exception as e:
            logger.warning(f"Finance report PDF skill failed: {e}")

        if not skill_ok:
            try:
                from app.tools.document.pdf_ops import PDFOps
                pdf = PDFOps(self.config)
                pdf_result = await pdf.execute("create_pdf", content=summary, title=pdf_title)
                tools_called.append("create_pdf")
                if pdf_result.get("success") and pdf_result.get("output"):
                    artifacts.append({
                        "name": f"financial_report_{date.today().strftime('%Y%m%d')}.pdf",
                        "path": pdf_result["output"],
                        "type": "pdf",
                    })
            except Exception as e:
                logger.warning(f"Finance report PDF fallback failed: {e}")

        # Deliver to Teams for automated runs
        if self._is_automated(task):
            await self._deliver_to_teams(
                channel="#finance",
                message=f"Monthly Financial Statements\n\n{summary[:500]}...",
                attachments=artifacts,
            )
            cfo_email = self.config.get("notifications", {}).get("cfo_email", "")
            if cfo_email:
                await self._send_email(
                    to=cfo_email,
                    subject=f"Monthly Financial Statements — {today_str}",
                    body=f"<h2>Monthly Financial Statements</h2><p>{summary}</p>",
                    attachments=artifacts,
                )

        return self._ok(content=summary, artifacts=artifacts, tools_called=tools_called)

    async def handle_ar_followup(self, task: dict) -> dict:
        """Identify overdue invoices and draft follow-up communications."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"Use the list_overdue_invoices tool to fetch all overdue invoices as at today ({today_str}). "
            f"Then draft professional follow-up communication for each overdue customer, "
            f"grouped by aging bucket (1-30, 31-60, 61-90, 90+ days). "
            f"Prioritise invoices over 60 days for immediate escalation.\n\n"
            f"Request: {user_context}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.append("list_overdue_invoices")
        content = llm_result.get("content", "AR follow-up review complete.")

        # For automated scheduler runs, post to Teams
        if self._is_automated(task):
            await self._deliver_to_teams(
                channel="#finance",
                message=f"Daily AR Overdue Check\n\n{content[:600]}...",
                attachments=[],
            )

        return self._ok(content=content, tools_called=tools_called)

    async def handle_expense_approval(self, task: dict) -> dict:
        """Review and approve/reject pending expense claims."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"The finance manager wants to review and action expense claims. "
            f"Use the approve_expense tool to approve or reject based on the request. "
            f"Check the expense against company policy (travel cap SGD 300/night, "
            f"meals SGD 50/person, entertainment requires CFO approval >SGD 500).\n\n"
            f"Request: {user_context}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.append("approve_expense")
        content = llm_result.get("content", "Expense review complete.")
        return self._ok(content=content, tools_called=tools_called)

    async def handle_tax_preparation(self, task: dict) -> dict:
        """Prepare GST F5 data, corporate tax, or withholding tax summaries."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")
        source = task.get("source", "mobile")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"Help the finance manager prepare tax data. Use the get_financial_report tool "
            f"with report_type='tax_summary' to fetch the relevant period data. "
            f"For GST F5: populate all 9 boxes (Box 1-9) per IRAS requirements. "
            f"Standard rate is 9% (effective 2024). Flag any blocked input tax items.\n\n"
            f"Request: {user_context}\n"
            f"Date: {today_str}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.append("get_financial_report")
        content = llm_result.get("content", "Tax preparation data compiled.")

        # For automated GST reminder, post to Teams
        if self._is_automated(task):
            await self._deliver_to_teams(
                channel="#finance",
                message=f"GST Filing Reminder\n\n{content[:500]}...",
                attachments=[],
            )
            finance_email = self.config.get("notifications", {}).get("finance_manager_email", "")
            if finance_email:
                await self._send_email(
                    to=finance_email,
                    subject=f"GST F5 Filing Reminder — {today_str}",
                    body=f"<h2>GST Filing Reminder</h2><p>{content}</p>",
                    attachments=[],
                )

        return self._ok(content=content, tools_called=tools_called)

    async def handle_finance_analysis(self, task: dict) -> dict:
        """Compute financial KPIs, trends, and ratio analysis."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"Perform financial analysis using the get_financial_report tool with "
            f"report_type='analysis'. Calculate key ratios: Current Ratio, Quick Ratio, "
            f"Gross Margin, Net Margin, DSO, DPO, ROE, Debt/Equity. "
            f"Compare to prior period and flag any deteriorating metrics.\n\n"
            f"Request: {user_context}\n"
            f"Date: {today_str}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.append("get_financial_report")
        content = llm_result.get("content", "Financial analysis complete.")
        return self._ok(content=content, tools_called=tools_called)

    async def handle_bank_reconciliation(self, task: dict) -> dict:
        """Match bank statement transactions against GL entries."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"Help the finance manager perform bank reconciliation. "
            f"Use the get_account_balance tool to check GL bank account balances. "
            f"List any unreconciled items and suggest matching entries. "
            f"Common unreconciled items: outstanding cheques, deposits in transit, "
            f"bank fees not yet recorded, timing differences.\n\n"
            f"Request: {user_context}\n"
            f"Date: {today_str}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.append("get_account_balance")
        content = llm_result.get("content", "Bank reconciliation review complete.")
        return self._ok(content=content, tools_called=tools_called)

    # ── Scheduler-only workflows ───────────────────────────────────────────────

    async def _ar_ap_summary_workflow(self, task: dict) -> dict:
        """Scheduler (Monday 1AM UTC): weekly AR/AP aging summary → finance manager."""
        from app.finance.agent_tools import FINANCE_TOOLS

        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"Generate the weekly AR and AP aging summary report. "
            f"Use get_financial_report twice: once with report_type='ar_aging' and once with "
            f"report_type='ap_aging'. Summarise total outstanding, aging buckets, "
            f"top 5 overdue customers (AR), and top 5 overdue vendors (AP). "
            f"Highlight any accounts more than 60 days outstanding.\n\n"
            f"Date: {today_str}"
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=FINANCE_TOOLS,
            task_context=task,
        )
        tools_called.extend(["get_financial_report", "get_financial_report"])
        summary = llm_result.get("content", "Weekly AR/AP summary generated.")

        await self._deliver_to_teams(
            channel="#finance",
            message=f"Weekly AR/AP Aging Summary\n\n{summary[:600]}...",
            attachments=[],
        )
        finance_email = self.config.get("notifications", {}).get("finance_manager_email", "")
        if finance_email:
            await self._send_email(
                to=finance_email,
                subject=f"Weekly AR/AP Aging Summary — {today_str}",
                body=f"<h2>Weekly AR/AP Aging Summary</h2><p>{summary}</p>",
                attachments=[],
            )

        return self._ok(content=summary, tools_called=tools_called)

    async def _month_close_reminder_workflow(self, task: dict) -> dict:
        """Scheduler (25th of month, 1AM UTC): month-end close reminder → finance manager."""
        tools_called = []
        today_str = date.today().strftime("%B %d, %Y")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        prompt = (
            f"Send a month-end close reminder to the finance manager. "
            f"Today is {today_str}. The month-end close is approaching. "
            f"List the standard close checklist:\n"
            f"1. All invoices for the period posted\n"
            f"2. All bills approved and posted\n"
            f"3. Bank reconciliations complete\n"
            f"4. Recurring journal entries posted\n"
            f"5. Depreciation entries posted\n"
            f"6. Trial balance balanced\n"
            f"7. Intercompany eliminations (if group)\n"
            f"Write a concise reminder message."
        )

        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            task_context=task,
        )
        reminder = llm_result.get("content", "Month-end close reminder: please complete all period-end tasks before month close.")

        await self._deliver_to_teams(
            channel="#finance",
            message=f"Month-End Close Reminder\n\n{reminder}",
            attachments=[],
        )
        finance_email = self.config.get("notifications", {}).get("finance_manager_email", "")
        if finance_email:
            await self._send_email(
                to=finance_email,
                subject=f"Month-End Close Reminder — {today_str}",
                body=f"<h2>Month-End Close Reminder</h2><p>{reminder}</p>",
                attachments=[],
            )

        return self._ok(content=reminder, tools_called=tools_called)

    # ── General fallback ───────────────────────────────────────────────────────

    async def _general_response(self, task: dict) -> dict:
        """Fallback: answer general finance questions using LLM."""
        today_str = date.today().strftime("%B %d, %Y")
        user_context = task.get("extracted_text") or task.get("message", "")

        system = _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
        llm_result = await llm_mod.get().chat(
            messages=[{"role": "user", "content": user_context}],
            system=system,
            task_context=task,
        )
        content = llm_result.get("content", "How can I help with your finance query?")
        return self._ok(content=content, tools_called=[])
