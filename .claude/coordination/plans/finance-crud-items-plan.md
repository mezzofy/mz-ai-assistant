# Plan: Finance Settings CRUD + Items Module
**Date:** 2026-04-04
**Lead:** Lead Agent
**Agents:** Backend (1 session) → Frontend (1 session)
**Workflow:** Change Request

---

## Objective
1. Add full CRUD (Edit + Delete) to Chart of Accounts and Tax Codes pages
2. Build a new **Items** master module under Finance Settings for standardised item/service pricing by currency — usable as line items in Quotes (Sales) and Invoices (Finance)

---

## Scope Summary

| Area | What's missing |
|------|----------------|
| `GET/POST /api/finance/accounts` | ✅ exists |
| `PUT /api/finance/accounts/{id}` | ❌ missing |
| `DELETE /api/finance/accounts/{id}` | ❌ missing |
| `GET/POST /api/finance/tax-codes` | ✅ exists |
| `PUT /api/finance/tax-codes/{id}` | ❌ missing |
| `DELETE /api/finance/tax-codes/{id}` | ❌ missing |
| Items (`fin_items` table + CRUD API) | ❌ missing entirely |
| `ItemsPage.tsx` (frontend) | ❌ missing |
| Sidebar — Items under Finance Settings | ❌ missing |
| `portalApi` methods for items | ❌ missing |

---

## Task 1 — Backend: Accounts + Tax Codes CRUD endpoints

**File:** `server/app/finance/router.py`
**File:** `server/app/finance/schemas.py`

### 1a — Chart of Accounts endpoints

Add after the existing `POST /accounts`:

```python
@finance_router.put("/accounts/{account_id}")
async def update_account(
    account_id: UUID,
    body: AccountUpdate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update a GL account (code, name, description, currency, flags)."""
    await db.execute(
        text("""
            UPDATE fin_accounts
            SET code = :code, name = :name, description = :desc,
                currency = :curr, is_bank_account = :bank,
                is_control = :ctrl, allow_direct_posting = :direct,
                category_id = :cat
            WHERE id = :id AND entity_id = :eid
        """),
        {
            "id": str(account_id),
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
    return _ok({"id": str(account_id), **body.model_dump()})


@finance_router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(
    account_id: UUID,
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a GL account (set is_active = false)."""
    await db.execute(
        text("UPDATE fin_accounts SET is_active = false WHERE id = :id AND entity_id = :eid"),
        {"id": str(account_id), "eid": str(entity_id)},
    )
    await db.commit()
```

**New schema `AccountUpdate`** (same fields as `AccountCreate`):
```python
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
```

### 1b — Tax Codes endpoints

Add after existing `POST /tax-codes`:

```python
@finance_router.put("/tax-codes/{tc_id}")
async def update_tax_code(
    tc_id: UUID,
    body: TaxCodeUpdate,
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("""
            UPDATE fin_tax_codes
            SET code = :code, name = :name, tax_type = :type,
                rate = :rate, country_code = :country,
                applies_to = :applies, gl_account_id = :gl
            WHERE id = :id AND entity_id = :eid
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


@finance_router.delete("/tax-codes/{tc_id}", status_code=204)
async def delete_tax_code(
    tc_id: UUID,
    entity_id: UUID = Query(...),
    current_user: dict = Depends(require_permission("finance_admin")),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("UPDATE fin_tax_codes SET is_active = false WHERE id = :id AND entity_id = :eid"),
        {"id": str(tc_id), "eid": str(entity_id)},
    )
    await db.commit()
```

**New schema `TaxCodeUpdate`** (same fields as `TaxCodeCreate`):
```python
class TaxCodeUpdate(BaseModel):
    entity_id: UUID
    code: str
    name: str
    tax_type: str
    rate: Decimal
    country_code: Optional[str] = None
    applies_to: str = "both"
    gl_account_id: Optional[UUID] = None
```

---

## Task 2 — Backend: Items Module (DB + API)

### 2a — DB Migration (`server/scripts/migrate_finance_items.py`)

New standalone migration script (safe to re-run):

```sql
CREATE TABLE IF NOT EXISTS fin_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES fin_entities(id) ON DELETE CASCADE,
    item_code       VARCHAR(30) UNIQUE NOT NULL,   -- auto-generated: MZ-ITEM-0001
    name            TEXT NOT NULL,
    description     TEXT,
    category        TEXT,                           -- product | service | subscription | other
    unit            VARCHAR(20) DEFAULT 'each',     -- each | hour | day | kg | box | etc.
    unit_price      NUMERIC(20, 4) NOT NULL DEFAULT 0,
    currency        VARCHAR(10) NOT NULL DEFAULT 'SGD',
    tax_code_id     UUID REFERENCES fin_tax_codes(id),
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fin_items_entity ON fin_items(entity_id);
CREATE INDEX IF NOT EXISTS idx_fin_items_code ON fin_items(item_code);
```

**Note:** `item_code` auto-generated by `next_number()` service (same as vendors: `MZ-ITEM-0001`)

### 2b — Schemas (`server/app/finance/schemas.py`)

Add at end of file:

```python
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
    pass  # same fields

class ItemResponse(ItemCreate):
    id: UUID
    item_code: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}
```

### 2c — Router endpoints (`server/app/finance/router.py`)

Add new route group `/items` after the tax-returns section:

```python
# ── Items ─────────────────────────────────────────────────────────────────────

@finance_router.get("/items")
async def list_items(entity_id: UUID = Query(...), ...):
    SELECT * FROM fin_items WHERE entity_id = :eid AND is_active = true ORDER BY item_code

@finance_router.post("/items", status_code=201)
async def create_item(body: ItemCreate, ...):
    item_code = await FinanceService.next_number(db, "item", str(body.entity_id))
    INSERT INTO fin_items (id, entity_id, item_code, name, description, category,
                           unit, unit_price, currency, tax_code_id)
    VALUES (...)

@finance_router.put("/items/{item_id}")
async def update_item(item_id: UUID, body: ItemUpdate, ...):
    UPDATE fin_items SET name=..., description=..., category=..., unit=...,
           unit_price=..., currency=..., tax_code_id=..., updated_at=NOW()
    WHERE id = :id AND entity_id = :eid

@finance_router.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: UUID, entity_id: UUID = Query(...), ...):
    UPDATE fin_items SET is_active = false WHERE id = :id AND entity_id = :eid
```

**Permission levels:**
- GET: `require_permission("finance_read", "finance_admin")`
- POST/PUT/DELETE: `require_permission("finance_admin")`

### 2d — Register import in router.py

Add to the `from .schemas import (...)` block:
```python
ItemCreate,
ItemUpdate,
```

---

## Task 3 — Frontend: Chart of Accounts CRUD

**File:** `portal/src/pages/finance/ChartOfAccountsPage.tsx`

The existing page is read-only. Update it to support:

### 3a — Add/Edit via slide-in form panel (not separate page)

Use the **inline form panel** pattern (right side panel or modal):
- "New Account" button in top-right of page header
- Each row has an "Edit" button (pencil icon) and "Delete" button (trash icon)
- Edit/New opens a slide-over panel or modal with fields:
  - Entity (read-only in edit, selector in new)
  - Category (dropdown from `getFinanceAccountCategories`)
  - Code (text input)
  - Name (text input)
  - Description (textarea, optional)
  - Currency (text input, default SGD)
  - Is Bank Account (checkbox)
  - Is Control Account (checkbox)
  - Allow Direct Posting (checkbox)
- Save calls `portalApi.createFinanceAccount()` or `portalApi.updateFinanceAccount(id, data)`
- Delete shows inline confirm text "Confirm delete?" with Yes/No buttons (no browser alert)

### 3b — New portalApi methods needed

Add to `portal/src/api/portal.ts`:
```typescript
updateFinanceAccount: (id: string, data: any) =>
  client.put(`/api/finance/accounts/${id}`, data),
deleteFinanceAccount: (id: string, entityId: string) =>
  client.delete(`/api/finance/accounts/${id}?entity_id=${entityId}`),
getFinanceAccountCategories: (entityId: string) =>
  client.get(`/api/finance/account-categories?entity_id=${entityId}`),
```

---

## Task 4 — Frontend: Tax Codes CRUD

**File:** `portal/src/pages/finance/TaxCodesPage.tsx`

Same pattern as Chart of Accounts — inline form panel:
- "New Tax Code" button in header
- Edit/Delete per row
- Form fields:
  - Entity (read-only in edit)
  - Code (text input)
  - Name (text input)
  - Tax Type (select: GST | VAT | Withholding | Corporate)
  - Rate % (number input)
  - Applies To (select: Sales | Purchases | Both)
  - Country Code (text input, optional)
  - GL Account (optional — skip for now, too complex)
- Save calls `portalApi.createTaxCode()` or `portalApi.updateTaxCode(id, data)`
- Delete: inline confirm

### New portalApi methods:
```typescript
updateTaxCode: (id: string, data: any) =>
  client.put(`/api/finance/tax-codes/${id}`, data),
deleteTaxCode: (id: string, entityId: string) =>
  client.delete(`/api/finance/tax-codes/${id}?entity_id=${entityId}`),
```

---

## Task 5 — Frontend: Items Page (new)

**File:** `portal/src/pages/finance/ItemsPage.tsx`

New page under Finance > Settings > Items.

### Design
- Entity selector at top (same as other Finance pages)
- Table columns: Item Code | Name | Category | Unit | Unit Price | Currency | Tax Code | Active
- "New Item" button in header
- Edit + Delete per row (same inline panel pattern)
- Form fields:
  - Entity (read-only in edit)
  - Name (required)
  - Description (optional textarea)
  - Category (select: Product | Service | Subscription | Other)
  - Unit (select: Each | Hour | Day | kg | Box | Unit, or text input)
  - Unit Price (number input, 4 decimal places)
  - Currency (text input, default SGD)
  - Tax Code (optional dropdown from `portalApi.getTaxCodes(entityId)`)
- Save calls `portalApi.createItem()` or `portalApi.updateItem(id, data)`
- Delete: inline confirm

### New portalApi methods:
```typescript
getItems: (entityId: string) =>
  client.get(`/api/finance/items?entity_id=${entityId}`),
createItem: (data: any) =>
  client.post('/api/finance/items', data),
updateItem: (id: string, data: any) =>
  client.put(`/api/finance/items/${id}`, data),
deleteItem: (id: string, entityId: string) =>
  client.delete(`/api/finance/items/${id}?entity_id=${entityId}`),
```

---

## Task 6 — Sidebar: Add Items to Finance Settings group

**File:** `portal/src/components/layout/Sidebar.tsx`

In `FINANCE_NAV_ITEMS`, find the Settings group children array and add:
```typescript
{ path: '/mission-control/finance/items', label: 'Items', icon: Package },
```

Also add `Package` to the lucide-react import.

---

## Task 7 — Routes: App.tsx

**File:** `portal/src/App.tsx`

Add one new route inside the finance section:
```tsx
<Route path="finance/items" element={<ItemsPage />} />
```

Import `ItemsPage` at the top.

---

## Files to Modify

| File | Change |
|------|--------|
| `server/app/finance/router.py` | Add PUT/DELETE for accounts, tax-codes; add full Items CRUD |
| `server/app/finance/schemas.py` | Add AccountUpdate, TaxCodeUpdate, ItemCreate, ItemUpdate, ItemResponse |
| `portal/src/pages/finance/ChartOfAccountsPage.tsx` | Add inline form + CRUD actions |
| `portal/src/pages/finance/TaxCodesPage.tsx` | Add inline form + CRUD actions |
| `portal/src/components/layout/Sidebar.tsx` | Add Items to Settings group |
| `portal/src/App.tsx` | Add Items route |
| `portal/src/api/portal.ts` | Add 8 new API methods |

## Files to Create

| File | Purpose |
|------|---------|
| `server/scripts/migrate_finance_items.py` | Create fin_items table |
| `portal/src/pages/finance/ItemsPage.tsx` | Items list + CRUD UI |

---

## Agent Execution Order

**Sequential — Backend must complete before Frontend starts.**

### Session 1: Backend Agent
1. Add `AccountUpdate`, `TaxCodeUpdate`, `ItemCreate`, `ItemUpdate` to schemas.py
2. Add `PUT/DELETE /accounts/{id}` to router.py
3. Add `PUT/DELETE /tax-codes/{id}` to router.py
4. Add full Items CRUD endpoints to router.py
5. Create `migrate_finance_items.py` script
6. Update imports in router.py

### Session 2: Frontend Agent
1. Add 8 new methods to `portal/src/api/portal.ts`
2. Update `ChartOfAccountsPage.tsx` with inline CRUD form
3. Update `TaxCodesPage.tsx` with inline CRUD form
4. Create `ItemsPage.tsx`
5. Update `Sidebar.tsx` — add Items link with Package icon
6. Update `App.tsx` — add Items route

---

## Quality Gate

- [ ] `PUT /api/finance/accounts/{id}` — updates record, returns updated data
- [ ] `DELETE /api/finance/accounts/{id}` — soft deletes (is_active=false)
- [ ] `PUT /api/finance/tax-codes/{id}` — updates record
- [ ] `DELETE /api/finance/tax-codes/{id}` — soft deletes
- [ ] `GET/POST/PUT/DELETE /api/finance/items` — all working
- [ ] `migrate_finance_items.py` runs successfully on EC2
- [ ] ChartOfAccountsPage shows Edit + Delete buttons, form saves correctly
- [ ] TaxCodesPage shows Edit + Delete buttons, form saves correctly
- [ ] ItemsPage loads, shows list, can Add/Edit/Delete items
- [ ] Items link appears in Finance > Settings sidebar group
- [ ] No TypeScript errors
- [ ] No JSONB cast issues (use CAST(:param AS JSONB) if any JSON columns)
- [ ] Commit to `eric-design` branch

---

## Constraints

- Dark theme: bg `#111827`, cards `#1F2937`, accent `#f97316`
- Delete = soft delete (is_active = false), NOT hard delete
- No browser `alert()` — use inline confirmation UI
- Items are not yet integrated into Quotes/Invoices line-item selectors — that's a separate task
- Icons from `lucide-react` only
- Use `CAST(:param AS JSONB)` if any JSON params needed (asyncpg requirement)
