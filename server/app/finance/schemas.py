"""
Finance Module — Pydantic v2 schemas.

Covers all 19 finance tables:
  fin_currencies, fin_exchange_rates, fin_entities,
  fin_account_categories, fin_accounts, fin_periods,
  fin_journal_entries, fin_journal_lines,
  fin_customers, fin_vendors,
  fin_quotes, fin_invoices, fin_bills,
  fin_bank_accounts, fin_payments,
  fin_expenses, fin_shareholders,
  fin_tax_codes, fin_tax_returns
"""

from pydantic import BaseModel, model_validator
from typing import Optional, List, Any
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID


# ── Shared ────────────────────────────────────────────────────────────────────

class MoneyAmount(BaseModel):
    amount: Decimal
    currency: str
    base_amount: Optional[Decimal] = None
    exchange_rate: Optional[Decimal] = None


class LineItem(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Optional[Decimal] = Decimal("0")
    amount: Optional[Decimal] = None  # calculated field


# ── Currencies ────────────────────────────────────────────────────────────────

class CurrencyCreate(BaseModel):
    code: str
    name: str
    symbol: Optional[str] = None
    is_base: bool = False
    decimal_places: int = 2


class CurrencyResponse(CurrencyCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ExchangeRateCreate(BaseModel):
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_date: date
    source: str = "manual"


class ExchangeRateResponse(ExchangeRateCreate):
    id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Entities ──────────────────────────────────────────────────────────────────

class EntityCreate(BaseModel):
    code: str
    name: str
    entity_type: str  # subsidiary | holding | branch | group
    country_code: Optional[str] = None
    base_currency: str = "SGD"
    parent_entity_id: Optional[UUID] = None
    tax_id: Optional[str] = None
    business_id: Optional[str] = None
    registered_address: Optional[str] = None
    fiscal_year_start: int = 1


class EntityResponse(EntityCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Chart of Accounts ─────────────────────────────────────────────────────────

class AccountCategoryCreate(BaseModel):
    entity_id: UUID
    code: str
    name: str
    account_type: str  # asset | liability | equity | income | expense
    normal_balance: str  # debit | credit
    display_order: int = 0
    parent_id: Optional[UUID] = None


class AccountCategoryResponse(AccountCategoryCreate):
    id: UUID
    model_config = {"from_attributes": True}


class AccountCreate(BaseModel):
    entity_id: UUID
    category_id: UUID
    code: str
    name: str
    description: Optional[str] = None
    currency: str = "SGD"
    is_bank_account: bool = False
    is_control: bool = False
    allow_direct_posting: bool = True


class AccountResponse(AccountCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Periods ───────────────────────────────────────────────────────────────────

class PeriodCreate(BaseModel):
    entity_id: UUID
    name: str
    period_type: str  # monthly | quarterly | annual
    start_date: date
    end_date: date


class PeriodResponse(PeriodCreate):
    id: UUID
    status: str
    closed_by: Optional[UUID] = None
    closed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Journal Entries ───────────────────────────────────────────────────────────

class JournalLineCreate(BaseModel):
    account_id: UUID
    description: Optional[str] = None
    debit_amount: Decimal = Decimal("0")
    credit_amount: Decimal = Decimal("0")
    currency: Optional[str] = None
    tax_code: Optional[str] = None
    cost_center: Optional[str] = None
    project_ref: Optional[str] = None
    line_order: int = 0


class JournalEntryCreate(BaseModel):
    entity_id: UUID
    entry_date: date
    description: str
    reference: Optional[str] = None
    currency: str = "SGD"
    exchange_rate: Decimal = Decimal("1")
    period_id: Optional[UUID] = None
    tags: List[str] = []
    lines: List[JournalLineCreate]

    @model_validator(mode="after")
    def validate_balanced(self):
        total_debit = sum(l.debit_amount for l in self.lines)
        total_credit = sum(l.credit_amount for l in self.lines)
        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise ValueError(
                f"Journal entry not balanced: debit={total_debit}, credit={total_credit}"
            )
        if len(self.lines) < 2:
            raise ValueError("Journal entry must have at least 2 lines")
        return self


class JournalEntryResponse(BaseModel):
    id: UUID
    entity_id: UUID
    period_id: Optional[UUID]
    entry_number: str
    entry_date: date
    description: str
    reference: Optional[str]
    currency: str
    exchange_rate: Decimal
    status: str
    created_by: Optional[UUID]
    posted_by: Optional[UUID]
    posted_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Customers ─────────────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    entity_id: UUID
    name: str
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    billing_address: Optional[dict] = None
    shipping_address: Optional[dict] = None
    currency: str = "SGD"
    payment_terms: int = 30
    credit_limit: Optional[Decimal] = None
    tax_id: Optional[str] = None
    notes: Optional[str] = None
    lead_id: Optional[UUID] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    account_manager: Optional[str] = None
    customer_type: str = "buyer"  # merchant | buyer | partner
    is_active: bool = True


class CustomerResponse(CustomerCreate):
    id: UUID
    customer_code: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Vendors ───────────────────────────────────────────────────────────────────

class VendorCreate(BaseModel):
    entity_id: UUID
    name: str
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    billing_address: Optional[dict] = None
    currency: str = "SGD"
    payment_terms: int = 30
    bank_details: Optional[dict] = None
    tax_id: Optional[str] = None


class VendorResponse(VendorCreate):
    id: UUID
    vendor_code: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Quotes ────────────────────────────────────────────────────────────────────

class QuoteCreate(BaseModel):
    entity_id: UUID
    customer_id: UUID
    quote_date: date
    expiry_date: Optional[date] = None
    currency: str = "SGD"
    exchange_rate: Decimal = Decimal("1")
    line_items: List[LineItem]
    terms: Optional[str] = None
    notes: Optional[str] = None
    lead_id: Optional[UUID] = None


class QuoteResponse(BaseModel):
    id: UUID
    entity_id: UUID
    quote_number: str
    customer_id: UUID
    quote_date: date
    expiry_date: Optional[date]
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Invoices ──────────────────────────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    entity_id: UUID
    customer_id: UUID
    invoice_date: date
    due_date: date
    currency: str = "SGD"
    exchange_rate: Decimal = Decimal("1")
    line_items: List[LineItem]
    payment_terms: int = 30
    notes: Optional[str] = None
    quote_id: Optional[UUID] = None


class InvoiceResponse(BaseModel):
    id: UUID
    entity_id: UUID
    invoice_number: str
    customer_id: UUID
    invoice_date: date
    due_date: date
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Bills ─────────────────────────────────────────────────────────────────────

class BillCreate(BaseModel):
    entity_id: UUID
    vendor_id: UUID
    bill_date: date
    due_date: date
    reference: Optional[str] = None
    currency: str = "SGD"
    exchange_rate: Decimal = Decimal("1")
    line_items: List[LineItem]
    notes: Optional[str] = None


class BillResponse(BaseModel):
    id: UUID
    entity_id: UUID
    bill_number: str
    vendor_id: UUID
    bill_date: date
    due_date: date
    currency: str
    total_amount: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Bank Accounts ─────────────────────────────────────────────────────────────

class BankAccountCreate(BaseModel):
    entity_id: UUID
    account_id: Optional[UUID] = None
    bank_name: str
    account_name: str
    account_number: Optional[str] = None
    swift_code: Optional[str] = None
    iban: Optional[str] = None
    currency: str


class BankAccountResponse(BankAccountCreate):
    id: UUID
    current_balance: Decimal
    last_reconciled: Optional[date]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Payments ──────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    entity_id: UUID
    payment_type: str  # receipt | payment
    payment_date: date
    bank_account_id: UUID
    currency: str
    amount: Decimal
    exchange_rate: Decimal = Decimal("1")
    payment_method: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    customer_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    invoice_id: Optional[UUID] = None
    bill_id: Optional[UUID] = None


class PaymentResponse(PaymentCreate):
    id: UUID
    payment_number: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Expenses ──────────────────────────────────────────────────────────────────

class ExpenseCreate(BaseModel):
    entity_id: UUID
    expense_date: date
    category: str
    description: str
    vendor_name: Optional[str] = None
    vendor_id: Optional[UUID] = None
    account_id: Optional[UUID] = None
    currency: str
    amount: Decimal
    tax_amount: Decimal = Decimal("0")
    receipt_path: Optional[str] = None


class ExpenseResponse(ExpenseCreate):
    id: UUID
    expense_number: str
    status: str
    submitted_by: Optional[UUID]
    approved_by: Optional[UUID]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Shareholders ──────────────────────────────────────────────────────────────

class ShareholderCreate(BaseModel):
    entity_id: UUID
    name: str
    shareholder_type: str  # individual | company
    id_number: Optional[str] = None
    nationality: Optional[str] = None
    address: Optional[dict] = None
    share_class: str = "ordinary"
    shares_held: Decimal = Decimal("0")
    par_value: Decimal = Decimal("1")
    total_paid: Decimal = Decimal("0")
    ownership_pct: Optional[Decimal] = None
    effective_date: date
    notes: Optional[str] = None


class ShareholderResponse(ShareholderCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Tax Codes ─────────────────────────────────────────────────────────────────

class TaxCodeCreate(BaseModel):
    entity_id: UUID
    code: str
    name: str
    tax_type: str  # gst | vat | withholding | corporate
    rate: Decimal
    country_code: Optional[str] = None
    applies_to: str = "both"
    gl_account_id: Optional[UUID] = None


class TaxCodeResponse(TaxCodeCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Tax Returns ───────────────────────────────────────────────────────────────

class TaxReturnCreate(BaseModel):
    entity_id: UUID
    period_id: UUID
    tax_type: str
    filing_period: str
    due_date: Optional[date] = None


class TaxReturnResponse(TaxReturnCreate):
    id: UUID
    filed_date: Optional[date]
    total_tax_due: Decimal
    total_tax_paid: Decimal
    status: str
    submission_ref: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Reports ───────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    entity_id: UUID
    report_type: str  # pnl | balance_sheet | cash_flow | trial_balance | ar_aging | ap_aging | tax_summary | audit | analysis | consolidated
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    period_id: Optional[UUID] = None
    currency: str = "SGD"
    compare_previous: bool = False
    group_by: Optional[str] = None  # month | quarter | department
    format: str = "json"  # json | pdf | xlsx | csv
    include_zero_balances: bool = False
    consolidate_entities: bool = False


# ── Account Update ────────────────────────────────────────────────────────────

class AccountUpdate(BaseModel):
    entity_id: UUID
    category_id: UUID
    code: str
    name: str
    description: Optional[str] = None
    currency: str = "SGD"
    is_bank_account: bool = False
    is_control: bool = False
    allow_direct_posting: bool = True


# ── Tax Code Update ────────────────────────────────────────────────────────────

class TaxCodeUpdate(BaseModel):
    entity_id: UUID
    code: str
    name: str
    tax_type: str  # gst | vat | withholding | corporate
    rate: Decimal
    country_code: Optional[str] = None
    applies_to: str = "both"
    gl_account_id: Optional[UUID] = None


# ── Items ─────────────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    entity_id: UUID
    name: str
    description: Optional[str] = None
    category: str = "service"  # product | service | subscription | other
    unit: str = "each"
    unit_price: Decimal
    currency: str = "SGD"
    tax_code_id: Optional[UUID] = None


class ItemUpdate(ItemCreate):
    pass


class ItemResponse(ItemCreate):
    id: UUID
    item_code: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Standard API Envelope ─────────────────────────────────────────────────────

class FinanceResponse(BaseModel):
    success: bool = True
    data: Any
    meta: Optional[dict] = None
