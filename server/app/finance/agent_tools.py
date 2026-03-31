"""
Finance Module — Agent Tool Definitions.

These tool schemas are consumed by the FinanceAgent (Phase 5) when
building the tools= list for Claude API calls. Each entry follows the
Anthropic tool-use input_schema format.
"""

FINANCE_TOOLS = [
    {
        "name": "create_journal_entry",
        "description": (
            "Create and optionally post a double-entry journal entry. "
            "Validates that debits equal credits."
        ),
        "input_schema": {
            "type": "object",
            "required": ["entity_id", "entry_date", "description", "lines"],
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "Legal entity UUID",
                },
                "entry_date": {"type": "string", "format": "date"},
                "description": {"type": "string"},
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "account_code": {"type": "string"},
                            "debit": {"type": "number"},
                            "credit": {"type": "number"},
                            "description": {"type": "string"},
                        },
                    },
                },
                "post_immediately": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "create_invoice",
        "description": (
            "Create a customer invoice with line items. "
            "Auto-generates invoice number."
        ),
        "input_schema": {
            "type": "object",
            "required": [
                "entity_id",
                "customer_id",
                "invoice_date",
                "due_date",
                "line_items",
            ],
            "properties": {
                "entity_id": {"type": "string"},
                "customer_id": {"type": "string"},
                "invoice_date": {"type": "string", "format": "date"},
                "due_date": {"type": "string", "format": "date"},
                "currency": {"type": "string", "default": "SGD"},
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                            "tax_rate": {"type": "number"},
                        },
                    },
                },
                "notes": {"type": "string"},
            },
        },
    },
    {
        "name": "get_financial_report",
        "description": (
            "Generate any financial report: pnl, balance_sheet, cash_flow, "
            "ar_aging, ap_aging, trial_balance, tax_summary, analysis, consolidated"
        ),
        "input_schema": {
            "type": "object",
            "required": ["entity_id", "report_type"],
            "properties": {
                "entity_id": {"type": "string"},
                "report_type": {
                    "type": "string",
                    "enum": [
                        "pnl",
                        "balance_sheet",
                        "cash_flow",
                        "ar_aging",
                        "ap_aging",
                        "trial_balance",
                        "tax_summary",
                        "analysis",
                        "consolidated",
                    ],
                },
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
                "currency": {"type": "string", "default": "SGD"},
                "format": {
                    "type": "string",
                    "enum": ["json", "pdf", "xlsx", "csv"],
                    "default": "json",
                },
            },
        },
    },
    {
        "name": "list_overdue_invoices",
        "description": (
            "List overdue invoices with days outstanding and customer details"
        ),
        "input_schema": {
            "type": "object",
            "required": ["entity_id"],
            "properties": {
                "entity_id": {"type": "string"},
                "as_at_date": {"type": "string", "format": "date"},
            },
        },
    },
    {
        "name": "record_payment",
        "description": (
            "Record a customer payment against an invoice or a vendor payment "
            "against a bill"
        ),
        "input_schema": {
            "type": "object",
            "required": [
                "entity_id",
                "payment_type",
                "payment_date",
                "amount",
                "currency",
            ],
            "properties": {
                "entity_id": {"type": "string"},
                "payment_type": {
                    "type": "string",
                    "enum": ["receipt", "payment"],
                },
                "payment_date": {"type": "string", "format": "date"},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
                "invoice_id": {"type": "string"},
                "bill_id": {"type": "string"},
                "payment_method": {"type": "string"},
                "reference": {"type": "string"},
            },
        },
    },
    {
        "name": "approve_expense",
        "description": "Approve or reject a pending expense claim",
        "input_schema": {
            "type": "object",
            "required": ["expense_id", "action"],
            "properties": {
                "expense_id": {"type": "string"},
                "action": {
                    "type": "string",
                    "enum": ["approve", "reject"],
                },
                "notes": {"type": "string"},
            },
        },
    },
    {
        "name": "get_account_balance",
        "description": "Get current balance of any GL account by account code",
        "input_schema": {
            "type": "object",
            "required": ["entity_id", "account_code"],
            "properties": {
                "entity_id": {"type": "string"},
                "account_code": {"type": "string"},
                "as_at_date": {"type": "string", "format": "date"},
            },
        },
    },
    {
        "name": "close_period",
        "description": (
            "Close an accounting period after validating all journal entries "
            "are posted"
        ),
        "input_schema": {
            "type": "object",
            "required": ["period_id"],
            "properties": {
                "period_id": {"type": "string"},
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true to proceed",
                },
            },
        },
    },
    {
        "name": "export_report",
        "description": (
            "Export any financial report as PDF, XLSX or CSV and optionally "
            "email it"
        ),
        "input_schema": {
            "type": "object",
            "required": ["entity_id", "report_type", "format"],
            "properties": {
                "entity_id": {"type": "string"},
                "report_type": {"type": "string"},
                "format": {
                    "type": "string",
                    "enum": ["pdf", "xlsx", "csv"],
                },
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "email_to": {
                    "type": "string",
                    "description": "Email address to send report to",
                },
            },
        },
    },
]
