# Mezzofy Accounting Practices

## Double-Entry Bookkeeping Rules

Every financial transaction must have equal debits and credits.

### Common Journal Entry Patterns

| Transaction | Debit | Credit |
|-------------|-------|--------|
| Issue Invoice | Accounts Receivable (1100) | Revenue (6000+) + GST Payable (3200) |
| Receive Payment | Bank (1010) | Accounts Receivable (1100) |
| Record Bill | Expense Account + GST Receivable | Accounts Payable (3000) |
| Pay Bill | Accounts Payable (3000) | Bank (1010) |
| Record Expense | Expense Account | Bank or Payable |
| Record Depreciation | Depreciation (8800) | Accumulated Depreciation (2100) |
| Record Salary | Staff Costs - Salaries (8000) | Bank (1010) / Payroll Payable |
| Record CPF | Staff Costs - CPF (8100) | Bank (1010) |

### Account Number Ranges (Mezzofy Standard SG CoA)
- 1000-1999: Assets
  - 1010: Cash and Cash Equivalents
  - 1020: Fixed Deposits
  - 1100: Accounts Receivable (Control)
  - 1200: Prepaid Expenses
  - 1300: Inventory
  - 2000: Property, Plant & Equipment
  - 2100: Accumulated Depreciation
- 3000-3999: Liabilities
  - 3000: Accounts Payable (Control)
  - 3200: GST Payable
  - 3300: Income Tax Payable
- 5000-5999: Equity
  - 5000: Share Capital
  - 5100: Retained Earnings
- 6000-6999: Revenue
  - 6000: Revenue - Coupon Exchange Fees
  - 6100: Revenue - Subscription Fees
  - 6200: Revenue - Transaction Fees
- 7000-7999: Cost of Revenue
- 8000-8999: Operating Expenses

### Multi-Currency Handling
- Base currency per entity: SGD (SG), HKD (HK), MYR (MY), CNY (CN)
- FX rates applied at transaction date
- Unrealised FX gains/losses on outstanding AR/AP at period-end
- Realised FX gains/losses on settlement

### Intercompany Transactions
- All intercompany transactions must be recorded on both sides
- Eliminated at group consolidation level
- Use intercompany clearing accounts (ask finance manager for account codes)

### Period Close Checklist
1. All invoices for the period are posted
2. All bills are approved and posted
3. All bank reconciliations are complete
4. Recurring journal entries are posted
5. Depreciation entries are posted
6. Trial balance is balanced (debits = credits)
7. Intercompany eliminations are completed (group level)
8. FX revaluation entries posted for outstanding AR/AP
9. Accruals and prepayments adjusted
10. Management review and sign-off

### GST Filing Schedule (Singapore)
- GST F5 filing: quarterly (Jan, Apr, Jul, Oct for calendar-year entities)
- Filing deadline: within 1 month of quarter-end
- Standard rate: 9% (effective 1 Jan 2024)
- Zero-rated supplies must be documented with export evidence
