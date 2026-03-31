"""
Finance Module — FastAPI Router.

Prefix:  /api/finance  (registered in main.py)
Auth:    JWT required on all endpoints via get_current_user / require_permission
RBAC:    finance_read / finance_write / finance_admin

Route groups:
  /entities          — Legal entities (subsidiaries, holdings, branches)
  /currencies        — Currency master + FX rates
  /accounts          — Chart of accounts + categories
  /periods           — Accounting periods + close
  /journal           — Journal entries + post/reverse
  /customers         — Customer master
  /vendors           — Vendor master
  /invoices          — Sales invoices + send/void
  /quotes            — Sales quotes
  /bills             — Vendor bills
  /payments          — Receipts & payments
  /bank-accounts     — Bank account master
  /expenses          — Expense claims + approve/reject
  /shareholders      — Shareholder register
  /tax-codes         — Tax code master
  /tax-returns       — Tax return filings
  /reports/*         — P&L, balance sheet, trial balance, AR/AP aging, cash flow, tax summary, analysis
  /dashboard         — Finance KPI dashboard
"""

import json
import logging
from datetime import date as date_type
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission

from .schemas import (
    AccountCategoryCreate,
    AccountCreate,
    BankAccountCreate,
    BillCreate,
    CurrencyCreate,
    CustomerCreate,
    EntityCreate,
    ExpenseCreate,
    ExchangeRateCreate,
    InvoiceCreate,
    JournalEntryCreate,
    PaymentCreate,
    PeriodCreate,
    QuoteCreate,
    ReportRequest,
    ShareholderCreate,
    TaxCodeCreate,
    TaxReturnCreate,
    VendorCreate,
)
from .service import FinanceService

logger = logging.getLogger("mezzofy.finance")

finance_router = APIRouter(tags=["Finance"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(data, meta: Optional[dict] = None) -> dict:
    """Standard success envelope."""
    return {"success": True, "data": data, "meta": meta}


# ── Entities ──────────────────────────────────────────────────────────────────

@finance_router.get("/entities")
async def list_entities(
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all active legal entities."""
    result = await db.execute(
        text("SELECT * FROM fin_entities WHERE is_active = true ORDER BY name")
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/entities", status_code=201)
async def create_entity(
    body: EntityCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new legal entity."""
    entity_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_entities
                (id, code, name, entity_type, country_code, base_currency,
                 parent_entity_id, tax_id, business_id, registered_address, fiscal_year_start)
            VALUES
                (:id, :code, :name, :type, :country, :currency,
                 :parent, :tax_id, :business_id, :address, :fy_start)
        """),
        {
            "id": str(entity_id),
            "code": body.code,
            "name": body.name,
            "type": body.entity_type,
            "country": body.country_code,
            "currency": body.base_currency,
            "parent": str(body.parent_entity_id) if body.parent_entity_id else None,
            "tax_id": body.tax_id,
            "business_id": body.business_id,
            "address": body.registered_address,
            "fy_start": body.fiscal_year_start,
        },
    )
    await db.commit()
    logger.info("Entity created: %s by user %s", entity_id, current_user.get("user_id"))
    return _ok({"id": str(entity_id), **body.model_dump()})


@finance_router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: UUID,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single legal entity by ID."""
    result = await db.execute(
        text("SELECT * FROM fin_entities WHERE id = :id"),
        {"id": str(entity_id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Entity not found")
    return _ok(dict(row._mapping))


# ── Currencies & FX Rates ─────────────────────────────────────────────────────

@finance_router.get("/currencies")
async def list_currencies(
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all active currencies."""
    result = await db.execute(
        text("SELECT * FROM fin_currencies WHERE is_active = true ORDER BY code")
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/currencies", status_code=201)
async def create_currency(
    body: CurrencyCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Add a currency. No-op if code already exists (ON CONFLICT DO NOTHING)."""
    await db.execute(
        text("""
            INSERT INTO fin_currencies (id, code, name, symbol, is_base, decimal_places)
            VALUES (:id, :code, :name, :symbol, :is_base, :dp)
            ON CONFLICT (code) DO NOTHING
        """),
        {
            "id": str(uuid4()),
            "code": body.code,
            "name": body.name,
            "symbol": body.symbol,
            "is_base": body.is_base,
            "dp": body.decimal_places,
        },
    )
    await db.commit()
    return _ok(body.model_dump())


@finance_router.post("/currencies/fx-rates", status_code=201)
async def create_fx_rate(
    body: ExchangeRateCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Upsert an exchange rate for a given date."""
    await db.execute(
        text("""
            INSERT INTO fin_exchange_rates
                (id, from_currency, to_currency, rate, effective_date, source)
            VALUES (:id, :from_c, :to_c, :rate, :date, :source)
            ON CONFLICT (from_currency, to_currency, effective_date)
            DO UPDATE SET rate = EXCLUDED.rate
        """),
        {
            "id": str(uuid4()),
            "from_c": body.from_currency,
            "to_c": body.to_currency,
            "rate": str(body.rate),
            "date": body.effective_date,
            "source": body.source,
        },
    )
    await db.commit()
    return _ok(body.model_dump())


# ── Chart of Accounts ─────────────────────────────────────────────────────────

@finance_router.get("/account-categories")
async def list_account_categories(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all account categories for an entity."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_account_categories WHERE entity_id = :eid ORDER BY display_order, code"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/account-categories", status_code=201)
async def create_account_category(
    body: AccountCategoryCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new account category."""
    cat_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_account_categories
                (id, entity_id, code, name, account_type, normal_balance,
                 display_order, parent_id)
            VALUES
                (:id, :eid, :code, :name, :type, :normal, :order, :parent)
        """),
        {
            "id": str(cat_id),
            "eid": str(body.entity_id),
            "code": body.code,
            "name": body.name,
            "type": body.account_type,
            "normal": body.normal_balance,
            "order": body.display_order,
            "parent": str(body.parent_id) if body.parent_id else None,
        },
    )
    await db.commit()
    return _ok({"id": str(cat_id), **body.model_dump()})


@finance_router.get("/accounts")
async def list_accounts(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all active GL accounts for an entity, joined with category info."""
    result = await db.execute(
        text("""
            SELECT a.*, ac.name AS category_name, ac.account_type
            FROM fin_accounts a
            JOIN fin_account_categories ac ON a.category_id = ac.id
            WHERE a.entity_id = :eid AND a.is_active = true
            ORDER BY a.code
        """),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/accounts", status_code=201)
async def create_account(
    body: AccountCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a GL account."""
    acct_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_accounts
                (id, entity_id, category_id, code, name, description,
                 currency, is_bank_account, is_control, allow_direct_posting)
            VALUES
                (:id, :eid, :cat, :code, :name, :desc,
                 :curr, :bank, :ctrl, :direct)
        """),
        {
            "id": str(acct_id),
            "eid": str(body.entity_id),
            "cat": str(body.category_id),
            "code": body.code,
            "name": body.name,
            "desc": body.description,
            "curr": body.currency,
            "bank": body.is_bank_account,
            "ctrl": body.is_control,
            "direct": body.allow_direct_posting,
        },
    )
    await db.commit()
    return _ok({"id": str(acct_id), **body.model_dump()})


# ── Periods ───────────────────────────────────────────────────────────────────

@finance_router.get("/periods")
async def list_periods(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List accounting periods for an entity, newest first."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_periods WHERE entity_id = :eid ORDER BY start_date DESC"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/periods", status_code=201)
async def create_period(
    body: PeriodCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create an accounting period."""
    period_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_periods
                (id, entity_id, name, period_type, start_date, end_date)
            VALUES
                (:id, :eid, :name, :type, :start, :end)
        """),
        {
            "id": str(period_id),
            "eid": str(body.entity_id),
            "name": body.name,
            "type": body.period_type,
            "start": body.start_date,
            "end": body.end_date,
        },
    )
    await db.commit()
    return _ok({"id": str(period_id), **body.model_dump()})


@finance_router.post("/periods/{period_id}/close")
async def close_period(
    period_id: UUID,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Close an accounting period after validating all entries are posted."""
    user_id = UUID(str(current_user.get("user_id", str(uuid4()))))
    svc = FinanceService(db)
    result = await svc.close_period(period_id, user_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Cannot close period"))
    return _ok(result)


# ── Journal Entries ───────────────────────────────────────────────────────────

@finance_router.get("/journal")
async def list_journal_entries(
    entity_id: UUID = Query(...),
    status: Optional[str] = None,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List journal entries for an entity. Optionally filter by status."""
    sql = "SELECT * FROM fin_journal_entries WHERE entity_id = :eid"
    params: dict = {"eid": str(entity_id)}
    if status:
        sql += " AND status = :status"
        params["status"] = status
    sql += " ORDER BY entry_date DESC, created_at DESC LIMIT 200"
    result = await db.execute(text(sql), params)
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/journal", status_code=201)
async def create_journal_entry(
    body: JournalEntryCreate,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft journal entry with balanced debit/credit lines."""
    svc = FinanceService(db)
    entry_number = await svc.next_number(
        body.entity_id, "MZ-JE", "fin_journal_entries", "entry_number"
    )
    entry_id = uuid4()
    period_id = body.period_id or await svc.get_or_create_period(
        body.entity_id, body.entry_date
    )
    # Serialise tags list to JSON string for PostgreSQL jsonb column
    tags_json = json.dumps(body.tags)
    await db.execute(
        text("""
            INSERT INTO fin_journal_entries
                (id, entity_id, period_id, entry_number, entry_date,
                 description, reference, currency, exchange_rate, tags, created_by)
            VALUES
                (:id, :eid, :pid, :num, :date,
                 :desc, :ref, :curr, :rate, :tags::jsonb, :uid)
        """),
        {
            "id": str(entry_id),
            "eid": str(body.entity_id),
            "pid": str(period_id),
            "num": entry_number,
            "date": body.entry_date,
            "desc": body.description,
            "ref": body.reference,
            "curr": body.currency,
            "rate": str(body.exchange_rate),
            "tags": tags_json,
            "uid": str(current_user.get("user_id", "")),
        },
    )
    for i, line in enumerate(body.lines):
        await db.execute(
            text("""
                INSERT INTO fin_journal_lines
                    (id, journal_entry_id, account_id, description,
                     debit_amount, credit_amount, currency, tax_code, line_order)
                VALUES
                    (:id, :je, :acct, :desc, :dr, :cr, :curr, :tax, :order)
            """),
            {
                "id": str(uuid4()),
                "je": str(entry_id),
                "acct": str(line.account_id),
                "desc": line.description,
                "dr": str(line.debit_amount),
                "cr": str(line.credit_amount),
                "curr": line.currency or body.currency,
                "tax": line.tax_code,
                "order": i,
            },
        )
    await db.commit()
    logger.info(
        "Journal entry %s created by user %s", entry_number, current_user.get("user_id")
    )
    return _ok({"id": str(entry_id), "entry_number": entry_number})


@finance_router.post("/journal/{entry_id}/post")
async def post_journal_entry(
    entry_id: UUID,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Mark a draft journal entry as posted."""
    await db.execute(
        text("""
            UPDATE fin_journal_entries
            SET status = 'posted',
                posted_by = :uid,
                posted_at = NOW()
            WHERE id = :id AND status = 'draft'
        """),
        {"id": str(entry_id), "uid": str(current_user.get("user_id", ""))},
    )
    await db.commit()
    return _ok({"id": str(entry_id), "status": "posted"})


@finance_router.post("/journal/{entry_id}/reverse")
async def reverse_journal_entry(
    entry_id: UUID,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a reversal entry that swaps debits and credits of the original."""
    svc = FinanceService(db)
    result = await db.execute(
        text("SELECT * FROM fin_journal_entries WHERE id = :id"),
        {"id": str(entry_id)},
    )
    original = result.fetchone()
    if not original:
        raise HTTPException(404, "Journal entry not found")

    lines_result = await db.execute(
        text("SELECT * FROM fin_journal_lines WHERE journal_entry_id = :id"),
        {"id": str(entry_id)},
    )
    lines = lines_result.fetchall()

    rev_number = await svc.next_number(
        UUID(str(original.entity_id)), "MZ-JE", "fin_journal_entries", "entry_number"
    )
    rev_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_journal_entries
                (id, entity_id, period_id, entry_number, entry_date,
                 description, source, currency, status, reversed_by, created_by)
            VALUES
                (:id, :eid, :pid, :num, NOW()::date,
                 :desc, 'reversal', :curr, 'posted', :orig, :uid)
        """),
        {
            "id": str(rev_id),
            "eid": str(original.entity_id),
            "pid": str(original.period_id),
            "num": rev_number,
            "desc": f"Reversal of {original.entry_number}",
            "curr": original.currency,
            "orig": str(entry_id),
            "uid": str(current_user.get("user_id", "")),
        },
    )
    for line in lines:
        await db.execute(
            text("""
                INSERT INTO fin_journal_lines
                    (id, journal_entry_id, account_id,
                     debit_amount, credit_amount, description)
                VALUES
                    (:id, :je, :acct, :dr, :cr, :desc)
            """),
            {
                "id": str(uuid4()),
                "je": str(rev_id),
                "acct": str(line.account_id),
                # Swap debit ↔ credit
                "dr": str(line.credit_amount),
                "cr": str(line.debit_amount),
                "desc": f"Reversal: {line.description or ''}",
            },
        )
    await db.execute(
        text(
            "UPDATE fin_journal_entries SET status = 'reversed' WHERE id = :id"
        ),
        {"id": str(entry_id)},
    )
    await db.commit()
    logger.info(
        "Journal entry %s reversed → %s by user %s",
        entry_id,
        rev_number,
        current_user.get("user_id"),
    )
    return _ok({"reversal_entry_number": rev_number, "reversal_id": str(rev_id)})


# ── Customers ─────────────────────────────────────────────────────────────────

@finance_router.get("/customers")
async def list_customers(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List active customers for an entity."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_customers "
            "WHERE entity_id = :eid AND is_active = true ORDER BY name"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/customers", status_code=201)
async def create_customer(
    body: CustomerCreate,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a customer. Auto-generates customer_code."""
    svc = FinanceService(db)
    cust_code = await svc.next_number(
        body.entity_id, "MZ-CUST", "fin_customers", "customer_code"
    )
    cust_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_customers
                (id, entity_id, lead_id, customer_code, name, company_name,
                 email, phone, billing_address, shipping_address,
                 currency, payment_terms, credit_limit, tax_id, notes)
            VALUES
                (:id, :eid, :lid, :code, :name, :company,
                 :email, :phone, :billing::jsonb, :shipping::jsonb,
                 :curr, :terms, :limit, :tax, :notes)
        """),
        {
            "id": str(cust_id),
            "eid": str(body.entity_id),
            "lid": str(body.lead_id) if body.lead_id else None,
            "code": cust_code,
            "name": body.name,
            "company": body.company_name,
            "email": body.email,
            "phone": body.phone,
            "billing": json.dumps(body.billing_address) if body.billing_address else None,
            "shipping": json.dumps(body.shipping_address) if body.shipping_address else None,
            "curr": body.currency,
            "terms": body.payment_terms,
            "limit": str(body.credit_limit) if body.credit_limit else None,
            "tax": body.tax_id,
            "notes": body.notes,
        },
    )
    await db.commit()
    return _ok({"id": str(cust_id), "customer_code": cust_code, **body.model_dump()})


@finance_router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: UUID,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single customer."""
    result = await db.execute(
        text("SELECT * FROM fin_customers WHERE id = :id"),
        {"id": str(customer_id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Customer not found")
    return _ok(dict(row._mapping))


# ── Vendors ───────────────────────────────────────────────────────────────────

@finance_router.get("/vendors")
async def list_vendors(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List active vendors for an entity."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_vendors "
            "WHERE entity_id = :eid AND is_active = true ORDER BY name"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/vendors", status_code=201)
async def create_vendor(
    body: VendorCreate,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a vendor. Auto-generates vendor_code."""
    svc = FinanceService(db)
    vendor_code = await svc.next_number(
        body.entity_id, "MZ-VEND", "fin_vendors", "vendor_code"
    )
    vendor_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_vendors
                (id, entity_id, vendor_code, name, company_name,
                 email, phone, billing_address, currency,
                 payment_terms, bank_details, tax_id)
            VALUES
                (:id, :eid, :code, :name, :company,
                 :email, :phone, :billing::jsonb, :curr,
                 :terms, :bank::jsonb, :tax)
        """),
        {
            "id": str(vendor_id),
            "eid": str(body.entity_id),
            "code": vendor_code,
            "name": body.name,
            "company": body.company_name,
            "email": body.email,
            "phone": body.phone,
            "billing": json.dumps(body.billing_address) if body.billing_address else None,
            "curr": body.currency,
            "terms": body.payment_terms,
            "bank": json.dumps(body.bank_details) if body.bank_details else None,
            "tax": body.tax_id,
        },
    )
    await db.commit()
    return _ok({"id": str(vendor_id), "vendor_code": vendor_code, **body.model_dump()})


@finance_router.get("/vendors/{vendor_id}")
async def get_vendor(
    vendor_id: UUID,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single vendor."""
    result = await db.execute(
        text("SELECT * FROM fin_vendors WHERE id = :id"),
        {"id": str(vendor_id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Vendor not found")
    return _ok(dict(row._mapping))


# ── Quotes ────────────────────────────────────────────────────────────────────

@finance_router.get("/quotes")
async def list_quotes(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List quotes for an entity, joined with customer name."""
    result = await db.execute(
        text("""
            SELECT q.*, c.name AS customer_name
            FROM fin_quotes q
            JOIN fin_customers c ON q.customer_id = c.id
            WHERE q.entity_id = :eid
            ORDER BY q.quote_date DESC
        """),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/quotes", status_code=201)
async def create_quote(
    body: QuoteCreate,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft quote. Auto-generates quote_number and computes totals."""
    svc = FinanceService(db)
    quote_number = await svc.next_number(
        body.entity_id, "MZ-QUO", "fin_quotes", "quote_number"
    )
    quote_id = uuid4()
    totals = svc._compute_totals([item.model_dump() for item in body.line_items])
    await db.execute(
        text("""
            INSERT INTO fin_quotes
                (id, entity_id, quote_number, customer_id, lead_id,
                 quote_date, expiry_date, currency, exchange_rate,
                 subtotal, tax_amount, total_amount, status,
                 line_items, terms, notes)
            VALUES
                (:id, :eid, :num, :cust, :lead,
                 :date, :expiry, :curr, :rate,
                 :sub, :tax, :total, 'draft',
                 :items::jsonb, :terms, :notes)
        """),
        {
            "id": str(quote_id),
            "eid": str(body.entity_id),
            "num": quote_number,
            "cust": str(body.customer_id),
            "lead": str(body.lead_id) if body.lead_id else None,
            "date": body.quote_date,
            "expiry": body.expiry_date,
            "curr": body.currency,
            "rate": str(body.exchange_rate),
            "sub": str(totals["subtotal"]),
            "tax": str(totals["tax_amount"]),
            "total": str(totals["total_amount"]),
            "items": json.dumps([i.model_dump(mode="json") for i in body.line_items]),
            "terms": body.terms,
            "notes": body.notes,
        },
    )
    await db.commit()
    return _ok({"id": str(quote_id), "quote_number": quote_number, **totals})


# ── Invoices ──────────────────────────────────────────────────────────────────

@finance_router.get("/invoices")
async def list_invoices(
    entity_id: UUID = Query(...),
    status: Optional[str] = None,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List invoices for an entity with optional status filter."""
    sql = (
        "SELECT i.*, c.name AS customer_name "
        "FROM fin_invoices i "
        "JOIN fin_customers c ON i.customer_id = c.id "
        "WHERE i.entity_id = :eid"
    )
    params: dict = {"eid": str(entity_id)}
    if status:
        sql += " AND i.status = :status"
        params["status"] = status
    sql += " ORDER BY i.invoice_date DESC LIMIT 200"
    result = await db.execute(text(sql), params)
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/invoices", status_code=201)
async def create_invoice(
    body: InvoiceCreate,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft invoice. Auto-generates invoice_number and computes totals."""
    svc = FinanceService(db)
    inv_number = await svc.next_number(
        body.entity_id, "MZ-INV", "fin_invoices", "invoice_number"
    )
    inv_id = uuid4()
    totals = svc._compute_totals([item.model_dump() for item in body.line_items])
    await db.execute(
        text("""
            INSERT INTO fin_invoices
                (id, entity_id, invoice_number, customer_id, quote_id,
                 invoice_date, due_date, currency, exchange_rate,
                 subtotal, tax_amount, total_amount, status,
                 line_items, payment_terms, notes, created_by)
            VALUES
                (:id, :eid, :num, :cust, :quote,
                 :date, :due, :curr, :rate,
                 :sub, :tax, :total, 'draft',
                 :items::jsonb, :terms, :notes, :uid)
        """),
        {
            "id": str(inv_id),
            "eid": str(body.entity_id),
            "num": inv_number,
            "cust": str(body.customer_id),
            "quote": str(body.quote_id) if body.quote_id else None,
            "date": body.invoice_date,
            "due": body.due_date,
            "curr": body.currency,
            "rate": str(body.exchange_rate),
            "sub": str(totals["subtotal"]),
            "tax": str(totals["tax_amount"]),
            "total": str(totals["total_amount"]),
            "items": json.dumps([i.model_dump(mode="json") for i in body.line_items]),
            "terms": body.payment_terms,
            "notes": body.notes,
            "uid": str(current_user.get("user_id", "")),
        },
    )
    await db.commit()
    return _ok({"id": str(inv_id), "invoice_number": inv_number, **totals})


@finance_router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: UUID,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single invoice."""
    result = await db.execute(
        text("SELECT * FROM fin_invoices WHERE id = :id"),
        {"id": str(invoice_id)},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Invoice not found")
    return _ok(dict(row._mapping))


@finance_router.post("/invoices/{invoice_id}/send")
async def send_invoice(
    invoice_id: UUID,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Mark a draft invoice as sent."""
    await db.execute(
        text("""
            UPDATE fin_invoices
            SET status = 'sent', sent_at = NOW()
            WHERE id = :id AND status = 'draft'
        """),
        {"id": str(invoice_id)},
    )
    await db.commit()
    return _ok({"id": str(invoice_id), "status": "sent"})


@finance_router.post("/invoices/{invoice_id}/void")
async def void_invoice(
    invoice_id: UUID,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Void an invoice."""
    await db.execute(
        text("UPDATE fin_invoices SET status = 'void' WHERE id = :id"),
        {"id": str(invoice_id)},
    )
    await db.commit()
    return _ok({"id": str(invoice_id), "status": "void"})


# ── Bills ─────────────────────────────────────────────────────────────────────

@finance_router.get("/bills")
async def list_bills(
    entity_id: UUID = Query(...),
    status: Optional[str] = None,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List vendor bills, optionally filtered by status, ordered by due date."""
    sql = (
        "SELECT b.*, v.name AS vendor_name "
        "FROM fin_bills b "
        "JOIN fin_vendors v ON b.vendor_id = v.id "
        "WHERE b.entity_id = :eid"
    )
    params: dict = {"eid": str(entity_id)}
    if status:
        sql += " AND b.status = :status"
        params["status"] = status
    sql += " ORDER BY b.due_date ASC LIMIT 200"
    result = await db.execute(text(sql), params)
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/bills", status_code=201)
async def create_bill(
    body: BillCreate,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a vendor bill. Auto-generates bill_number and computes totals."""
    svc = FinanceService(db)
    bill_number = await svc.next_number(
        body.entity_id, "MZ-BILL", "fin_bills", "bill_number"
    )
    bill_id = uuid4()
    totals = svc._compute_totals([item.model_dump() for item in body.line_items])
    await db.execute(
        text("""
            INSERT INTO fin_bills
                (id, entity_id, bill_number, vendor_id, bill_date,
                 due_date, reference, currency, exchange_rate,
                 subtotal, tax_amount, total_amount, status,
                 line_items, notes)
            VALUES
                (:id, :eid, :num, :vend, :date,
                 :due, :ref, :curr, :rate,
                 :sub, :tax, :total, 'pending',
                 :items::jsonb, :notes)
        """),
        {
            "id": str(bill_id),
            "eid": str(body.entity_id),
            "num": bill_number,
            "vend": str(body.vendor_id),
            "date": body.bill_date,
            "due": body.due_date,
            "ref": body.reference,
            "curr": body.currency,
            "rate": str(body.exchange_rate),
            "sub": str(totals["subtotal"]),
            "tax": str(totals["tax_amount"]),
            "total": str(totals["total_amount"]),
            "items": json.dumps([i.model_dump(mode="json") for i in body.line_items]),
            "notes": body.notes,
        },
    )
    await db.commit()
    return _ok({"id": str(bill_id), "bill_number": bill_number, **totals})


@finance_router.post("/bills/{bill_id}/approve")
async def approve_bill(
    bill_id: UUID,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending vendor bill."""
    await db.execute(
        text(
            "UPDATE fin_bills SET status = 'approved' "
            "WHERE id = :id AND status = 'pending'"
        ),
        {"id": str(bill_id)},
    )
    await db.commit()
    return _ok({"id": str(bill_id), "status": "approved"})


# ── Payments ──────────────────────────────────────────────────────────────────

@finance_router.get("/payments")
async def list_payments(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List payments for an entity, newest first."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_payments "
            "WHERE entity_id = :eid ORDER BY payment_date DESC LIMIT 200"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/payments", status_code=201)
async def create_payment(
    body: PaymentCreate,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Record a receipt or payment. Auto-generates payment_number.
    Updates invoice/bill paid_amount and status automatically.
    """
    svc = FinanceService(db)
    payment_number = await svc.next_number(
        body.entity_id, "MZ-PMT", "fin_payments", "payment_number"
    )
    payment_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_payments
                (id, entity_id, payment_number, payment_type, payment_date,
                 bank_account_id, customer_id, vendor_id, invoice_id, bill_id,
                 currency, amount, exchange_rate, payment_method, reference, notes)
            VALUES
                (:id, :eid, :num, :type, :date,
                 :bank, :cust, :vend, :inv, :bill,
                 :curr, :amt, :rate, :method, :ref, :notes)
        """),
        {
            "id": str(payment_id),
            "eid": str(body.entity_id),
            "num": payment_number,
            "type": body.payment_type,
            "date": body.payment_date,
            "bank": str(body.bank_account_id),
            "cust": str(body.customer_id) if body.customer_id else None,
            "vend": str(body.vendor_id) if body.vendor_id else None,
            "inv": str(body.invoice_id) if body.invoice_id else None,
            "bill": str(body.bill_id) if body.bill_id else None,
            "curr": body.currency,
            "amt": str(body.amount),
            "rate": str(body.exchange_rate),
            "method": body.payment_method,
            "ref": body.reference,
            "notes": body.notes,
        },
    )
    # Update invoice paid_amount + auto-set status
    if body.invoice_id:
        await db.execute(
            text("""
                UPDATE fin_invoices
                SET paid_amount = paid_amount + :amt,
                    status = CASE
                        WHEN paid_amount + :amt >= total_amount THEN 'paid'
                        WHEN paid_amount + :amt > 0              THEN 'partial'
                        ELSE status
                    END
                WHERE id = :id
            """),
            {"amt": str(body.amount), "id": str(body.invoice_id)},
        )
    # Update bill paid_amount + auto-set status
    if body.bill_id:
        await db.execute(
            text("""
                UPDATE fin_bills
                SET paid_amount = paid_amount + :amt,
                    status = CASE
                        WHEN paid_amount + :amt >= total_amount THEN 'paid'
                        WHEN paid_amount + :amt > 0              THEN 'partial'
                        ELSE status
                    END
                WHERE id = :id
            """),
            {"amt": str(body.amount), "id": str(body.bill_id)},
        )
    await db.commit()
    return _ok({"id": str(payment_id), "payment_number": payment_number})


# ── Bank Accounts ─────────────────────────────────────────────────────────────

@finance_router.get("/bank-accounts")
async def list_bank_accounts(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List active bank accounts for an entity."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_bank_accounts "
            "WHERE entity_id = :eid AND is_active = true"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/bank-accounts", status_code=201)
async def create_bank_account(
    body: BankAccountCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Register a bank account."""
    ba_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_bank_accounts
                (id, entity_id, account_id, bank_name, account_name,
                 account_number, swift_code, iban, currency)
            VALUES
                (:id, :eid, :acct, :bank, :name,
                 :num, :swift, :iban, :curr)
        """),
        {
            "id": str(ba_id),
            "eid": str(body.entity_id),
            "acct": str(body.account_id) if body.account_id else None,
            "bank": body.bank_name,
            "name": body.account_name,
            "num": body.account_number,
            "swift": body.swift_code,
            "iban": body.iban,
            "curr": body.currency,
        },
    )
    await db.commit()
    return _ok({"id": str(ba_id), **body.model_dump()})


# ── Expenses ──────────────────────────────────────────────────────────────────

@finance_router.get("/expenses")
async def list_expenses(
    entity_id: UUID = Query(...),
    status: Optional[str] = None,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List expense claims for an entity, optionally filtered by status."""
    sql = "SELECT * FROM fin_expenses WHERE entity_id = :eid"
    params: dict = {"eid": str(entity_id)}
    if status:
        sql += " AND status = :status"
        params["status"] = status
    sql += " ORDER BY expense_date DESC"
    result = await db.execute(text(sql), params)
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/expenses", status_code=201)
async def create_expense(
    body: ExpenseCreate,
    current_user: dict = Depends(require_permission("finance_write", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Submit an expense claim. Auto-generates expense_number."""
    svc = FinanceService(db)
    exp_number = await svc.next_number(
        body.entity_id, "MZ-EXP", "fin_expenses", "expense_number"
    )
    exp_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_expenses
                (id, entity_id, expense_number, expense_date, category,
                 description, vendor_name, vendor_id, account_id,
                 currency, amount, tax_amount, receipt_path, submitted_by)
            VALUES
                (:id, :eid, :num, :date, :cat,
                 :desc, :vname, :vid, :acct,
                 :curr, :amt, :tax, :receipt, :uid)
        """),
        {
            "id": str(exp_id),
            "eid": str(body.entity_id),
            "num": exp_number,
            "date": body.expense_date,
            "cat": body.category,
            "desc": body.description,
            "vname": body.vendor_name,
            "vid": str(body.vendor_id) if body.vendor_id else None,
            "acct": str(body.account_id) if body.account_id else None,
            "curr": body.currency,
            "amt": str(body.amount),
            "tax": str(body.tax_amount),
            "receipt": body.receipt_path,
            "uid": str(current_user.get("user_id", "")),
        },
    )
    await db.commit()
    return _ok({"id": str(exp_id), "expense_number": exp_number})


@finance_router.post("/expenses/{expense_id}/approve")
async def approve_expense(
    expense_id: UUID,
    action: str = Query(..., pattern="^(approve|reject)$"),
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject an expense claim."""
    new_status = "approved" if action == "approve" else "rejected"
    await db.execute(
        text("""
            UPDATE fin_expenses
            SET status = :status,
                approved_by = :uid
            WHERE id = :id
        """),
        {
            "status": new_status,
            "uid": str(current_user.get("user_id", "")),
            "id": str(expense_id),
        },
    )
    await db.commit()
    return _ok({"id": str(expense_id), "status": new_status})


# ── Shareholders ──────────────────────────────────────────────────────────────

@finance_router.get("/shareholders")
async def list_shareholders(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List active shareholders for an entity, sorted by ownership percentage."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_shareholders "
            "WHERE entity_id = :eid AND is_active = true "
            "ORDER BY ownership_pct DESC NULLS LAST"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/shareholders", status_code=201)
async def create_shareholder(
    body: ShareholderCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Add a shareholder to the register."""
    sh_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_shareholders
                (id, entity_id, name, shareholder_type, id_number,
                 nationality, address, share_class, shares_held,
                 par_value, total_paid, ownership_pct, effective_date, notes)
            VALUES
                (:id, :eid, :name, :type, :id_num,
                 :nat, :addr::jsonb, :class, :shares,
                 :par, :paid, :pct, :date, :notes)
        """),
        {
            "id": str(sh_id),
            "eid": str(body.entity_id),
            "name": body.name,
            "type": body.shareholder_type,
            "id_num": body.id_number,
            "nat": body.nationality,
            "addr": json.dumps(body.address) if body.address else None,
            "class": body.share_class,
            "shares": str(body.shares_held),
            "par": str(body.par_value),
            "paid": str(body.total_paid),
            "pct": str(body.ownership_pct) if body.ownership_pct else None,
            "date": body.effective_date,
            "notes": body.notes,
        },
    )
    await db.commit()
    return _ok({"id": str(sh_id), **body.model_dump()})


# ── Tax Codes ─────────────────────────────────────────────────────────────────

@finance_router.get("/tax-codes")
async def list_tax_codes(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List active tax codes for an entity."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_tax_codes "
            "WHERE entity_id = :eid AND is_active = true"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/tax-codes", status_code=201)
async def create_tax_code(
    body: TaxCodeCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a tax code (GST/VAT/withholding/corporate)."""
    tc_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_tax_codes
                (id, entity_id, code, name, tax_type,
                 rate, country_code, applies_to, gl_account_id)
            VALUES
                (:id, :eid, :code, :name, :type,
                 :rate, :country, :applies, :gl)
        """),
        {
            "id": str(tc_id),
            "eid": str(body.entity_id),
            "code": body.code,
            "name": body.name,
            "type": body.tax_type,
            "rate": str(body.rate),
            "country": body.country_code,
            "applies": body.applies_to,
            "gl": str(body.gl_account_id) if body.gl_account_id else None,
        },
    )
    await db.commit()
    return _ok({"id": str(tc_id), **body.model_dump()})


# ── Tax Returns ───────────────────────────────────────────────────────────────

@finance_router.get("/tax-returns")
async def list_tax_returns(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List tax return filings for an entity."""
    result = await db.execute(
        text(
            "SELECT * FROM fin_tax_returns "
            "WHERE entity_id = :eid ORDER BY created_at DESC"
        ),
        {"eid": str(entity_id)},
    )
    return _ok([dict(r._mapping) for r in result.fetchall()])


@finance_router.post("/tax-returns", status_code=201)
async def create_tax_return(
    body: TaxReturnCreate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a tax return record."""
    tr_id = uuid4()
    await db.execute(
        text("""
            INSERT INTO fin_tax_returns
                (id, entity_id, period_id, tax_type, filing_period, due_date)
            VALUES
                (:id, :eid, :pid, :type, :period, :due)
        """),
        {
            "id": str(tr_id),
            "eid": str(body.entity_id),
            "pid": str(body.period_id),
            "type": body.tax_type,
            "period": body.filing_period,
            "due": body.due_date,
        },
    )
    await db.commit()
    return _ok({"id": str(tr_id), **body.model_dump()})


# ── Reports ───────────────────────────────────────────────────────────────────

@finance_router.post("/reports/pnl")
async def report_pnl(
    body: ReportRequest,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Profit & Loss report for a date range."""
    svc = FinanceService(db)
    start = body.start_date or date_type(date_type.today().year, 1, 1)
    end = body.end_date or date_type.today()
    data = await svc.get_pnl(body.entity_id, start, end, body.currency, body.compare_previous)
    return _ok(data)


@finance_router.post("/reports/balance-sheet")
async def report_balance_sheet(
    body: ReportRequest,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Balance sheet (Assets = Liabilities + Equity) as at end_date."""
    svc = FinanceService(db)
    as_at = body.end_date or date_type.today()
    data = await svc.get_balance_sheet(body.entity_id, as_at, body.currency)
    return _ok(data)


@finance_router.post("/reports/trial-balance")
async def report_trial_balance(
    body: ReportRequest,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Trial balance as at end_date."""
    svc = FinanceService(db)
    as_at = body.end_date or date_type.today()
    data = await svc.get_trial_balance(body.entity_id, as_at, body.currency)
    return _ok(data)


@finance_router.post("/reports/ar-aging")
async def report_ar_aging(
    body: ReportRequest,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Accounts receivable aging report."""
    svc = FinanceService(db)
    as_at = body.end_date or date_type.today()
    data = await svc.get_ar_aging(body.entity_id, as_at, body.currency)
    return _ok(data)


@finance_router.post("/reports/ap-aging")
async def report_ap_aging(
    body: ReportRequest,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Accounts payable aging report."""
    svc = FinanceService(db)
    as_at = body.end_date or date_type.today()
    data = await svc.get_ap_aging(body.entity_id, as_at, body.currency)
    return _ok(data)


@finance_router.post("/reports/tax-summary")
async def report_tax_summary(
    body: ReportRequest,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """GST/VAT output vs input tax summary."""
    svc = FinanceService(db)
    data = await svc.get_tax_summary(body.entity_id, body.period_id)
    return _ok(data)


@finance_router.post("/reports/analysis")
async def report_analysis(
    body: ReportRequest,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Finance KPI analysis (AR, AP, cash balance)."""
    svc = FinanceService(db)
    data = await svc.get_finance_kpis(body.entity_id)
    return _ok(data)


@finance_router.post("/reports/cash-flow")
async def report_cash_flow(
    body: ReportRequest,
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Simplified cash flow: sum of fin_payments receipts vs payments."""
    start = body.start_date or date_type(date_type.today().year, 1, 1)
    end = body.end_date or date_type.today()
    result = await db.execute(
        text("""
            SELECT payment_type, SUM(amount) AS total
            FROM fin_payments
            WHERE entity_id = :eid
              AND payment_date BETWEEN :start AND :end
            GROUP BY payment_type
        """),
        {"eid": str(body.entity_id), "start": start, "end": end},
    )
    rows = {r[0]: float(r[1]) for r in result.fetchall()}
    data = {
        "receipts": rows.get("receipt", 0),
        "payments": rows.get("payment", 0),
        "net": rows.get("receipt", 0) - rows.get("payment", 0),
        "period": {"start": str(start), "end": str(end)},
    }
    return _ok(data)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@finance_router.get("/dashboard")
async def finance_dashboard(
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_read", "finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Finance dashboard: KPIs, month-to-date P&L, AR aging snapshot,
    and last 10 journal entries.
    """
    svc = FinanceService(db)
    kpis = await svc.get_finance_kpis(entity_id)
    today = date_type.today()
    start_of_month = date_type(today.year, today.month, 1)
    pnl = await svc.get_pnl(entity_id, start_of_month, today, "SGD")
    ar_aging = await svc.get_ar_aging(entity_id, today, "SGD")
    recent_je = await db.execute(
        text("""
            SELECT entry_number, entry_date, description, status
            FROM fin_journal_entries
            WHERE entity_id = :eid
            ORDER BY created_at DESC
            LIMIT 10
        """),
        {"eid": str(entity_id)},
    )
    return _ok(
        {
            "kpis": kpis,
            "pnl_mtd": pnl,
            "ar_aging": ar_aging,
            "recent_journal_entries": [
                dict(r._mapping) for r in recent_je.fetchall()
            ],
        }
    )
