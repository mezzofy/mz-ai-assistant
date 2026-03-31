"""Finance Module — 19 fin_* tables, 8 indexes, journal balance trigger

Revision ID: 004_finance_module
Revises: None
Create Date: 2026-03-31

Note: This is the first Alembic migration in this project.
      Prior schema changes were applied via raw SQL in server/app/db/migrations/.
      Prerequisites (must already exist in DB before running this migration):
        - users table
        - sales_leads table
"""

from alembic import op

# revision identifiers, used by Alembic
revision = '004_finance_module'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
-- ============================================================
-- Finance Module — 19 fin_* tables
-- All monetary columns use NUMERIC(20,6)
-- All tables use IF NOT EXISTS guards
-- Dependency order: referenced tables created before referencing tables
-- ============================================================

-- 1. fin_currencies
CREATE TABLE IF NOT EXISTS fin_currencies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(10) UNIQUE NOT NULL,
    name            TEXT,
    symbol          VARCHAR(10),
    is_base         BOOL DEFAULT false,
    decimal_places  INT DEFAULT 2,
    is_active       BOOL DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. fin_exchange_rates
CREATE TABLE IF NOT EXISTS fin_exchange_rates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency   VARCHAR(10),
    to_currency     VARCHAR(10),
    rate            NUMERIC(20,10),
    effective_date  DATE,
    source          TEXT DEFAULT 'manual',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_currency, to_currency, effective_date)
);

-- 3. fin_entities  (self-referencing parent_entity_id)
CREATE TABLE IF NOT EXISTS fin_entities (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                    VARCHAR(20) UNIQUE,
    name                    TEXT,
    entity_type             TEXT,
    country_code            VARCHAR(5),
    base_currency           VARCHAR(10) DEFAULT 'SGD',
    parent_entity_id        UUID REFERENCES fin_entities(id),
    tax_id                  TEXT,
    registered_address      TEXT,
    fiscal_year_start       INT DEFAULT 1,
    is_active               BOOL DEFAULT true,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- 4. fin_account_categories  (self-referencing parent_id)
CREATE TABLE IF NOT EXISTS fin_account_categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    code            VARCHAR(20),
    name            TEXT,
    account_type    TEXT,
    normal_balance  TEXT,
    display_order   INT DEFAULT 0,
    parent_id       UUID REFERENCES fin_account_categories(id),
    UNIQUE(entity_id, code)
);

-- 5. fin_accounts
CREATE TABLE IF NOT EXISTS fin_accounts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id               UUID REFERENCES fin_entities(id),
    category_id             UUID REFERENCES fin_account_categories(id),
    code                    VARCHAR(30),
    name                    TEXT,
    description             TEXT,
    currency                VARCHAR(10) DEFAULT 'SGD',
    is_bank_account         BOOL DEFAULT false,
    is_control              BOOL DEFAULT false,
    allow_direct_posting    BOOL DEFAULT true,
    is_active               BOOL DEFAULT true,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, code)
);

-- 6. fin_periods
CREATE TABLE IF NOT EXISTS fin_periods (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    name            TEXT,
    period_type     TEXT,
    start_date      DATE,
    end_date        DATE,
    status          TEXT DEFAULT 'open',
    closed_by       UUID REFERENCES users(id),
    closed_at       TIMESTAMPTZ,
    UNIQUE(entity_id, start_date, period_type)
);

-- 7. fin_journal_entries  (self-referencing reversed_by)
CREATE TABLE IF NOT EXISTS fin_journal_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    period_id       UUID REFERENCES fin_periods(id),
    entry_number    TEXT,
    entry_date      DATE,
    description     TEXT,
    reference       TEXT,
    source          TEXT DEFAULT 'manual',
    currency        VARCHAR(10) DEFAULT 'SGD',
    exchange_rate   NUMERIC(20,10) DEFAULT 1,
    status          TEXT DEFAULT 'draft',
    created_by      UUID REFERENCES users(id),
    posted_by       UUID REFERENCES users(id),
    posted_at       TIMESTAMPTZ,
    reversed_by     UUID REFERENCES fin_journal_entries(id),
    tags            JSONB DEFAULT '[]',
    attachments     JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, entry_number)
);

-- 8. fin_journal_lines
CREATE TABLE IF NOT EXISTS fin_journal_lines (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_entry_id    UUID REFERENCES fin_journal_entries(id) ON DELETE CASCADE,
    account_id          UUID REFERENCES fin_accounts(id),
    description         TEXT,
    debit_amount        NUMERIC(20,6) DEFAULT 0,
    credit_amount       NUMERIC(20,6) DEFAULT 0,
    currency            VARCHAR(10),
    base_amount         NUMERIC(20,6),
    tax_code            TEXT,
    cost_center         TEXT,
    project_ref         TEXT,
    line_order          INT DEFAULT 0
);

-- 9. fin_customers
CREATE TABLE IF NOT EXISTS fin_customers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    lead_id             UUID REFERENCES sales_leads(id),
    customer_code       TEXT,
    name                TEXT,
    company_name        TEXT,
    email               TEXT,
    phone               TEXT,
    billing_address     JSONB,
    shipping_address    JSONB,
    currency            VARCHAR(10) DEFAULT 'SGD',
    payment_terms       INT DEFAULT 30,
    credit_limit        NUMERIC(20,6),
    tax_id              TEXT,
    notes               TEXT,
    is_active           BOOL DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, customer_code)
);

-- 10. fin_vendors
CREATE TABLE IF NOT EXISTS fin_vendors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    vendor_code     TEXT,
    name            TEXT,
    company_name    TEXT,
    email           TEXT,
    phone           TEXT,
    billing_address JSONB,
    currency        VARCHAR(10) DEFAULT 'SGD',
    payment_terms   INT DEFAULT 30,
    bank_details    JSONB,
    tax_id          TEXT,
    is_active       BOOL DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, vendor_code)
);

-- 11. fin_quotes
CREATE TABLE IF NOT EXISTS fin_quotes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    quote_number        TEXT,
    customer_id         UUID REFERENCES fin_customers(id),
    lead_id             UUID REFERENCES sales_leads(id),
    quote_date          DATE,
    expiry_date         DATE,
    currency            VARCHAR(10) DEFAULT 'SGD',
    exchange_rate       NUMERIC(20,10) DEFAULT 1,
    subtotal            NUMERIC(20,6) DEFAULT 0,
    tax_amount          NUMERIC(20,6) DEFAULT 0,
    discount_amount     NUMERIC(20,6) DEFAULT 0,
    total_amount        NUMERIC(20,6) DEFAULT 0,
    status              TEXT DEFAULT 'draft',
    terms               TEXT,
    notes               TEXT,
    line_items          JSONB NOT NULL DEFAULT '[]',
    created_by          UUID REFERENCES users(id),
    sent_at             TIMESTAMPTZ,
    converted_to_invoice UUID,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, quote_number)
);

-- 12. fin_invoices
CREATE TABLE IF NOT EXISTS fin_invoices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    invoice_number      TEXT,
    customer_id         UUID REFERENCES fin_customers(id),
    quote_id            UUID REFERENCES fin_quotes(id),
    invoice_date        DATE,
    due_date            DATE,
    currency            VARCHAR(10) DEFAULT 'SGD',
    exchange_rate       NUMERIC(20,10) DEFAULT 1,
    subtotal            NUMERIC(20,6) DEFAULT 0,
    tax_amount          NUMERIC(20,6) DEFAULT 0,
    discount_amount     NUMERIC(20,6) DEFAULT 0,
    total_amount        NUMERIC(20,6) DEFAULT 0,
    paid_amount         NUMERIC(20,6) DEFAULT 0,
    outstanding         NUMERIC(20,6) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    status              TEXT DEFAULT 'draft',
    line_items          JSONB NOT NULL DEFAULT '[]',
    payment_terms       INT DEFAULT 30,
    notes               TEXT,
    created_by          UUID REFERENCES users(id),
    sent_at             TIMESTAMPTZ,
    paid_at             TIMESTAMPTZ,
    journal_entry_id    UUID REFERENCES fin_journal_entries(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, invoice_number)
);

-- 13. fin_bills
CREATE TABLE IF NOT EXISTS fin_bills (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    bill_number         TEXT,
    vendor_id           UUID REFERENCES fin_vendors(id),
    bill_date           DATE,
    due_date            DATE,
    reference           TEXT,
    currency            VARCHAR(10) DEFAULT 'SGD',
    exchange_rate       NUMERIC(20,10) DEFAULT 1,
    subtotal            NUMERIC(20,6) DEFAULT 0,
    tax_amount          NUMERIC(20,6) DEFAULT 0,
    total_amount        NUMERIC(20,6) DEFAULT 0,
    paid_amount         NUMERIC(20,6) DEFAULT 0,
    outstanding         NUMERIC(20,6) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    status              TEXT DEFAULT 'pending',
    line_items          JSONB NOT NULL DEFAULT '[]',
    notes               TEXT,
    approved_by         UUID REFERENCES users(id),
    journal_entry_id    UUID REFERENCES fin_journal_entries(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, bill_number)
);

-- 14. fin_bank_accounts
CREATE TABLE IF NOT EXISTS fin_bank_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    account_id          UUID REFERENCES fin_accounts(id),
    bank_name           TEXT,
    account_name        TEXT,
    account_number      TEXT,
    swift_code          TEXT,
    iban                TEXT,
    currency            VARCHAR(10) NOT NULL,
    current_balance     NUMERIC(20,6) DEFAULT 0,
    last_reconciled     DATE,
    is_active           BOOL DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 15. fin_payments
CREATE TABLE IF NOT EXISTS fin_payments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    payment_number      TEXT,
    payment_type        TEXT,
    payment_date        DATE,
    bank_account_id     UUID REFERENCES fin_bank_accounts(id),
    customer_id         UUID REFERENCES fin_customers(id),
    vendor_id           UUID REFERENCES fin_vendors(id),
    invoice_id          UUID REFERENCES fin_invoices(id),
    bill_id             UUID REFERENCES fin_bills(id),
    currency            VARCHAR(10) NOT NULL,
    amount              NUMERIC(20,6) NOT NULL,
    exchange_rate       NUMERIC(20,10) DEFAULT 1,
    payment_method      TEXT,
    reference           TEXT,
    notes               TEXT,
    journal_entry_id    UUID REFERENCES fin_journal_entries(id),
    created_by          UUID REFERENCES users(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, payment_number)
);

-- 16. fin_expenses
CREATE TABLE IF NOT EXISTS fin_expenses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    expense_number      TEXT,
    expense_date        DATE,
    category            TEXT,
    description         TEXT,
    vendor_name         TEXT,
    vendor_id           UUID REFERENCES fin_vendors(id),
    account_id          UUID REFERENCES fin_accounts(id),
    currency            VARCHAR(10) NOT NULL,
    amount              NUMERIC(20,6) NOT NULL,
    tax_amount          NUMERIC(20,6) DEFAULT 0,
    status              TEXT DEFAULT 'pending',
    submitted_by        UUID REFERENCES users(id),
    approved_by         UUID REFERENCES users(id),
    receipt_path        TEXT,
    journal_entry_id    UUID REFERENCES fin_journal_entries(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, expense_number)
);

-- 17. fin_shareholders
CREATE TABLE IF NOT EXISTS fin_shareholders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    name                TEXT,
    shareholder_type    TEXT,
    id_number           TEXT,
    nationality         TEXT,
    address             JSONB,
    share_class         TEXT DEFAULT 'ordinary',
    shares_held         NUMERIC(20,0) DEFAULT 0,
    par_value           NUMERIC(20,6) DEFAULT 1,
    total_paid          NUMERIC(20,6) DEFAULT 0,
    ownership_pct       NUMERIC(8,4),
    effective_date      DATE,
    is_active           BOOL DEFAULT true,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 18. fin_tax_codes
CREATE TABLE IF NOT EXISTS fin_tax_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    code            TEXT,
    name            TEXT,
    tax_type        TEXT,
    rate            NUMERIC(8,4),
    country_code    VARCHAR(5),
    applies_to      TEXT DEFAULT 'both',
    gl_account_id   UUID REFERENCES fin_accounts(id),
    is_active       BOOL DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, code)
);

-- 19. fin_tax_returns
CREATE TABLE IF NOT EXISTS fin_tax_returns (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id           UUID REFERENCES fin_entities(id),
    period_id           UUID REFERENCES fin_periods(id),
    tax_type            TEXT,
    filing_period       TEXT,
    due_date            DATE,
    filed_date          DATE,
    total_tax_due       NUMERIC(20,6) DEFAULT 0,
    total_tax_paid      NUMERIC(20,6) DEFAULT 0,
    status              TEXT DEFAULT 'pending',
    submission_ref      TEXT,
    notes               TEXT,
    generated_by        UUID REFERENCES users(id),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Performance Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_fin_je_entity_date ON fin_journal_entries(entity_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_fin_je_period ON fin_journal_entries(period_id);
CREATE INDEX IF NOT EXISTS idx_fin_jl_account ON fin_journal_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_fin_invoices_customer ON fin_invoices(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_fin_invoices_due ON fin_invoices(due_date, status);
CREATE INDEX IF NOT EXISTS idx_fin_bills_vendor ON fin_bills(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_fin_payments_date ON fin_payments(payment_date, entity_id);
CREATE INDEX IF NOT EXISTS idx_fin_expenses_date ON fin_expenses(expense_date, entity_id);

-- ============================================================
-- Journal Balance Trigger
-- Enforces that posted journal entries must be balanced (debits = credits)
-- ============================================================

CREATE OR REPLACE FUNCTION check_journal_balance() RETURNS trigger AS $$
BEGIN
    IF NEW.status = 'posted' THEN
        IF (SELECT ABS(SUM(debit_amount) - SUM(credit_amount))
            FROM fin_journal_lines
            WHERE journal_entry_id = NEW.id) > 0.01 THEN
            RAISE EXCEPTION 'Journal entry % is not balanced', NEW.entry_number;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_journal_balance
    BEFORE UPDATE ON fin_journal_entries
    FOR EACH ROW EXECUTE FUNCTION check_journal_balance();
""")


def downgrade() -> None:
    op.execute("""
-- Drop trigger and function first
DROP TRIGGER IF EXISTS enforce_journal_balance ON fin_journal_entries;
DROP FUNCTION IF EXISTS check_journal_balance();

-- Drop indexes
DROP INDEX IF EXISTS idx_fin_expenses_date;
DROP INDEX IF EXISTS idx_fin_payments_date;
DROP INDEX IF EXISTS idx_fin_bills_vendor;
DROP INDEX IF EXISTS idx_fin_invoices_due;
DROP INDEX IF EXISTS idx_fin_invoices_customer;
DROP INDEX IF EXISTS idx_fin_jl_account;
DROP INDEX IF EXISTS idx_fin_je_period;
DROP INDEX IF EXISTS idx_fin_je_entity_date;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS fin_tax_returns;
DROP TABLE IF EXISTS fin_tax_codes;
DROP TABLE IF EXISTS fin_shareholders;
DROP TABLE IF EXISTS fin_expenses;
DROP TABLE IF EXISTS fin_payments;
DROP TABLE IF EXISTS fin_bank_accounts;
DROP TABLE IF EXISTS fin_bills;
DROP TABLE IF EXISTS fin_invoices;
DROP TABLE IF EXISTS fin_quotes;
DROP TABLE IF EXISTS fin_vendors;
DROP TABLE IF EXISTS fin_customers;
DROP TABLE IF EXISTS fin_journal_lines;
DROP TABLE IF EXISTS fin_journal_entries;
DROP TABLE IF EXISTS fin_periods;
DROP TABLE IF EXISTS fin_accounts;
DROP TABLE IF EXISTS fin_account_categories;
DROP TABLE IF EXISTS fin_entities;
DROP TABLE IF EXISTS fin_exchange_rates;
DROP TABLE IF EXISTS fin_currencies;
""")
