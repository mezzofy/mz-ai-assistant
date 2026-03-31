#!/usr/bin/env python3
"""
Finance Module — Database Migration Script
Creates 19 fin_* tables, 8 indexes, and the double-entry balance trigger.
Safe to re-run: uses CREATE TABLE IF NOT EXISTS + IF NOT EXISTS guards throughout.

Usage:
    cd server
    venv/bin/python scripts/migrate_finance.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv("config/.env")

import psycopg2


def get_connection():
    db_url = os.getenv("DATABASE_URL", "")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if not sync_url:
        sync_url = "postgresql://mezzofy_ai:password@localhost:5432/mezzofy_ai"
    return psycopg2.connect(sync_url)


FINANCE_SQL = """
-- ─── MULTI-CURRENCY & ENTITY FOUNDATION ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS fin_currencies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(10) UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    symbol          VARCHAR(10),
    is_base         BOOLEAN DEFAULT false,
    decimal_places  INT DEFAULT 2,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fin_exchange_rates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency   VARCHAR(10) NOT NULL,
    to_currency     VARCHAR(10) NOT NULL,
    rate            NUMERIC(20,10) NOT NULL,
    effective_date  DATE NOT NULL,
    source          TEXT DEFAULT 'manual',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_currency, to_currency, effective_date)
);

CREATE TABLE IF NOT EXISTS fin_entities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                VARCHAR(20) UNIQUE NOT NULL,
    name                TEXT NOT NULL,
    entity_type         TEXT NOT NULL,
    country_code        VARCHAR(5),
    base_currency       VARCHAR(10) DEFAULT 'SGD',
    parent_entity_id    UUID REFERENCES fin_entities(id),
    tax_id              TEXT,
    registered_address  TEXT,
    fiscal_year_start   INT DEFAULT 1,
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─── CHART OF ACCOUNTS ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fin_account_categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    code            VARCHAR(20) NOT NULL,
    name            TEXT NOT NULL,
    account_type    TEXT NOT NULL,
    normal_balance  TEXT NOT NULL,
    display_order   INT DEFAULT 0,
    parent_id       UUID REFERENCES fin_account_categories(id),
    UNIQUE(entity_id, code)
);

CREATE TABLE IF NOT EXISTS fin_accounts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id               UUID REFERENCES fin_entities(id),
    category_id             UUID REFERENCES fin_account_categories(id),
    code                    VARCHAR(30) NOT NULL,
    name                    TEXT NOT NULL,
    description             TEXT,
    currency                VARCHAR(10) DEFAULT 'SGD',
    is_bank_account         BOOLEAN DEFAULT false,
    is_control              BOOLEAN DEFAULT false,
    allow_direct_posting    BOOLEAN DEFAULT true,
    is_active               BOOLEAN DEFAULT true,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, code)
);

-- ─── JOURNAL & LEDGER ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fin_periods (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    name            TEXT NOT NULL,
    period_type     TEXT NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    status          TEXT DEFAULT 'open',
    closed_by       UUID REFERENCES users(id),
    closed_at       TIMESTAMPTZ,
    UNIQUE(entity_id, start_date, period_type)
);

CREATE TABLE IF NOT EXISTS fin_journal_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    period_id       UUID REFERENCES fin_periods(id),
    entry_number    TEXT NOT NULL,
    entry_date      DATE NOT NULL,
    description     TEXT NOT NULL,
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

-- ─── CUSTOMERS & VENDORS ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fin_customers (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id        UUID REFERENCES fin_entities(id),
    lead_id          UUID REFERENCES sales_leads(id),
    customer_code    TEXT NOT NULL,
    name             TEXT NOT NULL,
    company_name     TEXT,
    email            TEXT,
    phone            TEXT,
    billing_address  JSONB,
    shipping_address JSONB,
    currency         VARCHAR(10) DEFAULT 'SGD',
    payment_terms    INT DEFAULT 30,
    credit_limit     NUMERIC(20,6),
    tax_id           TEXT,
    notes            TEXT,
    is_active        BOOLEAN DEFAULT true,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, customer_code)
);

CREATE TABLE IF NOT EXISTS fin_vendors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    vendor_code     TEXT NOT NULL,
    name            TEXT NOT NULL,
    company_name    TEXT,
    email           TEXT,
    phone           TEXT,
    billing_address JSONB,
    currency        VARCHAR(10) DEFAULT 'SGD',
    payment_terms   INT DEFAULT 30,
    bank_details    JSONB,
    tax_id          TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, vendor_code)
);

-- ─── INVOICES & QUOTES ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fin_quotes (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id            UUID REFERENCES fin_entities(id),
    quote_number         TEXT NOT NULL,
    customer_id          UUID REFERENCES fin_customers(id),
    lead_id              UUID REFERENCES sales_leads(id),
    quote_date           DATE NOT NULL,
    expiry_date          DATE,
    currency             VARCHAR(10) DEFAULT 'SGD',
    exchange_rate        NUMERIC(20,10) DEFAULT 1,
    subtotal             NUMERIC(20,6) DEFAULT 0,
    tax_amount           NUMERIC(20,6) DEFAULT 0,
    discount_amount      NUMERIC(20,6) DEFAULT 0,
    total_amount         NUMERIC(20,6) DEFAULT 0,
    status               TEXT DEFAULT 'draft',
    terms                TEXT,
    notes                TEXT,
    line_items           JSONB NOT NULL DEFAULT '[]',
    created_by           UUID REFERENCES users(id),
    sent_at              TIMESTAMPTZ,
    converted_to_invoice UUID,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, quote_number)
);

CREATE TABLE IF NOT EXISTS fin_invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    invoice_number  TEXT NOT NULL,
    customer_id     UUID REFERENCES fin_customers(id),
    quote_id        UUID REFERENCES fin_quotes(id),
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
    status          TEXT DEFAULT 'draft',
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

CREATE TABLE IF NOT EXISTS fin_bills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES fin_entities(id),
    bill_number     TEXT NOT NULL,
    vendor_id       UUID REFERENCES fin_vendors(id),
    bill_date       DATE NOT NULL,
    due_date        DATE NOT NULL,
    reference       TEXT,
    currency        VARCHAR(10) DEFAULT 'SGD',
    exchange_rate   NUMERIC(20,10) DEFAULT 1,
    subtotal        NUMERIC(20,6) DEFAULT 0,
    tax_amount      NUMERIC(20,6) DEFAULT 0,
    total_amount    NUMERIC(20,6) DEFAULT 0,
    paid_amount     NUMERIC(20,6) DEFAULT 0,
    outstanding     NUMERIC(20,6) GENERATED ALWAYS AS (total_amount - paid_amount) STORED,
    status          TEXT DEFAULT 'pending',
    line_items      JSONB NOT NULL DEFAULT '[]',
    notes           TEXT,
    approved_by     UUID REFERENCES users(id),
    journal_entry_id UUID REFERENCES fin_journal_entries(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, bill_number)
);

-- ─── PAYMENTS & BANK ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fin_bank_accounts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id        UUID REFERENCES fin_entities(id),
    account_id       UUID REFERENCES fin_accounts(id),
    bank_name        TEXT NOT NULL,
    account_name     TEXT NOT NULL,
    account_number   TEXT,
    swift_code       TEXT,
    iban             TEXT,
    currency         VARCHAR(10) NOT NULL,
    current_balance  NUMERIC(20,6) DEFAULT 0,
    last_reconciled  DATE,
    is_active        BOOLEAN DEFAULT true,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fin_payments (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id        UUID REFERENCES fin_entities(id),
    payment_number   TEXT NOT NULL,
    payment_type     TEXT NOT NULL,
    payment_date     DATE NOT NULL,
    bank_account_id  UUID REFERENCES fin_bank_accounts(id),
    customer_id      UUID REFERENCES fin_customers(id),
    vendor_id        UUID REFERENCES fin_vendors(id),
    invoice_id       UUID REFERENCES fin_invoices(id),
    bill_id          UUID REFERENCES fin_bills(id),
    currency         VARCHAR(10) NOT NULL,
    amount           NUMERIC(20,6) NOT NULL,
    exchange_rate    NUMERIC(20,10) DEFAULT 1,
    payment_method   TEXT,
    reference        TEXT,
    notes            TEXT,
    journal_entry_id UUID REFERENCES fin_journal_entries(id),
    created_by       UUID REFERENCES users(id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, payment_number)
);

-- ─── EXPENSES & SHAREHOLDERS ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fin_expenses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id        UUID REFERENCES fin_entities(id),
    expense_number   TEXT NOT NULL,
    expense_date     DATE NOT NULL,
    category         TEXT NOT NULL,
    description      TEXT NOT NULL,
    vendor_name      TEXT,
    vendor_id        UUID REFERENCES fin_vendors(id),
    account_id       UUID REFERENCES fin_accounts(id),
    currency         VARCHAR(10) NOT NULL,
    amount           NUMERIC(20,6) NOT NULL,
    tax_amount       NUMERIC(20,6) DEFAULT 0,
    status           TEXT DEFAULT 'pending',
    submitted_by     UUID REFERENCES users(id),
    approved_by      UUID REFERENCES users(id),
    receipt_path     TEXT,
    journal_entry_id UUID REFERENCES fin_journal_entries(id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, expense_number)
);

CREATE TABLE IF NOT EXISTS fin_shareholders (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id        UUID REFERENCES fin_entities(id),
    name             TEXT NOT NULL,
    shareholder_type TEXT NOT NULL,
    id_number        TEXT,
    nationality      TEXT,
    address          JSONB,
    share_class      TEXT DEFAULT 'ordinary',
    shares_held      NUMERIC(20,0) DEFAULT 0,
    par_value        NUMERIC(20,6) DEFAULT 1,
    total_paid       NUMERIC(20,6) DEFAULT 0,
    ownership_pct    NUMERIC(8,4),
    effective_date   DATE NOT NULL,
    is_active        BOOLEAN DEFAULT true,
    notes            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ─── TAX ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fin_tax_codes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id    UUID REFERENCES fin_entities(id),
    code         TEXT NOT NULL,
    name         TEXT NOT NULL,
    tax_type     TEXT NOT NULL,
    rate         NUMERIC(8,4) NOT NULL,
    country_code VARCHAR(5),
    applies_to   TEXT DEFAULT 'both',
    gl_account_id UUID REFERENCES fin_accounts(id),
    is_active    BOOLEAN DEFAULT true,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, code)
);

CREATE TABLE IF NOT EXISTS fin_tax_returns (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id      UUID REFERENCES fin_entities(id),
    period_id      UUID REFERENCES fin_periods(id),
    tax_type       TEXT NOT NULL,
    filing_period  TEXT NOT NULL,
    due_date       DATE,
    filed_date     DATE,
    total_tax_due  NUMERIC(20,6) DEFAULT 0,
    total_tax_paid NUMERIC(20,6) DEFAULT 0,
    status         TEXT DEFAULT 'pending',
    submission_ref TEXT,
    notes          TEXT,
    generated_by   UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ─── INDEXES ─────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_fin_je_entity_date ON fin_journal_entries(entity_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_fin_je_period      ON fin_journal_entries(period_id);
CREATE INDEX IF NOT EXISTS idx_fin_jl_account     ON fin_journal_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_fin_invoices_customer ON fin_invoices(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_fin_invoices_due   ON fin_invoices(due_date, status);
CREATE INDEX IF NOT EXISTS idx_fin_bills_vendor   ON fin_bills(vendor_id, status);
CREATE INDEX IF NOT EXISTS idx_fin_payments_date  ON fin_payments(payment_date, entity_id);
CREATE INDEX IF NOT EXISTS idx_fin_expenses_date  ON fin_expenses(expense_date, entity_id);

-- ─── DOUBLE-ENTRY BALANCE TRIGGER ────────────────────────────────────────────

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

DROP TRIGGER IF EXISTS enforce_journal_balance ON fin_journal_entries;
CREATE TRIGGER enforce_journal_balance
    BEFORE UPDATE ON fin_journal_entries
    FOR EACH ROW EXECUTE FUNCTION check_journal_balance();
"""


def migrate():
    print("Finance Module Migration — creating 19 fin_* tables...")
    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        cur.execute(FINANCE_SQL)
        print("✅ All fin_* tables, indexes, and balance trigger created successfully.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

    # Verify
    print("\nVerifying tables...")
    conn2 = get_connection()
    cur2 = conn2.cursor()
    cur2.execute("SELECT tablename FROM pg_tables WHERE tablename LIKE 'fin_%' ORDER BY tablename")
    tables = [r[0] for r in cur2.fetchall()]
    conn2.close()

    print(f"Found {len(tables)} fin_* tables:")
    for t in tables:
        print(f"  ✅ {t}")

    if len(tables) < 19:
        print(f"\n⚠️  Expected 19 tables, found {len(tables)}. Check for errors above.")
    else:
        print(f"\n✅ All 19 Finance tables ready.")


if __name__ == "__main__":
    migrate()
