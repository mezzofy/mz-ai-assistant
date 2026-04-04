# Plan: Finance Menu Regroup
**Date:** 2026-04-04
**Lead:** Lead Agent
**Agent:** Frontend (1 session)
**Workflow:** Change Request

---

## Objective
Restructure the Finance sidebar from a flat 11-item list into a grouped menu with Receivables, Payables, Reports, and Settings sub-sections. Add two missing pages (Chart of Accounts, Tax Codes).

---

## Final Menu Structure

```
FINANCE (section header)
  Dashboard                         /finance
  Journal Entries                   /finance/journal

  ── RECEIVABLES ──                 (sub-section label, no link)
  Invoices                          /finance/invoices

  ── PAYABLES ──                    (sub-section label, no link)
  Bills                             /finance/bills
  Expenses                          /finance/expenses
  Payments                          /finance/payments

  ── REPORTS ──                     (sub-section label, no link)
  Reports                           /finance/reports

  ── SETTINGS ──                    (sub-section label, no link)
  Legal Entities                    /finance/entities
  Chart of Accounts                 /finance/accounts     (NEW page)
  Bank Accounts                     /finance/bank-accounts
  Vendors                           /finance/vendors
  Tax Codes                         /finance/tax-codes    (NEW page)

  Files                             /finance/files
```

---

## Tasks

### Task 1 — Sidebar restructure (`portal/src/components/layout/Sidebar.tsx`)

Replace the flat `FINANCE_NAV_ITEMS` array with a grouped structure. The sidebar needs to render:
- Regular nav links (same as current)
- Sub-section labels (non-clickable dividers styled like: smaller text, muted color, uppercase, with a horizontal rule or just the text label)

**Implementation approach:**
- Change `FINANCE_NAV_ITEMS` from a flat array to a grouped array with type discriminators, OR
- Keep a flat array but add a `group` field and `isLabel` boolean for section dividers
- Recommended: use an array that mixes nav items and label items:

```typescript
type FinanceNavItem =
  | { type: 'link'; path: string; label: string; icon: LucideIcon }
  | { type: 'label'; label: string }

const FINANCE_NAV_ITEMS: FinanceNavItem[] = [
  { type: 'link', path: '/mission-control/finance', label: 'Dashboard', icon: BarChart3 },
  { type: 'link', path: '/mission-control/finance/journal', label: 'Journal Entries', icon: BookOpen },
  { type: 'label', label: 'Receivables' },
  { type: 'link', path: '/mission-control/finance/invoices', label: 'Invoices', icon: FileText },
  { type: 'label', label: 'Payables' },
  { type: 'link', path: '/mission-control/finance/bills', label: 'Bills', icon: Inbox },
  { type: 'link', path: '/mission-control/finance/expenses', label: 'Expenses', icon: Receipt },
  { type: 'link', path: '/mission-control/finance/payments', label: 'Payments', icon: CreditCard },
  { type: 'label', label: 'Reports' },
  { type: 'link', path: '/mission-control/finance/reports', label: 'Reports', icon: PieChart },
  { type: 'label', label: 'Settings' },
  { type: 'link', path: '/mission-control/finance/entities', label: 'Legal Entities', icon: Building },
  { type: 'link', path: '/mission-control/finance/accounts', label: 'Chart of Accounts', icon: LayoutList },
  { type: 'link', path: '/mission-control/finance/bank-accounts', label: 'Bank Accounts', icon: Landmark },
  { type: 'link', path: '/mission-control/finance/vendors', label: 'Vendors', icon: Building2 },
  { type: 'link', path: '/mission-control/finance/tax-codes', label: 'Tax Codes', icon: Tag },
  { type: 'link', path: '/mission-control/finance/files', label: 'Files', icon: FolderOpen },
]
```

**Label styling** (for `type: 'label'` items):
```tsx
<div className="px-3 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider" style={{ color: '#374151' }}>
  {item.label}
</div>
```

**Render loop** — update the `.map()` inside `{showFinance && ...}` to handle both types.

**Icons needed** (check which are already imported):
- `LayoutList` — for Chart of Accounts
- `Tag` — for Tax Codes
- `Building` — for Legal Entities (different from `Building2` used for Vendors)
- All others should already be imported

---

### Task 2 — Chart of Accounts page (`portal/src/pages/finance/ChartOfAccountsPage.tsx`)

**NEW PAGE** — read-only list of chart of accounts for a selected entity.

**Data source:** `GET /api/finance/accounts?entity_id={id}` (already in portalApi as `getFinanceAccounts`)

**API response shape** (from backend `list_accounts`):
```
SELECT * FROM fin_accounts WHERE entity_id = :eid AND is_active = true ORDER BY code
```
Fields: `id, entity_id, category_id, code, name, description, currency, account_type, is_bank_account, is_control, is_active`

**Page design:**
- Match existing Finance page style: dark theme (`#111827` bg, `#1F2937` cards)
- Entity selector dropdown (same pattern as other Finance pages)
- Table with columns: Code | Name | Account Type | Currency | Bank Account | Active
- Account type badge (color-coded: Assets=blue, Liabilities=red, Equity=purple, Income=green, Expenses=orange)
- No create/edit needed for now (read-only list)
- Page header: "Chart of Accounts"

---

### Task 3 — Tax Codes page (`portal/src/pages/finance/TaxCodesPage.tsx`)

**NEW PAGE** — read-only list of tax codes for a selected entity.

**Data source:** `GET /api/finance/tax-codes?entity_id={id}` (already in portalApi as `getTaxCodes`)

**API response shape** (from backend):
Fields: `id, entity_id, code, name, tax_type, rate, applies_to, is_active`

**Page design:**
- Same dark theme style
- Entity selector dropdown
- Table with columns: Code | Name | Tax Type | Rate (%) | Applies To | Active
- No create/edit for now (read-only)
- Page header: "Tax Codes"

---

### Task 4 — Routes (`portal/src/App.tsx`)

Add two new routes inside the finance section:
```tsx
<Route path="finance/accounts" element={<ChartOfAccountsPage />} />
<Route path="finance/tax-codes" element={<TaxCodesPage />} />
```

Import the two new page components at the top of App.tsx.

---

## Files to Modify
| File | Change |
|------|--------|
| `portal/src/components/layout/Sidebar.tsx` | Restructure FINANCE_NAV_ITEMS, update render loop |
| `portal/src/App.tsx` | Add 2 new routes + imports |

## Files to Create
| File | Purpose |
|------|---------|
| `portal/src/pages/finance/ChartOfAccountsPage.tsx` | Chart of Accounts list |
| `portal/src/pages/finance/TaxCodesPage.tsx` | Tax Codes list |

---

## Quality Gate
- [ ] Finance sidebar shows grouped sub-sections (Receivables, Payables, Reports, Settings)
- [ ] Sub-section labels are non-clickable, visually distinct from nav items
- [ ] All existing routes still work (Dashboard, Journal, Invoices, Bills, etc.)
- [ ] `/finance/accounts` loads Chart of Accounts page with entity selector
- [ ] `/finance/tax-codes` loads Tax Codes page with entity selector
- [ ] No TypeScript errors
- [ ] Commit to `eric-design` branch

---

## Constraints
- Dark theme only: bg `#111827`, cards `#1F2937`, accent `#f97316`
- No new backend endpoints — use existing `getFinanceAccounts` and `getTaxCodes` from portalApi
- Read-only pages only (no create/edit modals/forms for accounts or tax codes)
- Icons must come from `lucide-react`
