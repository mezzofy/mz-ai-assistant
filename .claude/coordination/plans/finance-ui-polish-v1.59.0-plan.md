# Finance UI Polish + Entities Enhancements — Plan (v1.59.0)
**Date:** 2026-03-31
**Lead Agent:** eric-design branch
**Workflow:** Change Request (3 tasks)

---

## Overview

Three polish tasks on the Finance module:

1. **UI consistency** — Align all 15 Finance pages to the Leads (CRMPage) visual standard
2. **Entities enhancements** — Sort by Code, add Business ID column + field (optional)
3. **Entity-scoped currency** — Currency labels reflect the selected entity's `base_currency`

---

## Reference Standard — Leads (CRMPage.tsx)

| Element | Leads Pattern |
|---------|-------------|
| Wrapper | `<div className="space-y-5">` |
| Page title | `<h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>` |
| Subtitle / count | `<span className="text-sm" style={{ color: '#6B7280' }}>` |
| Header row | `<div className="flex items-center justify-between">` |
| Primary button | `className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"` + `style={{ background: '#f97316' }}` |
| Table body font | `fontSize: 13` |
| Secondary text | `color: '#9CA3AF'`, `fontSize: 13` |
| Muted values | `color: '#6B7280'`, `fontSize: 12` |

Current Finance pages use `style={{ padding: 24, color: '#F9FAFB' }}` wrapper, `fontSize: 20` titles, `fontSize: 13` button labels with `padding: '8px 16px'` — all need alignment.

---

## Task 1 — UI Polish: All 15 Finance Pages (Frontend)

**Files to update** (all in `portal/src/pages/finance/`):
- `FinanceDashboard.tsx`
- `JournalEntries.tsx`
- `Invoices.tsx`
- `Quotes.tsx`
- `Bills.tsx`
- `Payments.tsx`
- `Customers.tsx`
- `Vendors.tsx`
- `BankAccounts.tsx`
- `Expenses.tsx`
- `Reports.tsx`
- `Entities.tsx`
- `Shareholders.tsx`
- `Periods.tsx`
- `TaxCodes.tsx`

**Changes per page:**

1. **Outer wrapper**: Change `<div style={{ padding: 24, color: '#F9FAFB' }}>` → `<div className="space-y-5" style={{ color: '#F9FAFB' }}>` (add `padding: 24` back as `style={{ padding: 24 }}` on inner content div if the outer removes it — or use `className="space-y-5 p-6"`)

   Actually the cleaner fix: change the outermost div to `<div className="space-y-5">` and keep inner styling as needed. Most pages have a top header bar + a content card, this wrapper just adds vertical gap between sections.

2. **Page title h1**: Change inline `style={{ fontSize: 20/22, fontWeight: 700, margin: 0 }}` → `className="text-2xl font-bold text-white"` with `style={{ fontFamily: 'Space Grotesk, sans-serif', margin: 0 }}`

3. **Subtitle/description p**: Change inline `style={{ color: '#6B7280', fontSize: 13, margin: '4px 0 0' }}` → `className="text-sm"` with `style={{ color: '#6B7280', margin: '4px 0 0' }}`

4. **Primary action buttons** (New Invoice, New Bill, etc.): Change padding from `'8px 16px'` to match `px-4 py-2` (same pixel equivalent), but use `className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all"` pattern instead of full inline styles. Keep `style={{ background: '#f97316' }}` for color.

5. **Header row div**: Ensure `display: flex, justifyContent: 'space-between', alignItems: 'center'` — either keep as inline or use `className="flex items-center justify-between"`.

---

## Task 2 — Entities: Sort + Business ID (Backend + Frontend)

### 2a — Backend: Add `business_id` column (Backend Agent)

**New file: `server/scripts/migrate_finance_business_id.py`**
- Standalone psycopg2 ALTER TABLE script (same pattern as `migrate_finance.py`)
- SQL: `ALTER TABLE fin_entities ADD COLUMN IF NOT EXISTS business_id TEXT;`
- Safe to re-run (uses `IF NOT EXISTS`)

**Modify: `server/app/finance/schemas.py`**
- `FinEntityCreate`: add `business_id: Optional[str] = None`
- `FinEntityResponse` / any FinEntity response models: add `business_id: Optional[str] = None`

**Modify: `server/app/finance/router.py`**
- `POST /entities` create: include `business_id` in INSERT columns
- `GET /entities` list: include `business_id` in SELECT
- `GET /entities/{id}` detail: include `business_id` in SELECT

### 2b — Frontend: Entities page updates (Frontend Agent)

**Modify: `portal/src/types/index.ts`**
- `FinEntity` interface: add `business_id?: string`

**Modify: `portal/src/pages/finance/Entities.tsx`**
- **Sort**: apply `[...entities].sort((a, b) => a.code.localeCompare(b.code))` before rendering
- **Table columns**: change `['Code', 'Name', 'Type', 'Country', 'Currency', 'Tax ID', 'Status']` → `['Code', 'Name', 'Type', 'Country', 'Currency', 'Business ID', 'Tax ID', 'Status']`
- **Table row cells**: add Business ID cell `<td style={{ padding: '10px 14px', color: '#6B7280', fontSize: 12 }}>{e.business_id || '—'}</td>` BEFORE the Tax ID cell
- **Modal form state**: add `business_id: ''` to initial `form` state
- **Modal fields**: add Business ID input field (optional, label "Business ID") BEFORE Tax ID field in the form
- **handleSave**: `form` already passed to API — backend will include `business_id` once schema updated

---

## Task 3 — Entity-Scoped Currency Display (Frontend)

**Problem:** Currency labels are hardcoded as `'SGD'` across Finance pages (e.g., KpiCard in Dashboard shows `currency = 'SGD'`, amount column headers say "Amount (SGD)").

**Fix:** Each page that has an entity selector already loads the `entities` array AND tracks `selectedEntity` (ID string). Derive:
```tsx
const selectedEntityObj = entities.find(e => e.id === selectedEntity)
const currency = selectedEntityObj?.base_currency || 'SGD'
```
Then use `currency` variable wherever currency labels appear.

**Pages to update:**

| Page | Where currency appears |
|------|----------------------|
| `FinanceDashboard.tsx` | `KpiCard currency` prop (currently hardcoded `'SGD'`) |
| `Invoices.tsx` | Amount column header, any inline "SGD" labels |
| `Quotes.tsx` | Amount column header |
| `Bills.tsx` | Amount column header |
| `Payments.tsx` | Amount column header |
| `Customers.tsx` | Balance column header |
| `Vendors.tsx` | Balance column header |
| `JournalEntries.tsx` | Amount columns |
| `Expenses.tsx` | Amount column |
| `BankAccounts.tsx` | Balance column |
| `Shareholders.tsx` | Par value / total paid columns |
| `Reports.tsx` | Currency selector default |

**Pattern to apply per page:**
1. Confirm the page already loads `entities` and has `selectedEntity` state
2. If not (e.g., Entities/Periods/TaxCodes pages that don't show amounts — skip)
3. Add: `const currency = entities.find(e => e.id === selectedEntity)?.base_currency || 'SGD'`
4. Replace all occurrences of hardcoded `'SGD'` in JSX/labels with `{currency}`

**Note:** Pages without entity selectors or amount displays (Periods, TaxCodes) do not need this change.

---

## Agent Assignments

| Agent | Tasks | Sessions |
|-------|-------|---------|
| **Backend** | Task 2a — Add `business_id` column + schema + router | 1 session |
| **Frontend** | Task 1 — UI polish on 15 pages; Task 2b — Entities.tsx + types; Task 3 — currency from entity | 1 session |

**Parallelism:** Backend 2a and Frontend (Tasks 1, 2b, 3) can run in parallel — different file trees.

**Frontend notes:**
- For Task 2b, `FinEntity` type update + Entities.tsx can be done alongside UI polish
- For Task 3, the `entities` array is already loaded on most pages — just derive `currency`
- The portal build must succeed — `npm run build` after all changes

---

## Files to Create/Modify

### Backend
- `server/scripts/migrate_finance_business_id.py` (new)
- `server/app/finance/schemas.py` (modify — add business_id)
- `server/app/finance/router.py` (modify — business_id in entities CRUD)

### Frontend
- `portal/src/types/index.ts` (modify — add business_id to FinEntity)
- `portal/src/pages/finance/Entities.tsx` (modify — sort, col, field)
- `portal/src/pages/finance/FinanceDashboard.tsx` (modify — UI + currency)
- `portal/src/pages/finance/JournalEntries.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Invoices.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Quotes.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Bills.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Payments.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Customers.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Vendors.tsx` (modify — UI + currency)
- `portal/src/pages/finance/BankAccounts.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Expenses.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Reports.tsx` (modify — UI + currency)
- `portal/src/pages/finance/Shareholders.tsx` (modify — UI)
- `portal/src/pages/finance/Periods.tsx` (modify — UI)
- `portal/src/pages/finance/TaxCodes.tsx` (modify — UI)

---

## Deployment After Completion

```bash
# EC2
cd ~/mz-ai-assistant && git pull
cd server && venv/bin/python scripts/migrate_finance_business_id.py
sudo systemctl restart mezzofy-api.service

# Portal
cd portal && npm run build
sudo cp -r dist/* /var/www/mission-control/
```
