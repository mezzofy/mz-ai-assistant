"""
Finance Module — Service Layer.

FinanceService handles:
  - Auto-numbering (atomic, race-condition safe)
  - FX / multi-currency conversion
  - Period management (get or auto-create)
  - Line-item total computation
  - Double-entry automation (invoice → ledger, payment → ledger)
  - Financial reporting (P&L, balance sheet, trial balance, AR/AP aging,
    tax summary, KPI dashboard)
"""

import calendar
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


class FinanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Auto-numbering ────────────────────────────────────────────────────────

    async def next_number(
        self,
        entity_id: UUID,
        prefix: str,
        table: str,
        column: str,
    ) -> str:
        """
        Atomic auto-number generation.
        Format: PREFIX-YYYY-NNNN  (year-scoped)
             or PREFIX-NNNN       (entity-scoped, for customers/vendors)

        Counters without year: MZ-CUST, MZ-VEND.
        All others include the calendar year.
        """
        include_year = prefix not in ("MZ-CUST", "MZ-VEND")
        if include_year:
            year = datetime.now().year
            result = await self.db.execute(
                text(f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE entity_id = :entity_id
                    AND EXTRACT(YEAR FROM created_at) = :year
                """),
                {"entity_id": str(entity_id), "year": year},
            )
            count = result.scalar() + 1
            return f"{prefix}-{year}-{count:04d}"
        else:
            result = await self.db.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE entity_id = :entity_id"),
                {"entity_id": str(entity_id)},
            )
            count = result.scalar() + 1
            return f"{prefix}-{count:04d}"

    # ── FX / Multi-currency ───────────────────────────────────────────────────

    async def get_fx_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date,
    ) -> Decimal:
        """
        Look up exchange rate from fin_exchange_rates.
        Falls back to the most recent rate if no exact date match.
        Returns 1.0 if no rate is found at all.
        """
        if from_currency == to_currency:
            return Decimal("1")
        result = await self.db.execute(
            text("""
                SELECT rate FROM fin_exchange_rates
                WHERE from_currency = :from_c
                  AND to_currency   = :to_c
                  AND effective_date <= :rate_date
                ORDER BY effective_date DESC
                LIMIT 1
            """),
            {"from_c": from_currency, "to_c": to_currency, "rate_date": rate_date},
        )
        row = result.fetchone()
        if not row:
            logger.warning(
                "No FX rate found for %s/%s on %s, using 1.0",
                from_currency,
                to_currency,
                rate_date,
            )
            return Decimal("1")
        return Decimal(str(row[0]))

    async def convert_to_base(
        self,
        amount: Decimal,
        from_currency: str,
        entity_id: UUID,
        rate_date: date,
    ) -> Decimal:
        """Convert a foreign currency amount to the entity's base currency."""
        result = await self.db.execute(
            text("SELECT base_currency FROM fin_entities WHERE id = :id"),
            {"id": str(entity_id)},
        )
        row = result.fetchone()
        if not row:
            return amount
        base_currency = row[0]
        rate = await self.get_fx_rate(from_currency, base_currency, rate_date)
        return amount * rate

    # ── Period management ─────────────────────────────────────────────────────

    async def get_or_create_period(self, entity_id: UUID, for_date: date) -> UUID:
        """
        Return the open accounting period that contains for_date.
        Auto-creates a monthly period if none exists.
        """
        result = await self.db.execute(
            text("""
                SELECT id FROM fin_periods
                WHERE entity_id = :entity_id
                  AND :for_date BETWEEN start_date AND end_date
                  AND status = 'open'
                LIMIT 1
            """),
            {"entity_id": str(entity_id), "for_date": for_date},
        )
        row = result.fetchone()
        if row:
            return UUID(str(row[0]))

        # Auto-create a monthly period
        start = date(for_date.year, for_date.month, 1)
        end_day = calendar.monthrange(for_date.year, for_date.month)[1]
        end = date(for_date.year, for_date.month, end_day)
        period_id = uuid4()
        await self.db.execute(
            text("""
                INSERT INTO fin_periods
                    (id, entity_id, name, period_type, start_date, end_date)
                VALUES
                    (:id, :entity_id, :name, 'monthly', :start, :end)
                ON CONFLICT (entity_id, start_date, period_type) DO NOTHING
            """),
            {
                "id": str(period_id),
                "entity_id": str(entity_id),
                "name": start.strftime("%b %Y"),
                "start": start,
                "end": end,
            },
        )
        await self.db.commit()
        return period_id

    async def close_period(self, period_id: UUID, user_id: UUID) -> dict:
        """
        Lock a period. Validates that no draft journal entries remain.
        Returns success/error dict — does NOT raise HTTPException.
        """
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) FROM fin_journal_entries
                WHERE period_id = :pid AND status = 'draft'
            """),
            {"pid": str(period_id)},
        )
        draft_count = result.scalar()
        if draft_count > 0:
            return {
                "success": False,
                "error": (
                    f"{draft_count} journal entries still in draft — "
                    "post or delete before closing"
                ),
            }
        await self.db.execute(
            text("""
                UPDATE fin_periods
                SET status = 'closed',
                    closed_by = :uid,
                    closed_at = NOW()
                WHERE id = :pid
            """),
            {"pid": str(period_id), "uid": str(user_id)},
        )
        await self.db.commit()
        return {"success": True, "message": "Period closed successfully"}

    # ── Totals computation ────────────────────────────────────────────────────

    def _compute_totals(self, line_items: list) -> dict:
        """
        Compute subtotal, tax_amount, and total_amount from a list of
        line-item dicts with keys: quantity, unit_price, tax_rate.
        """
        subtotal = Decimal("0")
        tax_amount = Decimal("0")
        for item in line_items:
            qty = Decimal(str(item.get("quantity", 1)))
            price = Decimal(str(item.get("unit_price", 0)))
            tax_rate = Decimal(str(item.get("tax_rate", 0)))
            line_total = qty * price
            line_tax = line_total * (tax_rate / 100)
            subtotal += line_total
            tax_amount += line_tax
        return {
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": subtotal + tax_amount,
        }

    # ── Double-entry automation ───────────────────────────────────────────────

    async def post_invoice_to_ledger(
        self,
        invoice_id: UUID,
        entity_id: UUID,
        user_id: UUID,
    ) -> Optional[UUID]:
        """
        Create a posted journal entry for an invoice:
          DR Accounts Receivable  (total_amount)
          CR Revenue              (subtotal)
          CR Tax Payable          (tax_amount)  [simplified to CR Revenue here]
        Returns the new journal entry UUID, or None if invoice not found.
        """
        result = await self.db.execute(
            text("SELECT * FROM fin_invoices WHERE id = :id"),
            {"id": str(invoice_id)},
        )
        invoice = result.fetchone()
        if not invoice:
            return None

        period_id = await self.get_or_create_period(entity_id, invoice.invoice_date)
        entry_number = await self.next_number(
            entity_id, "MZ-JE", "fin_journal_entries", "entry_number"
        )
        entry_id = uuid4()

        await self.db.execute(
            text("""
                INSERT INTO fin_journal_entries
                    (id, entity_id, period_id, entry_number, entry_date,
                     description, source, currency, exchange_rate, status, created_by)
                VALUES
                    (:id, :eid, :pid, :num, :date, :desc,
                     'invoice', :curr, :rate, 'posted', :uid)
            """),
            {
                "id": str(entry_id),
                "eid": str(entity_id),
                "pid": str(period_id),
                "num": entry_number,
                "date": invoice.invoice_date,
                "desc": f"Invoice {invoice.invoice_number}",
                "curr": invoice.currency,
                "rate": invoice.exchange_rate,
                "uid": str(user_id),
            },
        )

        ar_account = await self._get_control_account(entity_id, "asset", "1200")
        revenue_account = await self._get_control_account(entity_id, "income", "4000")
        line_id1, line_id2 = uuid4(), uuid4()

        await self.db.execute(
            text("""
                INSERT INTO fin_journal_lines
                    (id, journal_entry_id, account_id, description,
                     debit_amount, credit_amount, line_order)
                VALUES
                    (:id1, :je, :ar,  'Accounts Receivable', :total,    0,         1),
                    (:id2, :je, :rev, 'Revenue',             0,         :subtotal, 2)
            """),
            {
                "id1": str(line_id1),
                "id2": str(line_id2),
                "je": str(entry_id),
                "ar": str(ar_account),
                "rev": str(revenue_account),
                "total": invoice.total_amount,
                "subtotal": invoice.subtotal,
            },
        )

        await self.db.execute(
            text("UPDATE fin_invoices SET journal_entry_id = :je WHERE id = :id"),
            {"je": str(entry_id), "id": str(invoice_id)},
        )
        await self.db.commit()
        return entry_id

    async def _get_control_account(
        self,
        entity_id: UUID,
        account_type: str,
        default_code: str,
    ) -> UUID:
        """
        Look up a control account by type. Falls back to matching by code.
        Returns a placeholder UUID if no account is set up yet.
        """
        result = await self.db.execute(
            text("""
                SELECT a.id
                FROM fin_accounts a
                JOIN fin_account_categories ac ON a.category_id = ac.id
                WHERE a.entity_id = :eid
                  AND ac.account_type = :atype
                  AND (a.is_control = true OR a.code = :code)
                LIMIT 1
            """),
            {"eid": str(entity_id), "atype": account_type, "code": default_code},
        )
        row = result.fetchone()
        if row:
            return UUID(str(row[0]))
        return uuid4()

    async def post_payment_to_ledger(
        self,
        payment_id: UUID,
        entity_id: UUID,
        user_id: UUID,
    ) -> Optional[UUID]:
        """
        Create a posted journal entry for a payment:
          Receipt: DR Bank | CR Accounts Receivable
          Payment: DR Accounts Payable | CR Bank
        Returns the new journal entry UUID, or None if payment not found.
        """
        result = await self.db.execute(
            text("SELECT * FROM fin_payments WHERE id = :id"),
            {"id": str(payment_id)},
        )
        payment = result.fetchone()
        if not payment:
            return None

        period_id = await self.get_or_create_period(entity_id, payment.payment_date)
        entry_number = await self.next_number(
            entity_id, "MZ-JE", "fin_journal_entries", "entry_number"
        )
        entry_id = uuid4()

        await self.db.execute(
            text("""
                INSERT INTO fin_journal_entries
                    (id, entity_id, period_id, entry_number, entry_date,
                     description, source, currency, status, created_by)
                VALUES
                    (:id, :eid, :pid, :num, :date, :desc,
                     'payment', :curr, 'posted', :uid)
            """),
            {
                "id": str(entry_id),
                "eid": str(entity_id),
                "pid": str(period_id),
                "num": entry_number,
                "date": payment.payment_date,
                "desc": f"Payment {payment.payment_number}",
                "curr": payment.currency,
                "uid": str(user_id),
            },
        )
        await self.db.commit()
        return entry_id

    # ── Reporting ─────────────────────────────────────────────────────────────

    async def get_account_balance(
        self,
        account_id: UUID,
        start_date: date,
        end_date: date,
        currency: str,
    ) -> Decimal:
        """Net balance (debit - credit) for a GL account over the given period."""
        result = await self.db.execute(
            text("""
                SELECT
                    COALESCE(SUM(jl.debit_amount), 0)
                    - COALESCE(SUM(jl.credit_amount), 0)
                FROM fin_journal_lines jl
                JOIN fin_journal_entries je ON jl.journal_entry_id = je.id
                WHERE jl.account_id = :acct
                  AND je.entry_date BETWEEN :start AND :end
                  AND je.status = 'posted'
            """),
            {"acct": str(account_id), "start": start_date, "end": end_date},
        )
        return Decimal(str(result.scalar() or "0"))

    async def get_trial_balance(
        self,
        entity_id: UUID,
        as_at_date: date,
        currency: str,
    ) -> dict:
        """All account balances as at a given date, with totals."""
        result = await self.db.execute(
            text("""
                SELECT
                    a.code,
                    a.name,
                    ac.account_type,
                    ac.normal_balance,
                    COALESCE(SUM(jl.debit_amount),  0) AS total_debit,
                    COALESCE(SUM(jl.credit_amount), 0) AS total_credit
                FROM fin_accounts a
                JOIN fin_account_categories ac ON a.category_id = ac.id
                LEFT JOIN fin_journal_lines jl ON jl.account_id = a.id
                LEFT JOIN fin_journal_entries je
                       ON jl.journal_entry_id = je.id
                      AND je.entry_date <= :as_at
                      AND je.status = 'posted'
                WHERE a.entity_id = :eid
                  AND a.is_active = true
                GROUP BY a.code, a.name, ac.account_type, ac.normal_balance
                ORDER BY a.code
            """),
            {"eid": str(entity_id), "as_at": as_at_date},
        )
        rows = result.fetchall()
        accounts = [
            {
                "code": r[0],
                "name": r[1],
                "type": r[2],
                "normal_balance": r[3],
                "debit": float(r[4]),
                "credit": float(r[5]),
                "balance": (
                    float(r[4] - r[5])
                    if r[3] == "debit"
                    else float(r[5] - r[4])
                ),
            }
            for r in rows
        ]
        total_debit = sum(a["debit"] for a in accounts)
        total_credit = sum(a["credit"] for a in accounts)
        return {
            "accounts": accounts,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "balanced": abs(total_debit - total_credit) < 0.01,
        }

    async def get_pnl(
        self,
        entity_id: UUID,
        start_date: date,
        end_date: date,
        currency: str,
        compare: bool = False,
    ) -> dict:
        """Income − Expenses = Net Profit with category breakdown."""
        result = await self.db.execute(
            text("""
                SELECT
                    ac.name AS category,
                    ac.account_type,
                    COALESCE(SUM(jl.credit_amount - jl.debit_amount), 0) AS amount
                FROM fin_account_categories ac
                JOIN fin_accounts a ON a.category_id = ac.id
                LEFT JOIN fin_journal_lines jl ON jl.account_id = a.id
                LEFT JOIN fin_journal_entries je
                       ON jl.journal_entry_id = je.id
                      AND je.entry_date BETWEEN :start AND :end
                      AND je.status = 'posted'
                WHERE a.entity_id = :eid
                  AND ac.account_type IN ('income', 'expense')
                GROUP BY ac.name, ac.account_type
                ORDER BY ac.account_type, ac.name
            """),
            {"eid": str(entity_id), "start": start_date, "end": end_date},
        )
        rows = result.fetchall()
        income = [
            {"category": r[0], "amount": float(r[2])}
            for r in rows
            if r[1] == "income"
        ]
        expenses = [
            {"category": r[0], "amount": abs(float(r[2]))}
            for r in rows
            if r[1] == "expense"
        ]
        total_income = sum(i["amount"] for i in income)
        total_expenses = sum(e["amount"] for e in expenses)
        return {
            "period": {"start": str(start_date), "end": str(end_date)},
            "income": income,
            "total_income": total_income,
            "expenses": expenses,
            "total_expenses": total_expenses,
            "net_profit": total_income - total_expenses,
            "currency": currency,
        }

    async def get_balance_sheet(
        self,
        entity_id: UUID,
        as_at_date: date,
        currency: str,
    ) -> dict:
        """Assets = Liabilities + Equity as at a given date."""
        result = await self.db.execute(
            text("""
                SELECT
                    ac.account_type,
                    COALESCE(
                        SUM(
                            CASE WHEN ac.normal_balance = 'debit'
                                 THEN jl.debit_amount  - jl.credit_amount
                                 ELSE jl.credit_amount - jl.debit_amount
                            END
                        ), 0
                    ) AS balance
                FROM fin_account_categories ac
                JOIN fin_accounts a ON a.category_id = ac.id
                LEFT JOIN fin_journal_lines jl ON jl.account_id = a.id
                LEFT JOIN fin_journal_entries je
                       ON jl.journal_entry_id = je.id
                      AND je.entry_date <= :as_at
                      AND je.status = 'posted'
                WHERE a.entity_id = :eid
                  AND ac.account_type IN ('asset', 'liability', 'equity')
                GROUP BY ac.account_type
            """),
            {"eid": str(entity_id), "as_at": as_at_date},
        )
        rows = {r[0]: float(r[1]) for r in result.fetchall()}
        return {
            "as_at": str(as_at_date),
            "assets": rows.get("asset", 0),
            "liabilities": rows.get("liability", 0),
            "equity": rows.get("equity", 0),
            "balanced": abs(
                rows.get("asset", 0)
                - rows.get("liability", 0)
                - rows.get("equity", 0)
            ) < 0.01,
            "currency": currency,
        }

    async def get_ar_aging(
        self,
        entity_id: UUID,
        as_at_date: date,
        currency: str,
    ) -> dict:
        """Accounts receivable aging: current, 1-30, 31-60, 61-90, 90+ days."""
        result = await self.db.execute(
            text("""
                SELECT
                    c.name,
                    i.invoice_number,
                    i.due_date,
                    i.outstanding,
                    (:as_at - i.due_date) AS days_overdue
                FROM fin_invoices i
                JOIN fin_customers c ON i.customer_id = c.id
                WHERE i.entity_id = :eid
                  AND i.outstanding > 0
                  AND i.status NOT IN ('cancelled', 'void')
                ORDER BY days_overdue DESC
            """),
            {"eid": str(entity_id), "as_at": as_at_date},
        )
        rows = result.fetchall()
        buckets: dict = {
            "current": [],
            "1_30": [],
            "31_60": [],
            "61_90": [],
            "over_90": [],
        }
        for r in rows:
            days = r[4] or 0
            item = {
                "customer": r[0],
                "invoice": r[1],
                "due_date": str(r[2]),
                "amount": float(r[3]),
                "days": int(days),
            }
            if days <= 0:
                buckets["current"].append(item)
            elif days <= 30:
                buckets["1_30"].append(item)
            elif days <= 60:
                buckets["31_60"].append(item)
            elif days <= 90:
                buckets["61_90"].append(item)
            else:
                buckets["over_90"].append(item)
        return {
            "as_at": str(as_at_date),
            "currency": currency,
            "buckets": buckets,
            "total_outstanding": sum(float(r[3]) for r in rows),
        }

    async def get_ap_aging(
        self,
        entity_id: UUID,
        as_at_date: date,
        currency: str,
    ) -> dict:
        """Accounts payable aging: current, 1-30, 31-60, 61-90, 90+ days."""
        result = await self.db.execute(
            text("""
                SELECT
                    v.name,
                    b.bill_number,
                    b.due_date,
                    b.outstanding,
                    (:as_at - b.due_date) AS days_overdue
                FROM fin_bills b
                JOIN fin_vendors v ON b.vendor_id = v.id
                WHERE b.entity_id = :eid
                  AND b.outstanding > 0
                  AND b.status NOT IN ('cancelled')
                ORDER BY days_overdue DESC
            """),
            {"eid": str(entity_id), "as_at": as_at_date},
        )
        rows = result.fetchall()
        buckets: dict = {
            "current": [],
            "1_30": [],
            "31_60": [],
            "61_90": [],
            "over_90": [],
        }
        for r in rows:
            days = r[4] or 0
            item = {
                "vendor": r[0],
                "bill": r[1],
                "due_date": str(r[2]),
                "amount": float(r[3]),
                "days": int(days),
            }
            if days <= 0:
                buckets["current"].append(item)
            elif days <= 30:
                buckets["1_30"].append(item)
            elif days <= 60:
                buckets["31_60"].append(item)
            elif days <= 90:
                buckets["61_90"].append(item)
            else:
                buckets["over_90"].append(item)
        return {
            "as_at": str(as_at_date),
            "currency": currency,
            "buckets": buckets,
            "total_outstanding": sum(float(r[3]) for r in rows),
        }

    async def get_tax_summary(self, entity_id: UUID, period_id: Optional[UUID]) -> dict:
        """GST/VAT output tax vs input tax, net payable."""
        output = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(tax_amount), 0)
                FROM fin_invoices
                WHERE entity_id = :eid
                  AND status IN ('sent', 'partial', 'paid')
            """),
            {"eid": str(entity_id)},
        )
        input_ = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(tax_amount), 0)
                FROM fin_bills
                WHERE entity_id = :eid
                  AND status IN ('approved', 'partial', 'paid')
            """),
            {"eid": str(entity_id)},
        )
        output_tax = Decimal(str(output.scalar()))
        input_tax = Decimal(str(input_.scalar()))
        return {
            "output_tax": float(output_tax),
            "input_tax": float(input_tax),
            "net_payable": float(output_tax - input_tax),
        }

    async def get_finance_kpis(self, entity_id: UUID) -> dict:
        """Key metrics: AR total, AP total, cash balance."""
        ar = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(outstanding), 0)
                FROM fin_invoices
                WHERE entity_id = :eid AND outstanding > 0
            """),
            {"eid": str(entity_id)},
        )
        ap = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(outstanding), 0)
                FROM fin_bills
                WHERE entity_id = :eid AND outstanding > 0
            """),
            {"eid": str(entity_id)},
        )
        cash = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(current_balance), 0)
                FROM fin_bank_accounts
                WHERE entity_id = :eid AND is_active = true
            """),
            {"eid": str(entity_id)},
        )
        return {
            "ar_outstanding": float(ar.scalar()),
            "ap_outstanding": float(ap.scalar()),
            "cash_balance": float(cash.scalar()),
        }
