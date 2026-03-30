# Claude Code Prompt — Mezzofy Finance Module (Full Build)

> **Version:** 1.1  
> **Target:** Claude Code CLI on EC2 (`/home/ubuntu/mezzofy-ai-assistant/`)  
> **Execution model:** Single session, sequential phases, fully additive  
> **Estimated phases:** 8

---

## CONTEXT & CONSTRAINTS

You are building the **Finance Module** for the Mezzofy AI Assistant — a production system running on AWS EC2 (ap-southeast-1, t3.xlarge, Ubuntu 22.04). The system uses FastAPI + PostgreSQL + Celery + Redis. All changes are **strictly additive** — you must never modify existing working code, never restart FastAPI/Celery/Celery Beat, and all Alembic migrations must use `IF NOT EXISTS` guards.

**Before writing any code in each phase**, audit the relevant existing files using `cat` or `grep` to confirm what already exists. Never duplicate or conflict with live code.

**Tech stack reminders:**
- Backend: FastAPI, SQLAlchemy (async), Alembic, PostgreSQL 15
- Task queue: Celery 5 + Celery Beat + Redis 7
- Auth: JWT + RBAC via `config/roles.yaml`
- LLM: Anthropic Claude API (claude-sonnet-4-20250514 for Finance Agent)
- Document generation: Claude Skills API (primary), python-pptx / reportlab / openpyxl (fallback)
- MS Graph: application-level + delegated OAuth flows
- Portal: React web app at `/portal/src/`
- Mobile: React Native at `/mobile/src/`

---

## PHASE 1 — DATABASE MIGRATIONS (Finance Schema)

### 1.1 Audit first
```bash
cat scripts/migrate.py | grep -A5 "CREATE TABLE"
cat alembic/versions/ | ls -la
```

### 1.2 Create Alembic migration: `alembic/versions/004_finance_module.py`

Create the following **19 tables** with `IF NOT EXISTS` guards. All monetary columns use `NUMERIC(20,6)` to support multi-currency precision.

```sql
-- ─── MULTI-CURRENCY & ENTITY FOUNDATION ───────────────────────────────────

-- 1. Currencies
CREATE TABLE IF NOT EXISTS fin_currencies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(10) UNIQUE NOT NULL,   -- ISO 4217: SGD, USD, HKD, CNY, MYR
    name            TEXT NOT NULL,
    symbol          VARCHAR(10),
    is_base         BOOLEAN DEFAULT false,          -- exactly one base currency per entity
    decimal_places  INT DEFAULT 2,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Exchange Rates (daily snapshot)
CREATE TABLE IF NOT EXISTS fin_exchange_rates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency   VARCHAR(10) NOT NULL,
    to_currency     VARCHAR(10) NOT NULL,
    rate            NUMERIC(20,10) NOT NULL,
    effective_date  DATE NOT NULL,
    source          TEXT DEFAULT 'manual',          -- manual | api | ecb
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_currency, to_currency, effective_date)
);

-- 3. Legal Entities / Country Groups
CREATE TABLE IF NOT EXISTS fin_entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(20) UNIQUE NOT NULL,    -- e.g. MEZZ-SG, MEZZ-HK, MEZZ-GROUP
    name            TEXT NOT NULL,
    entity_type     TEXT NOT NULL,                  -- subsidiary | holding | branch | group
    country_code    VARCHAR(5),                     -- ISO 3166: SG, HK, MY, CN
    base_currency   VARCHAR(10) DEFAULT 'SGD',
    parent_entity_id UUID REFERENCES fin_entities(id),
    tax_id          TEXT,
    registered_address TEXT,
    fiscal_year_start INT DEFAULT 1,               -- month number (1=Jan, 4=Apr)
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── CHART OF ACCOUNTS ────────────────────────────────────────────────────

-- 4. Account Categories
CREATE TABLE IF NOT EXISTS fin_account_categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    code            VARCHAR(20) NOT NULL,
    name            TEXT NOT NULL,
    account_type    TEXT NOT NULL,                  -- asset | liability | equity | income | expense
    normal_balance  TEXT NOT NULL,                  -- debit | credit
    display_order   INT DEFAULT 0,
    parent_id       UUID REFERENCES fin_account_categories(id),
    UNIQUE(entity_id, code)
);

-- 5. Chart of Accounts (General Ledger Accounts)
CREATE TABLE IF NOT EXISTS fin_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    category_id     UUID REFERENCES fin_account_categories(id),
    code            VARCHAR(30) NOT NULL,           -- e.g. 1001, 2100, 4001
    name            TEXT NOT NULL,
    description     TEXT,
    currency        VARCHAR(10) DEFAULT 'SGD',
    is_bank_account BOOLEAN DEFAULT false,
    is_control      BOOLEAN DEFAULT false,          -- control accounts (AR/AP)
    allow_direct_posting BOOLEAN DEFAULT true,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, code)
);

-- ─── JOURNAL & LEDGER ─────────────────────────────────────────────────────

-- 6. Accounting Periods
CREATE TABLE IF NOT EXISTS fin_periods (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    name            TEXT NOT NULL,                  -- e.g. "Jan 2025", "Q1 FY2025"
    period_type     TEXT NOT NULL,                  -- monthly | quarterly | annual
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    status          TEXT DEFAULT 'open',            -- open | closed | locked
    closed_by       UUID REFERENCES users(id),
    closed_at       TIMESTAMPTZ,
    UNIQUE(entity_id, start_date, period_type)
);

-- 7. Journal Entries (header)
CREATE TABLE IF NOT EXISTS fin_journal_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    period_id       UUID REFERENCES fin_periods(id),
    entry_number    TEXT NOT NULL,                  -- auto-generated: MZ-JE-2025-0001
    entry_date      DATE NOT NULL,
    description     TEXT NOT NULL,
    reference       TEXT,                           -- invoice number, receipt ID, etc.
    source          TEXT DEFAULT 'manual',          -- manual | invoice | payment | import | agent
    currency        VARCHAR(10) DEFAULT 'SGD',
    exchange_rate   NUMERIC(20,10) DEFAULT 1,
    status          TEXT DEFAULT 'draft',           -- draft | posted | reversed
    created_by      UUID REFERENCES users(id),
    posted_by       UUID REFERENCES users(id),
    posted_at       TIMESTAMPTZ,
    reversed_by     UUID REFERENCES fin_journal_entries(id),
    tags            JSONB DEFAULT '[]',
    attachments     JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, entry_number)
);

-- 8. Journal Entry Lines (debit/credit lines)
CREATE TABLE IF NOT EXISTS fin_journal_lines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_entry_id UUID REFERENCES fin_journal_entries(id) ON DELETE CASCADE,
    account_id      UUID REFERENCES fin_accounts(id),
    description     TEXT,
    debit_amount    NUMERIC(20,6) DEFAULT 0,
    credit_amount   NUMERIC(20,6) DEFAULT 0,
    currency        VARCHAR(10),
    base_amount     NUMERIC(20,6),                  -- converted to entity base currency
    tax_code        TEXT,
    cost_center     TEXT,
    project_ref     TEXT,
    line_order      INT DEFAULT 0
);

-- ─── CUSTOMERS & VENDORS ──────────────────────────────────────────────────

-- 9. Customers (linked to sales_leads or manually added)
CREATE TABLE IF NOT EXISTS fin_customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    lead_id         UUID REFERENCES sales_leads(id),  -- nullable, from CRM conversion
    customer_code   TEXT NOT NULL,                  -- MZ-CUST-0001
    name            TEXT NOT NULL,
    company_name    TEXT,
    email           TEXT,
    phone           TEXT,
    billing_address JSONB,
    shipping_address JSONB,
    currency        VARCHAR(10) DEFAULT 'SGD',
    payment_terms   INT DEFAULT 30,                 -- days
    credit_limit    NUMERIC(20,6),
    tax_id          TEXT,
    notes           TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, customer_code)
);

-- 10. Vendors / Suppliers
CREATE TABLE IF NOT EXISTS fin_vendors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    vendor_code     TEXT NOT NULL,                  -- MZ-VEND-0001
    name            TEXT NOT NULL,
    company_name    TEXT,
    email           TEXT,
    phone           TEXT,
    billing_address JSONB,
    currency        VARCHAR(10) DEFAULT 'SGD',
    payment_terms   INT DEFAULT 30,
    bank_details    JSONB,                          -- encrypted bank info
    tax_id          TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, vendor_code)
);

-- ─── INVOICES & QUOTES ────────────────────────────────────────────────────

-- 11. Quotes (used by Sales, owned by Finance)
CREATE TABLE IF NOT EXISTS fin_quotes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    quote_number    TEXT NOT NULL,                  -- MZ-QUO-2025-0001
    customer_id     UUID REFERENCES fin_customers(id),
    lead_id         UUID REFERENCES sales_leads(id),
    quote_date      DATE NOT NULL,
    expiry_date     DATE,
    currency        VARCHAR(10) DEFAULT 'SGD',
    exchange_rate   NUMERIC(20,10) DEFAULT 1,
    subtotal        NUMERIC(20,6) DEFAULT 0,
    tax_amount      NUMERIC(20,6) DEFAULT 0,
    discount_amount NUMERIC(20,6) DEFAULT 0,
    total_amount    NUMERIC(20,6) DEFAULT 0,
    status          TEXT DEFAULT 'draft',           -- draft | sent | accepted | declined | expired | converted
    terms           TEXT,
    notes           TEXT,
    line_items      JSONB NOT NULL DEFAULT '[]',    -- [{description, qty, unit_price, tax_rate, amount}]
    created_by      UUID REFERENCES users(id),
    sent_at         TIMESTAMPTZ,
    converted_to_invoice UUID,                      -- set when converted
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, quote_number)
);

-- 12. Invoices (AR — Accounts Receivable)
CREATE TABLE IF NOT EXISTS fin_invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    invoice_number  TEXT NOT NULL,                  -- MZ-INV-2025-0001
    customer_id     UUID REFERENCES fin_customers(id),
    quote_id        UUID REFERENCES fin_quotes(id), -- nullable
    invoice_date    DATE NOT NULL,
    due_date        DATE NOT NULL,
    currency        VARCHAR(10) DEFAULT 'SGD',
    exchange_rate   NUMERIC(20,10) DEFAULT 1,
    subtotal        NUMERIC(20,6) DEFAULT 0,
    tax_amount      NUMERIC(20,6) DEFAULT 0,
    discount_amount NUMERIC(20,6) DEFAULT 0,
    total_amount    NUMERIC(20,6) DEFAULT 0,
    paid_amount     NUMERIC(20,6) DEFAULT 0,
    outstanding     NUMERIC(20,6) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    status          TEXT DEFAULT 'draft',           -- draft | sent | partial | paid | overdue | cancelled | void
    line_items      JSONB NOT NULL DEFAULT '[]',
    payment_terms   INT DEFAULT 30,
    notes           TEXT,
    created_by      UUID REFERENCES users(id),
    sent_at         TIMESTAMPTZ,
    paid_at         TIMESTAMPTZ,
    journal_entry_id UUID REFERENCES fin_journal_entries(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, invoice_number)
);

-- 13. Bills (AP — Accounts Payable)
CREATE TABLE IF NOT EXISTS fin_bills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    bill_number     TEXT NOT NULL,                  -- MZ-BILL-2025-0001
    vendor_id       UUID REFERENCES fin_vendors(id),
    bill_date       DATE NOT NULL,
    due_date        DATE NOT NULL,
    reference       TEXT,                           -- vendor invoice number
    currency        VARCHAR(10) DEFAULT 'SGD',
    exchange_rate   NUMERIC(20,10) DEFAULT 1,
    subtotal        NUMERIC(20,6) DEFAULT 0,
    tax_amount      NUMERIC(20,6) DEFAULT 0,
    total_amount    NUMERIC(20,6) DEFAULT 0,
    paid_amount     NUMERIC(20,6) DEFAULT 0,
    outstanding     NUMERIC(20,6) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    status          TEXT DEFAULT 'pending',         -- pending | approved | partial | paid | cancelled
    line_items      JSONB NOT NULL DEFAULT '[]',
    notes           TEXT,
    approved_by     UUID REFERENCES users(id),
    journal_entry_id UUID REFERENCES fin_journal_entries(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, bill_number)
);

-- ─── PAYMENTS & BANK ──────────────────────────────────────────────────────

-- 14. Bank Accounts
CREATE TABLE IF NOT EXISTS fin_bank_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    account_id      UUID REFERENCES fin_accounts(id), -- linked GL account
    bank_name       TEXT NOT NULL,
    account_name    TEXT NOT NULL,
    account_number  TEXT,                           -- masked: ****1234
    swift_code      TEXT,
    iban            TEXT,
    currency        VARCHAR(10) NOT NULL,
    current_balance NUMERIC(20,6) DEFAULT 0,
    last_reconciled DATE,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 15. Payments (receipts from customers / payments to vendors)
CREATE TABLE IF NOT EXISTS fin_payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    payment_number  TEXT NOT NULL,                  -- MZ-PMT-2025-0001
    payment_type    TEXT NOT NULL,                  -- receipt | payment
    payment_date    DATE NOT NULL,
    bank_account_id UUID REFERENCES fin_bank_accounts(id),
    customer_id     UUID REFERENCES fin_customers(id),
    vendor_id       UUID REFERENCES fin_vendors(id),
    invoice_id      UUID REFERENCES fin_invoices(id),
    bill_id         UUID REFERENCES fin_bills(id),
    currency        VARCHAR(10) NOT NULL,
    amount          NUMERIC(20,6) NOT NULL,
    exchange_rate   NUMERIC(20,10) DEFAULT 1,
    payment_method  TEXT,                           -- bank_transfer | cheque | paynow | stripe | cash
    reference       TEXT,
    notes           TEXT,
    journal_entry_id UUID REFERENCES fin_journal_entries(id),
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, payment_number)
);

-- ─── EXPENSES & SHAREHOLDERS ──────────────────────────────────────────────

-- 16. Expenses
CREATE TABLE IF NOT EXISTS fin_expenses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    expense_number  TEXT NOT NULL,                  -- MZ-EXP-2025-0001
    expense_date    DATE NOT NULL,
    category        TEXT NOT NULL,                  -- travel | meals | software | marketing | etc.
    description     TEXT NOT NULL,
    vendor_name     TEXT,
    vendor_id       UUID REFERENCES fin_vendors(id),
    account_id      UUID REFERENCES fin_accounts(id),
    currency        VARCHAR(10) NOT NULL,
    amount          NUMERIC(20,6) NOT NULL,
    tax_amount      NUMERIC(20,6) DEFAULT 0,
    status          TEXT DEFAULT 'pending',         -- pending | approved | reimbursed | rejected
    submitted_by    UUID REFERENCES users(id),
    approved_by     UUID REFERENCES users(id),
    receipt_path    TEXT,                           -- S3 or EBS path
    journal_entry_id UUID REFERENCES fin_journal_entries(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, expense_number)
);

-- 17. Shareholders / Equity Register
CREATE TABLE IF NOT EXISTS fin_shareholders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    name            TEXT NOT NULL,
    shareholder_type TEXT NOT NULL,                 -- individual | company
    id_number       TEXT,                           -- NRIC / passport / company reg
    nationality     TEXT,
    address         JSONB,
    share_class     TEXT DEFAULT 'ordinary',        -- ordinary | preference | redeemable
    shares_held     NUMERIC(20,0) DEFAULT 0,
    par_value       NUMERIC(20,6) DEFAULT 1,
    total_paid      NUMERIC(20,6) DEFAULT 0,
    ownership_pct   NUMERIC(8,4),                   -- calculated field, stored for reporting
    effective_date  DATE NOT NULL,
    is_active       BOOLEAN DEFAULT true,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── TAX ──────────────────────────────────────────────────────────────────

-- 18. Tax Codes
CREATE TABLE IF NOT EXISTS fin_tax_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    code            TEXT NOT NULL,                  -- GST9, GST0, EXEMPT, WHT15
    name            TEXT NOT NULL,
    tax_type        TEXT NOT NULL,                  -- gst | vat | withholding | corporate
    rate            NUMERIC(8,4) NOT NULL,          -- percentage: 9.0000 = 9%
    country_code    VARCHAR(5),
    applies_to      TEXT DEFAULT 'both',            -- sales | purchases | both
    gl_account_id   UUID REFERENCES fin_accounts(id),
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, code)
);

-- 19. Tax Returns / Filing Log
CREATE TABLE IF NOT EXISTS fin_tax_returns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    period_id       UUID REFERENCES fin_periods(id),
    tax_type        TEXT NOT NULL,                  -- gst_f5 | corporate_tax | withholding
    filing_period   TEXT NOT NULL,                  -- Q1/2025, FY2025, etc.
    due_date        DATE,
    filed_date      DATE,
    total_tax_due   NUMERIC(20,6) DEFAULT 0,
    total_tax_paid  NUMERIC(20,6) DEFAULT 0,
    status          TEXT DEFAULT 'pending',         -- pending | filed | paid | amended
    submission_ref  TEXT,
    notes           TEXT,
    generated_by    UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 1.3 Create indexes
```sql
CREATE INDEX IF NOT EXISTS idx_fin_je_entity_date ON fin_journal_entries(entity_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_fin_je_period ON fin_journal_entries(period_id);
CREATE INDEX IF NOT EXISTS idx_fin_jl_account ON fin_journal_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_fin_invoices_customer ON fin_invoices(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_fin_invoices_due ON fin_invoices(due_date, status);
CREATE INDEX IF NOT EXISTS idx_fin_bills_vendor ON fin_bills(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_fin_payments_date ON fin_payments(payment_date, entity_id);
CREATE INDEX IF NOT EXISTS idx_fin_expenses_date ON fin_expenses(expense_date, entity_id);
```

### 1.4 Run migration
```bash
cd /home/ubuntu/mezzofy-ai-assistant/server
alembic upgrade head
```

---

## PHASE 2 — RBAC EXTENSIONS

### 2.1 Audit existing roles.yaml
```bash
cat config/roles.yaml
```

### 2.2 Extend `config/roles.yaml` — add new finance permissions (additive only)
Append to the `finance_manager` permissions block:
```yaml
      - finance_invoices          # Create/edit invoices and quotes
      - finance_bills             # Create/edit bills (AP)
      - finance_payments          # Record payments
      - finance_expenses          # Manage expenses
      - finance_journal           # Create/post journal entries
      - finance_reports           # Generate all financial reports
      - finance_audit             # View audit trail
      - finance_tax               # Manage tax codes and filings
      - finance_entities          # Manage legal entities
      - finance_shareholders      # Manage shareholder register
      - finance_customers         # Create/edit finance customers
      - finance_vendors           # Create/edit vendors
      - finance_bank              # Manage bank accounts
```

Also add new `finance_viewer` read-only permissions for report access, and extend `executive` permissions to include all `finance_*` permissions.

---

## PHASE 3 — BACKEND: PYDANTIC SCHEMAS & SERVICE LAYER

### 3.1 Create `/server/app/finance/` module directory
```
server/app/finance/
├── __init__.py
├── schemas.py          # Pydantic v2 models for all 19 tables + request/response
├── service.py          # Business logic (auto-numbering, double-entry, FX, reporting)
├── router.py           # FastAPI router — all /api/finance/* endpoints
├── reports.py          # Report generation engine (P&L, BS, CF, AR, AP, etc.)
└── agent_tools.py      # Finance Agent tool definitions
```

### 3.2 `schemas.py` — Key Pydantic models

Create schemas for every entity. Critical ones:

```python
# Multi-currency amounts
class MoneyAmount(BaseModel):
    amount: Decimal
    currency: str
    base_amount: Optional[Decimal] = None  # always in entity base currency
    exchange_rate: Optional[Decimal] = None

# Journal Entry with validation
class JournalEntryCreate(BaseModel):
    entity_id: UUID
    entry_date: date
    description: str
    reference: Optional[str]
    currency: str = "SGD"
    lines: List[JournalLineCreate]

    @model_validator(mode='after')
    def validate_balanced(self):
        total_debit = sum(l.debit_amount for l in self.lines)
        total_credit = sum(l.credit_amount for l in self.lines)
        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise ValueError(f"Journal entry not balanced: debit={total_debit}, credit={total_credit}")
        return self

# Invoice with line items
class InvoiceCreate(BaseModel):
    entity_id: UUID
    customer_id: UUID
    invoice_date: date
    due_date: date
    currency: str = "SGD"
    line_items: List[InvoiceLineItem]
    notes: Optional[str]

# Financial Report Request
class ReportRequest(BaseModel):
    entity_id: UUID
    report_type: str  # pnl | balance_sheet | cash_flow | trial_balance | ar_aging | ap_aging | tax_summary | audit
    start_date: Optional[date]
    end_date: Optional[date]
    period_id: Optional[UUID]
    currency: str = "SGD"
    compare_previous: bool = False
    group_by: Optional[str]  # month | quarter | department
    format: str = "json"     # json | pdf | xlsx | csv
    include_zero_balances: bool = False
    consolidate_entities: bool = False  # Group consolidation
```

### 3.3 `service.py` — Business Logic Layer

Implement these service methods:

```python
class FinanceService:

    # ── Auto-numbering ──────────────────────────────────────────────────────
```python
# In service.py, each create method passes the MZ- prefixed string:
invoice_number  = await self.next_number(entity_id, "MZ-INV",  "fin_invoices",  "invoice_number")
quote_number    = await self.next_number(entity_id, "MZ-QUO",  "fin_quotes",    "quote_number")
bill_number     = await self.next_number(entity_id, "MZ-BILL", "fin_bills",     "bill_number")
payment_number  = await self.next_number(entity_id, "MZ-PMT",  "fin_payments",  "payment_number")
expense_number  = await self.next_number(entity_id, "MZ-EXP",  "fin_expenses",  "expense_number")
entry_number    = await self.next_number(entity_id, "MZ-JE",   "fin_journal_entries", "entry_number")
customer_code   = await self.next_number(entity_id, "MZ-CUST", "fin_customers", "customer_code")
vendor_code     = await self.next_number(entity_id, "MZ-VEND", "fin_vendors",   "vendor_code")
```

**Auto-number format:** `{MZ-PREFIX}-{YYYY}-{ZEROPADDED_SEQ}` — e.g. `MZ-INV-2025-0001`. Sequence resets per entity per year. Customer and vendor codes omit the year segment: `MZ-CUST-0001`, `MZ-VEND-0001`.

The `next_number()` method must be implemented as a **single atomic SQL operation** using `SELECT ... FOR UPDATE` or a PostgreSQL sequence per entity+prefix combination to prevent race conditions under concurrent writes.

    # ── Double-entry automation ─────────────────────────────────────────────
    async def post_invoice_to_ledger(self, invoice_id) -> UUID:
        """DR: Accounts Receivable | CR: Revenue + Tax Payable"""

    async def post_bill_to_ledger(self, bill_id) -> UUID:
        """DR: Expense accounts + Tax Receivable | CR: Accounts Payable"""

    async def post_payment_to_ledger(self, payment_id) -> UUID:
        """Receipt: DR Bank | CR AR | Payment: DR AP | CR Bank"""

    async def post_expense_to_ledger(self, expense_id) -> UUID:
        """DR: Expense account | CR: Bank or Payable"""

    # ── FX / Multi-currency ─────────────────────────────────────────────────
    async def convert_to_base(self, amount, from_currency, entity_id, date) -> Decimal:
        """Convert foreign currency amount to entity base currency"""

    async def get_fx_rate(self, from_currency, to_currency, date) -> Decimal:
        """Look up exchange rate from fin_exchange_rates, raise if missing"""

    # ── Period management ───────────────────────────────────────────────────
    async def close_period(self, period_id, user_id) -> dict:
        """Validate all entries posted, lock period, generate closing JEs"""

    # ── Reporting engine ───────────────────────────────────────────────────
    async def get_account_balance(self, account_id, start_date, end_date, currency) -> Decimal:
        """Sum debit/credit lines for period"""

    async def get_trial_balance(self, entity_id, as_at_date, currency) -> dict:
        """All account balances at date"""

    async def get_pnl(self, entity_id, start_date, end_date, currency, compare=False) -> dict:
        """Income - Expenses = Net Profit with category breakdown"""

    async def get_balance_sheet(self, entity_id, as_at_date, currency) -> dict:
        """Assets = Liabilities + Equity at date"""

    async def get_cash_flow(self, entity_id, start_date, end_date, currency) -> dict:
        """Operating + Investing + Financing cash flows (indirect method)"""

    async def get_ar_aging(self, entity_id, as_at_date, currency) -> dict:
        """Receivables by 0-30, 31-60, 61-90, 90+ days"""

    async def get_ap_aging(self, entity_id, as_at_date, currency) -> dict:
        """Payables by 0-30, 31-60, 61-90, 90+ days"""

    async def get_tax_summary(self, entity_id, period_id) -> dict:
        """GST/VAT output vs input, net payable"""

    async def get_consolidated(self, holding_entity_id, currency) -> dict:
        """Group consolidation: aggregate all subsidiary financials"""

    async def get_audit_trail(self, entity_id, start_date, end_date) -> list:
        """All journal entries with user, timestamp, changes"""

    async def get_finance_analysis(self, entity_id, period) -> dict:
        """Key ratios: current ratio, quick ratio, debt/equity, gross margin, net margin, ROE"""
```

---

## PHASE 4 — FASTAPI ROUTER (80+ endpoints)

### 4.1 Create `router.py`

Register all routes under prefix `/api/finance`. Group by resource:

```
/api/finance/entities          CRUD for legal entities
/api/finance/currencies        CRUD + FX rates
/api/finance/accounts          Chart of accounts CRUD
/api/finance/periods           Accounting periods + close period
/api/finance/journal           Create, post, reverse journal entries
/api/finance/customers         CRUD + list + convert from lead
/api/finance/vendors           CRUD + list
/api/finance/quotes            CRUD + send + convert to invoice
/api/finance/invoices          CRUD + send + record payment + void
/api/finance/bills             CRUD + approve + record payment
/api/finance/payments          CRUD + list by entity/date/type
/api/finance/bank-accounts     CRUD + reconciliation status
/api/finance/expenses          CRUD + approve + reject
/api/finance/shareholders      CRUD + equity summary
/api/finance/tax-codes         CRUD
/api/finance/tax-returns       Create + file + list
/api/finance/reports/pnl                  P&L report
/api/finance/reports/balance-sheet        Balance sheet
/api/finance/reports/cash-flow            Cash flow
/api/finance/reports/trial-balance        Trial balance
/api/finance/reports/ar-aging             AR aging
/api/finance/reports/ap-aging             AP aging
/api/finance/reports/tax-summary          Tax summary / GST F5
/api/finance/reports/audit                Audit report
/api/finance/reports/analysis             Finance ratios analysis
/api/finance/reports/consolidated         Group holding consolidation
/api/finance/reports/export/{report_type} Export as PDF/XLSX/CSV
```

Each endpoint must:
- Verify JWT + RBAC permission (`finance_read` for GETs, `finance_write` for mutations)
- Scope all queries to `entity_id` (data isolation)
- Log all write actions to `audit_log` table
- Return consistent envelope: `{"success": true, "data": ..., "meta": {...}}`

### 4.2 Register router in `main.py` (additive only)
```bash
# Audit first
grep -n "include_router" app/main.py
```
Add:
```python
from app.finance.router import finance_router
app.include_router(finance_router, prefix="/api/finance", tags=["Finance"])
```

---

## PHASE 5 — ENHANCED FINANCE AGENT

### 5.1 Audit existing finance agent
```bash
cat server/agents/finance_agent.py
```

### 5.2 Extend `finance_agent.py` (additive — add new capabilities block)

Add the following capabilities to the existing agent without touching existing methods:

```python
# New Finance Agent capabilities (appended to existing agent class)

FINANCE_AGENT_SYSTEM_PROMPT = """
You are the Mezzofy Finance Agent — a senior financial controller AI assistant.
You help the Finance Manager manage all aspects of Mezzofy's financial operations including:
- Double-entry bookkeeping and journal entries
- Multi-currency transactions across SG, HK, MY, CN entities
- Invoice and quote management (shared with Sales)
- Accounts Receivable and Payable
- Bank account management
- Expense management and approval workflows
- Shareholder and equity register
- Tax compliance (GST F5, corporate tax, withholding tax)
- Comprehensive financial reporting (P&L, Balance Sheet, Cash Flow, etc.)
- Group consolidation across holding and subsidiary entities
- Financial analysis and KPI monitoring

Always confirm destructive operations (posting, period close, void) before executing.
For report generation, default to current fiscal period unless specified.
When amounts are mentioned without currency, default to entity base currency.
Flag any entries that would cause the trial balance to be unbalanced.
"""

async def handle_journal_entry(self, task: dict) -> dict:
    """Natural language → structured journal entry"""

async def handle_invoice_creation(self, task: dict) -> dict:
    """Create invoice from natural language description"""

async def handle_report_generation(self, task: dict) -> dict:
    """Generate any financial report, optionally as PDF/XLSX and email"""

async def handle_ar_followup(self, task: dict) -> dict:
    """Identify overdue invoices, draft follow-up emails"""

async def handle_expense_approval(self, task: dict) -> dict:
    """Review and approve/reject pending expenses"""

async def handle_tax_preparation(self, task: dict) -> dict:
    """Prepare GST F5 return data for a period"""

async def handle_finance_analysis(self, task: dict) -> dict:
    """Compute and narrate financial KPIs and trends"""

async def handle_bank_reconciliation(self, task: dict) -> dict:
    """Match bank statement entries to recorded transactions"""
```

### 5.3 Finance Agent Tool Definitions (`agent_tools.py`)

```python
FINANCE_TOOLS = [
    {
        "name": "create_journal_entry",
        "description": "Create and optionally post a double-entry journal entry",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
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
                            "description": {"type": "string"}
                        }
                    }
                },
                "post_immediately": {"type": "boolean", "default": False}
            }
        }
    },
    {
        "name": "create_invoice",
        "description": "Create a customer invoice with line items",
    },
    {
        "name": "get_financial_report",
        "description": "Generate any financial report: pnl, balance_sheet, cash_flow, ar_aging, ap_aging, trial_balance, tax_summary, audit, analysis, consolidated",
    },
    {
        "name": "list_overdue_invoices",
        "description": "List overdue invoices with days outstanding and customer details",
    },
    {
        "name": "record_payment",
        "description": "Record a customer payment against an invoice or a vendor payment against a bill",
    },
    {
        "name": "approve_expense",
        "description": "Approve or reject a pending expense claim",
    },
    {
        "name": "get_account_balance",
        "description": "Get current balance of any GL account",
    },
    {
        "name": "close_period",
        "description": "Close an accounting period after validation",
    },
    {
        "name": "export_report",
        "description": "Export any financial report as PDF, XLSX or CSV",
    }
]
```

### 5.4 Scheduled Finance Tasks — extend `scheduler/beat_schedule.py`

Add (audit existing first with `cat`):
```python
# Finance scheduled tasks
"daily-overdue-invoice-check": {
    "task": "finance.check_overdue_invoices",
    "schedule": crontab(hour=8, minute=30),    # 16:30 HKT daily
    "description": "Flag newly overdue invoices, post to #finance Teams"
},
"weekly-ar-ap-summary": {
    "task": "finance.ar_ap_weekly_summary",
    "schedule": crontab(day_of_week=1, hour=1, minute=0),  # Mon 09:00 HKT
    "description": "AR aging + AP aging summary to finance manager"
},
"monthly-financial-close-reminder": {
    "task": "finance.month_close_reminder",
    "schedule": crontab(day_of_month=25, hour=1, minute=0),  # 25th 09:00 HKT
    "description": "Remind finance manager to close month-end"
},
"quarterly-gst-reminder": {
    "task": "finance.gst_filing_reminder",
    "schedule": crontab(month_of_year="1,4,7,10", day_of_month=15, hour=1),
    "description": "GST F5 filing reminder 15th of quarter-end month"
},
"monthly-financial-statements": {
    "task": "finance.generate_monthly_statements",
    "schedule": crontab(day_of_month=2, hour=1, minute=30),  # 2nd 09:30 HKT
    "description": "Auto-generate P&L, BS, CF for previous month → email CFO + Teams"
}
```

---

## PHASE 6 — DOCUMENT GENERATION (Reports as PDF/XLSX)

### 6.1 Create `reports.py` — Report Generation Engine

Use Claude Skills API as primary, reportlab/openpyxl as fallback. All reports support:
- Multi-currency display with FX rates footnotes
- Comparative period columns (current vs. prior)
- Entity/group consolidation header
- Mezzofy brand colors (#1a73e8 primary, #34a853 positive, #ea4335 negative)
- Page headers with entity name, report type, period, generated date/time

**Report templates to implement:**

```python
async def generate_pnl_pdf(data: dict, entity: dict, period: str) -> bytes:
    """P&L Statement: Revenue → Gross Profit → EBITDA → Net Profit"""

async def generate_balance_sheet_pdf(data: dict, entity: dict, date: str) -> bytes:
    """Balance Sheet: Assets || Liabilities + Equity (must balance)"""

async def generate_cash_flow_pdf(data: dict, entity: dict, period: str) -> bytes:
    """Cash Flow Statement: Operating + Investing + Financing"""

async def generate_trial_balance_xlsx(data: dict, entity: dict) -> bytes:
    """Trial Balance with debit/credit columns and totals"""

async def generate_ar_aging_xlsx(data: dict, entity: dict) -> bytes:
    """AR Aging: Customer | Current | 1-30 | 31-60 | 61-90 | 90+ | Total"""

async def generate_ap_aging_xlsx(data: dict, entity: dict) -> bytes:
    """AP Aging: Vendor | Current | 1-30 | 31-60 | 61-90 | 90+ | Total"""

async def generate_gst_f5_pdf(data: dict, entity: dict, period: str) -> bytes:
    """Singapore GST F5 Return format"""

async def generate_audit_report_pdf(data: dict, entity: dict, period: str) -> bytes:
    """Audit trail: Date | User | Action | Before | After | IP"""

async def generate_finance_analysis_pdf(data: dict, entity: dict) -> bytes:
    """KPI dashboard: ratios, trends, charts (using matplotlib or SVG)"""

async def generate_consolidated_report_pdf(data: dict, holding: dict) -> bytes:
    """Group consolidation: subsidiary columns + elimination + group total"""

async def generate_invoice_pdf(invoice: dict, entity: dict) -> bytes:
    """Branded invoice: Mezzofy logo, entity details, line items, totals, bank details"""

async def generate_quote_pdf(quote: dict, entity: dict) -> bytes:
    """Branded quote: same layout as invoice with validity date"""
```

---

## PHASE 7 — PORTAL: FINANCE SECTION (React Web App)

### 7.1 Audit existing Portal structure
```bash
ls portal/src/pages/
ls portal/src/components/
cat portal/src/App.tsx | grep -A3 "Route"
```

### 7.2 Create Finance Portal section — 12 new pages

Create the following files under `portal/src/pages/Finance/`:

```
Finance/
├── index.tsx                    # Finance dashboard: KPI cards, AR/AP summary, recent JEs
├── Entities.tsx                 # Legal entities list + create/edit drawer
├── ChartOfAccounts.tsx          # Hierarchical account tree + create/edit
├── JournalEntries.tsx           # Journal entry list with filter, search, post action
├── JournalEntryNew.tsx          # Multi-line journal entry form with balance validator
├── Customers.tsx                # Customer list with AR balance, filter, create from lead
├── Vendors.tsx                  # Vendor list with AP balance
├── Quotes.tsx                   # Quote list + status filter + convert to invoice
├── QuoteNew.tsx                 # Quote builder with line items, tax, preview
├── Invoices.tsx                 # Invoice list + status filter + record payment modal
├── InvoiceNew.tsx               # Invoice builder (similar to quote)
├── Bills.tsx                    # AP bills list + approve + record payment
├── Payments.tsx                 # Payment history with filters
├── BankAccounts.tsx             # Bank account list + reconciliation status
├── Expenses.tsx                 # Expense list + approval queue
├── Shareholders.tsx             # Equity register table + ownership pie chart
├── TaxCodes.tsx                 # Tax code setup
├── TaxReturns.tsx               # GST/tax filing log
├── Periods.tsx                  # Accounting periods + close period action
└── Reports.tsx                  # Report generator: select type + date + entity + export
```

### 7.3 Finance Dashboard (`Finance/index.tsx`)

Key components on the dashboard:
- **KPI Cards Row**: Total AR Outstanding | Total AP Outstanding | Cash Balance | Net P&L MTD
- **AR Aging Chart**: Stacked bar chart by aging bucket
- **AP Aging Chart**: Stacked bar chart
- **Recent Journal Entries**: Last 10 with status badge
- **Overdue Invoices Alert**: Count + link to Invoices page
- **Quick Actions**: + New Invoice | + New Bill | + Journal Entry | Generate Report
- **Entity Selector**: Dropdown to switch between legal entities

### 7.4 Register Finance routes in `App.tsx` (additive)
```tsx
// Finance routes — additive only, audit existing routes first
<Route path="/finance" element={<PrivateRoute permission="finance_read"><Finance /></PrivateRoute>} />
<Route path="/finance/journal" element={<JournalEntries />} />
<Route path="/finance/journal/new" element={<JournalEntryNew />} />
<Route path="/finance/invoices" element={<Invoices />} />
<Route path="/finance/invoices/new" element={<InvoiceNew />} />
<Route path="/finance/quotes" element={<Quotes />} />
<Route path="/finance/quotes/new" element={<QuoteNew />} />
<Route path="/finance/customers" element={<Customers />} />
<Route path="/finance/vendors" element={<Vendors />} />
<Route path="/finance/bills" element={<Bills />} />
<Route path="/finance/payments" element={<Payments />} />
<Route path="/finance/bank-accounts" element={<BankAccounts />} />
<Route path="/finance/expenses" element={<Expenses />} />
<Route path="/finance/shareholders" element={<Shareholders />} />
<Route path="/finance/reports" element={<Reports />} />
<Route path="/finance/entities" element={<Entities />} />
<Route path="/finance/accounts" element={<ChartOfAccounts />} />
<Route path="/finance/periods" element={<Periods />} />
<Route path="/finance/tax" element={<TaxReturns />} />
```

### 7.5 Add Finance to sidebar navigation
Add Finance section to the existing sidebar component with the following nav items:
- 📊 Dashboard (Finance)
- 📖 Journal Entries
- 🧾 Invoices
- 💬 Quotes
- 📥 Bills (AP)
- 💳 Payments
- 👥 Customers
- 🏢 Vendors
- 🏦 Bank Accounts
- 💸 Expenses
- 📋 Reports
- ⚙️ Settings (Entities, CoA, Periods, Tax Codes, Shareholders)

---

## PHASE 8 — VALIDATION, KNOWLEDGE BASE UPDATE & TESTS

### 8.1 Update Finance Agent knowledge base
Create `server/knowledge/finance/`:
```
finance/
├── chart_of_accounts_template.json    # Default SG CoA (SFRS-aligned)
├── gst_codes_sg.json                  # Singapore GST tax codes
├── tax_codes_hk.json                  # HK tax codes
├── accounting_practices.md            # Double-entry rules, common JE patterns
├── report_formulas.md                 # Exact formulas for each report line item
└── fiscal_calendar.json              # Default fiscal year configs by country
```

### 8.2 Validate double-entry integrity
Add DB constraint check:
```sql
-- Ensure no journal entry has imbalanced lines when posted
CREATE OR REPLACE FUNCTION check_journal_balance() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'posted' THEN
        IF (SELECT ABS(SUM(debit_amount) - SUM(credit_amount)) FROM fin_journal_lines WHERE journal_entry_id = NEW.id) > 0.01 THEN
            RAISE EXCEPTION 'Journal entry is not balanced';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_journal_balance
BEFORE UPDATE ON fin_journal_entries
FOR EACH ROW EXECUTE FUNCTION check_journal_balance();
```

### 8.3 Add finance workflow tests to `TESTING.md`

Document these test scenarios:
```
Finance: Create Invoice → Post to Ledger → Record Payment → Check AR = 0
Finance: Create Journal Entry with unbalanced lines → Expect 422 validation error
Finance: Generate P&L for current month as PDF → Email to CFO
Finance: Multi-currency invoice (USD) → Verify base currency conversion stored
Finance: AR Aging report → Verify correct aging buckets
Finance: Group Consolidation → Sum all entity P&Ls
Finance: Close Period → Verify no further postings allowed
Finance: GST F5 Preparation → Correct output vs input tax
Finance: Agent: "Show me overdue invoices" → Returns AR aging summary
Finance: Agent: "Generate this month's P&L as PDF and send to CEO"
```

### 8.4 Verify installation
```bash
# Confirm all tables created
psql $DATABASE_URL -c "\dt fin_*"

# Confirm router registered
grep -n "finance" app/main.py

# Confirm agent extended
grep -n "def handle_" agents/finance_agent.py

# Confirm portal pages exist
ls portal/src/pages/Finance/

# Run a quick API smoke test
curl -H "Authorization: Bearer $TEST_TOKEN" http://localhost:8000/api/finance/entities
```

---

## IMPLEMENTATION NOTES

1. **No restarts** — Do not restart FastAPI, Celery, or Celery Beat at any point. New routes and tasks will be picked up on the next natural restart cycle.
2. **Additive only** — Every file creation must check for existing content first. Use `cat` before `write`.
3. **Audit log** — Every write to any `fin_*` table must produce an entry in the existing `audit_log` table with `department='finance'`.
4. **Currency precision** — Always use `NUMERIC(20,6)` for money, never `FLOAT`. Round display to 2 decimal places only at presentation layer.
5. **Entity scoping** — Every query must filter by `entity_id`. Never return cross-entity data unless the user has `finance_entities` permission and explicitly requests consolidation.
6. **Sequential phase execution** — Complete each phase fully before starting the next. Run the migration (`alembic upgrade head`) before writing any Python that references the new tables.
7. **FX rate fallback** — If no exchange rate exists for a date, use the most recent available rate and log a warning to the audit trail.
8. **Invoice/Quote PDF branding** — Use the Mezzofy brand guidelines from `server/knowledge/brand_guidelines_v2.md`.

---

*End of Finance Module Claude Code Prompt v1.1 — Updated: MZ- prefix applied to all auto-numbering*
