# Claude Code Prompt — HR Module (Portal + HR Agent Update)

## Context
You are extending the Mezzofy AI Assistant with a **Human Resources module**.
This touches two areas:
1. **Portal (web frontend)** — new HR section in the sidebar with two sub-modules
2. **Backend** — new DB tables, API endpoints, HR tools, and an update to the **existing** HR Agent

**Additive-only. Audit before building. Do not restart any running service. Do not rewrite any working component.**

---

## Phase 0 — Mandatory Audit

```bash
# 1. Find the portal frontend
find . -type d -name "portal" -o -name "web" -o -name "admin" -o -name "dashboard" | grep -v node_modules
ls portal/src/   # or web/src/ — locate the actual portal folder

# 2. Read the sidebar / navigation config
find portal/src -name "*navigation*" -o -name "*sidebar*" -o -name "*menu*" -o -name "*routes*" | grep -v node_modules
cat <sidebar_file>

# 3. Find existing portal pages/modules for structural reference
ls portal/src/pages/        # or portal/src/screens/ or portal/src/views/
ls portal/src/components/

# 4. Read the existing HR Agent
find server/app/agents -name "*hr*"
cat server/app/agents/hr_agent.py

# 5. Read existing tool patterns
ls server/app/tools/
cat server/app/tools/base_tool.py
cat server/app/tools/crm_ops.py   # reference for DB tool pattern

# 6. Read DB schema
cat scripts/migrate.py
psql $DATABASE_URL -c "\dt"
psql $DATABASE_URL -c "\d users"

# 7. Read RBAC config
cat config/roles.yaml

# 8. Read existing portal API calls (understand how portal talks to backend)
grep -r "api\." portal/src --include="*.ts" --include="*.tsx" | head -30
cat portal/src/services/api.ts   # or equivalent
```

**STOP. Read all output before writing any code.**

---

## Phase 1 — Database Migration (Additive Only)

Append to `scripts/migrate.py`. Use `IF NOT EXISTS` on all tables. Do not touch existing tables.

```sql
-- ============================================================
-- HR MODULE TABLES
-- ============================================================

-- Employee records (optionally linked to a users account)
CREATE TABLE IF NOT EXISTS hr_employees (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,  -- link to app user (optional)
    staff_id            TEXT UNIQUE NOT NULL,                          -- e.g. MZF-SG-0001
    full_name           TEXT NOT NULL,
    email               TEXT NOT NULL,
    phone               TEXT,
    department          TEXT NOT NULL,
    job_title           TEXT,
    employment_type     TEXT DEFAULT 'full_time',    -- full_time | part_time | contract
    country             TEXT NOT NULL,               -- ISO 3166-1 alpha-2: SG, MY, HK, etc.
    location_office     TEXT,
    manager_id          UUID REFERENCES hr_employees(id) ON DELETE SET NULL,
    annual_leave_days   INTEGER NOT NULL DEFAULT 14,
    sick_leave_days     INTEGER NOT NULL DEFAULT 14,
    other_leave_days    INTEGER NOT NULL DEFAULT 0,
    hire_date           DATE NOT NULL,
    probation_end_date  DATE,
    is_active           BOOLEAN DEFAULT true,
    profile_notes       TEXT,
    created_by          UUID REFERENCES users(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Leave type catalog
CREATE TABLE IF NOT EXISTS hr_leave_types (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,            -- "Annual Leave", "Sick Leave", etc.
    code                TEXT UNIQUE NOT NULL,     -- ANNUAL, SICK, COMPASSIONATE, MATERNITY, etc.
    is_paid             BOOLEAN DEFAULT true,
    requires_document   BOOLEAN DEFAULT false,
    country             TEXT,                     -- NULL = global; ISO code = country-specific
    is_active           BOOLEAN DEFAULT true,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Leave applications
CREATE TABLE IF NOT EXISTS hr_leave_applications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES hr_employees(id),
    leave_type_id       UUID NOT NULL REFERENCES hr_leave_types(id),
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    total_days          NUMERIC(4,1) NOT NULL,
    half_day            BOOLEAN DEFAULT false,
    half_day_period     TEXT,                     -- AM | PM
    reason              TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | cancelled
    approver_id         UUID REFERENCES hr_employees(id),
    approver_comment    TEXT,
    applied_via         TEXT DEFAULT 'portal',    -- portal | chat
    document_path       TEXT,
    approved_at         TIMESTAMPTZ,
    rejected_at         TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Leave balance per employee per year
CREATE TABLE IF NOT EXISTS hr_leave_balances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     UUID NOT NULL REFERENCES hr_employees(id),
    leave_type_id   UUID NOT NULL REFERENCES hr_leave_types(id),
    year            INTEGER NOT NULL,
    entitled_days   NUMERIC(5,1) NOT NULL,
    carried_over    NUMERIC(5,1) DEFAULT 0,
    taken_days      NUMERIC(5,1) DEFAULT 0,
    pending_days    NUMERIC(5,1) DEFAULT 0,
    remaining_days  NUMERIC(5,1) GENERATED ALWAYS AS
                    (entitled_days + carried_over - taken_days) STORED,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(employee_id, leave_type_id, year)
);

-- HR-specific audit trail
CREATE TABLE IF NOT EXISTS hr_audit_log (
    id          SERIAL PRIMARY KEY,
    actor_id    UUID REFERENCES users(id),
    target_type TEXT NOT NULL,   -- employee | leave_application | leave_balance
    target_id   UUID NOT NULL,
    action      TEXT NOT NULL,   -- created | updated | deactivated | approved | rejected | cancelled
    changes     JSONB,
    source      TEXT DEFAULT 'portal',  -- portal | chat
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_hr_employees_user_id     ON hr_employees(user_id);
CREATE INDEX IF NOT EXISTS idx_hr_employees_manager_id  ON hr_employees(manager_id);
CREATE INDEX IF NOT EXISTS idx_hr_employees_dept        ON hr_employees(department);
CREATE INDEX IF NOT EXISTS idx_hr_employees_country     ON hr_employees(country);
CREATE INDEX IF NOT EXISTS idx_hr_leave_apps_employee   ON hr_leave_applications(employee_id);
CREATE INDEX IF NOT EXISTS idx_hr_leave_apps_status     ON hr_leave_applications(status);
CREATE INDEX IF NOT EXISTS idx_hr_leave_apps_dates      ON hr_leave_applications(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_hr_leave_bal_emp_yr      ON hr_leave_balances(employee_id, year);
```

Then run:
```bash
python scripts/migrate.py
psql $DATABASE_URL -c "\dt hr_*"   # confirm 5 tables exist
```

---

## Phase 2 — Seed Default Leave Types

Add to `scripts/seed.py` (or create `scripts/seed_hr.py`):

```python
DEFAULT_LEAVE_TYPES = [
    {"name": "Annual Leave",        "code": "ANNUAL",          "is_paid": True,  "requires_document": False, "country": None},
    {"name": "Sick Leave",          "code": "SICK",            "is_paid": True,  "requires_document": False, "country": None},
    {"name": "Compassionate Leave", "code": "COMPASSIONATE",   "is_paid": True,  "requires_document": True,  "country": None},
    {"name": "Maternity Leave",     "code": "MATERNITY",       "is_paid": True,  "requires_document": True,  "country": None},
    {"name": "Paternity Leave",     "code": "PATERNITY",       "is_paid": True,  "requires_document": True,  "country": None},
    {"name": "Unpaid Leave",        "code": "UNPAID",          "is_paid": False, "requires_document": False, "country": None},
    {"name": "Childcare Leave",     "code": "CHILDCARE",       "is_paid": True,  "requires_document": True,  "country": "SG"},
    {"name": "Hospitalisation Leave","code": "HOSPITALISATION","is_paid": True,  "requires_document": True,  "country": "MY"},
]
# Use INSERT ... ON CONFLICT (code) DO NOTHING — safe to re-run
```

---

## Phase 3 — RBAC Update

**Read `config/roles.yaml` first.** Then make the following additions only — do not remove anything:

```yaml
# 1. Add to the departments list:
  - hr

# 2. Add new HR roles:
  hr_staff:
    department: hr
    permissions:
      - hr_read
      - hr_write
      - hr_employee_manage
      - hr_leave_manage
      - email_send

  hr_manager:
    department: hr
    permissions:
      - hr_read
      - hr_write
      - hr_employee_manage
      - hr_leave_manage
      - hr_admin
      - hr_reports
      - email_send
      - scheduler_manage

# 3. Add to executive role (append to existing permissions list):
      - hr_read
      - hr_reports

# 4. Add hr_self_service to every existing non-HR role
#    (allows all employees to manage own leaves via Chat)
#    Append to: finance_viewer, finance_manager, sales_rep, sales_manager,
#               marketing_creator, marketing_manager, support_agent, support_manager
      - hr_self_service
```

---

## Phase 4 — HR Tools (`server/app/tools/database/hr_ops.py`)

Create this file. **Inspect existing tools (e.g. `crm_ops.py`) first and follow the exact same class/method pattern.**

Implement these tools:

```
# Employee tools
get_employee(employee_id, requesting_user_id)
list_employees(filters, requesting_user_id)
    → HR staff: all | Managers: direct reports | Others: self only
create_employee(employee_data, created_by_user_id)
    → auto-generates staff_id
    → auto-creates hr_leave_balances rows for current year
    → optionally links user_id if provided
update_employee(employee_id, updates, updated_by_user_id)
set_employee_status(employee_id, is_active, updated_by_user_id)
get_employee_profile(employee_id, requesting_user_id)
    → employee data + current year leave balances + pending applications

# Leave tools
apply_leave(application_data, employee_id)
    → validate balance, check overlapping dates
    → update pending_days in hr_leave_balances
    → notify manager via outlook_send_email
get_leave_applications(filters, requesting_user_id)
    → scoped by role (same pattern as list_employees)
get_leave_balance(employee_id, year, requesting_user_id)
update_leave_status(application_id, new_status, comment, actor_user_id)
    → new_status: approved | rejected | cancelled
    → on approve: taken_days++, pending_days--
    → on reject/cancel: pending_days--
    → cancelled by employee only if status=pending or (status=approved AND start_date > today)
    → logs to hr_audit_log, notifies employee
get_leave_summary_dashboard(year, filters, requesting_user_id)
    → per-employee: entitled/taken/pending/remaining per leave type
    → requires hr_reports or management_read
get_pending_approvals(manager_employee_id)
list_leave_types(country=None)
```

All tools must write to `hr_audit_log` on any mutation.

---

## Phase 5 — API Endpoints (`server/app/api/hr.py`)

Create this router and register it in `server/app/main.py` at prefix `/hr`.
Follow the existing router file structure exactly.

```
# Employees
GET    /hr/employees                        hr_read or management_read
POST   /hr/employees                        hr_employee_manage
GET    /hr/employees/{id}                   hr_read or self
PUT    /hr/employees/{id}                   hr_employee_manage
PATCH  /hr/employees/{id}/status            hr_employee_manage
GET    /hr/employees/{id}/profile           hr_read or self
GET    /hr/employees/{id}/leave-balance     hr_read or self

# Leave
POST   /hr/leave/apply                      hr_self_service or hr_leave_manage
GET    /hr/leave/applications               scoped by role
GET    /hr/leave/applications/{id}          scoped by role
PATCH  /hr/leave/applications/{id}/status   approve/reject: hr_leave_manage or manager
                                            cancel: employee self or hr_leave_manage
GET    /hr/leave/pending-approvals          manager or hr_leave_manage
GET    /hr/leave/types                      authenticated
GET    /hr/leave/balance                    hr_self_service (own) or hr_read (others)

# Dashboard
GET    /hr/dashboard/leave-summary          hr_reports or management_read
```

All endpoints:
- Extract `user_id`, `role`, `permissions` from JWT
- Return `{"success": bool, "data": ..., "error": null}`
- Write mutations to `hr_audit_log`
- Return 403 for insufficient permissions

---

## Phase 6 — User Account → Employee Linking

**Read the existing user creation endpoint first** (`server/app/api/admin.py` → `POST /admin/users`).

Make these additive changes only:

1. After a user is successfully created, the response should include `"employee_record_created": false` by default.
2. If the request body includes `"create_employee": true` along with basic employee fields (`staff_id`, `department`, `country`, `hire_date`, `annual_leave_days`, `sick_leave_days`), call `create_employee(...)` with `user_id` set to the new user's UUID.
3. Update `GET /auth/me` (or equivalent profile endpoint) to include:
   ```json
   {
     "employee_id": "uuid-or-null",
     "staff_id": "MZF-SG-0001-or-null",
     "manager_employee_id": "uuid-or-null"
   }
   ```
   This lets the HR Agent resolve employee context from JWT in one step.

---

## Phase 7 — Update Existing HR Agent

**Read `server/app/agents/hr_agent.py` fully before editing.**
Do not rewrite the file — only add the new tool calls and workflows listed below using the existing code structure.

Add / extend these workflows in the agent:

```python
# WORKFLOW: Staff applies leave via Chat
# Trigger: "I want to apply 3 days annual leave from 15 Apr to 17 Apr"
# 1. get_employee(user_id from JWT) → resolve employee_id
# 2. get_leave_balance(employee_id, current_year) → check availability
# 3. list_leave_types(country=employee.country) → confirm leave type
# 4. LLM → confirm details: dates, type, working days (exclude weekends)
# 5. apply_leave(confirmed_data) → submit
# 6. Return confirmation with application reference

# WORKFLOW: Staff checks balance / history
# Trigger: "How many days of annual leave do I have left?"
# 1. get_employee_profile(user_id) → employee + balances + upcoming leaves
# 2. LLM → format readable summary

# WORKFLOW: Staff cancels leave via Chat
# Trigger: "Cancel my leave on 20 Apr"
# 1. get_leave_applications(employee_id, status=[pending, approved], future only)
# 2. LLM → match application from user's description, confirm
# 3. update_leave_status(id, "cancelled")

# WORKFLOW: Manager approves / rejects via Chat
# Trigger: "Show me pending leave requests" / "Approve John's leave"
# 1. get_employee(manager user_id) → resolve manager's employee_id
# 2. get_pending_approvals(manager_employee_id)
# 3. LLM → present list, ask for decision if not stated
# 4. update_leave_status(id, "approved" | "rejected", comment)
# 5. Notify employee via outlook_send_email

# WORKFLOW: HR staff queries employee leave status
# Trigger: "Show me all employees on leave this week"
# 1. get_leave_summary_dashboard(year, filters={date_range: this_week})
# 2. LLM → format summary table
```

Also update the HR Agent's keyword/trigger list to include:
```
leave, annual leave, sick leave, apply leave, leave application, leave balance,
days off, time off, approve leave, reject leave, cancel leave, pending approval,
employee, staff, headcount, staff id, manager assignment
```

---

## Phase 8 — Portal: Sidebar Navigation

**Read the existing sidebar/navigation file first.** Add the HR section **after** the last existing module and **before** Settings/Admin (if present). Do not reorder any existing items.

```
Side Navigation — New Section:

👥  Human Resources
    ├──  👤  Employees          → /hr/employees
    └──  📅  Leave Management  → /hr/leave-management
```

Apply the same component pattern (icon, label, active state, permission guard) as the existing navigation items. The HR section is visible only to users with `hr_read`, `hr_employee_manage`, `management_read`, or `executive` permissions. Use the existing `PermissionGate` component (or equivalent).

---

## Phase 9 — Portal Pages

**Inspect 2–3 existing portal page components first** to understand the component structure, data fetching pattern (REST hooks, state management), table/list patterns, and form patterns. Mirror them exactly.

### Page 1: `/hr/employees` — Employee Listing

**Layout:** Standard data table page matching existing module pages.

**Table columns:**
| Staff ID | Full Name | Department | Country | Job Title | Manager | Status |
- Status: coloured badge — Active (green) / Inactive (grey)
- Sortable columns: Staff ID, Full Name, Department, Country
- Filters: Department (dropdown), Country (dropdown), Status (Active/Inactive toggle), Manager (search)
- Search bar: by name or staff ID

**Actions:**
- "Add New Employee" button — top right, visible only to `hr_employee_manage` permission
- Row click → opens Employee Profile drawer/page
- Row action menu: Edit | Activate/Deactivate (hr_employee_manage only)

---

### Page 2: Employee Profile (`/hr/employees/:id`)

**Tabs:**

**Tab 1 — Profile**
Fields (read-only view with Edit button for hr_employee_manage):
- Staff ID, Full Name, Email, Phone
- Department, Job Title, Employment Type
- Country, Office Location
- Manager (name + staff ID)
- Hire Date, Probation End Date
- Linked User Account (name or "Not linked")
- Profile Notes
- Created At, Last Updated
- Active/Inactive toggle (hr_employee_manage only)

**Tab 2 — Leave Balance**
- Table: Leave Type | Entitled | Carried Over | Taken | Pending | Remaining
- Year selector (current year default)
- All figures for the selected year

**Tab 3 — Leave Records**
- Table: Application Date | Leave Type | Start | End | Days | Status | Approver | Actions
- Status badges: Pending (amber), Approved (green), Rejected (red), Cancelled (grey)
- Filter by: Status, Year, Leave Type
- Action: "Cancel" button on pending/future-approved leaves (employee self or hr_leave_manage)
- "Apply Leave" button (hr_leave_manage or self)

---

### Page 3: Add / Edit Employee (`/hr/employees/new` and `/hr/employees/:id/edit`)

**Form fields:**
- Staff ID (auto-suggested as next sequential, editable)
- Full Name *(required)*
- Email *(required)*
- Phone
- Department *(required, dropdown from existing departments)*
- Job Title
- Employment Type (Full-time / Part-time / Contract)
- Country *(required, ISO dropdown: SG, MY, HK, ...)*
- Office Location
- Manager *(searchable employee picker — typeahead from hr_employees)*
- Hire Date *(required)*
- Probation End Date
- Annual Leave Days *(required, default 14)*
- Sick Leave Days *(required, default 14)*
- Other Leave Days *(default 0)*
- Profile Notes
- **Link to User Account** toggle → if ON, show searchable user picker (from users table)

**On submit (create):**
- POST `/hr/employees`
- On success: redirect to Employee Profile page
- If "Link to User Account" was selected, display confirmation that user link was saved

---

### Page 4: Leave Application Modal / Drawer

Accessible from Employee Profile Tab 3 via "Apply Leave" button.

**Fields:**
- Employee (pre-filled, read-only if opened from a profile)
- Leave Type (dropdown from `/hr/leave/types` filtered by employee's country)
- Start Date *(date picker)*
- End Date *(date picker)*
- Half Day toggle → if ON, show AM/PM selector
- Calculated working days (auto-calculated, excluding weekends, shown read-only)
- Reason (text area)
- Document upload (shown only for leave types where `requires_document = true`)
- Available balance shown inline: "You have X days of [leave type] remaining"

**Validation (frontend):**
- End date >= start date
- Working days > 0
- Available balance >= requested days (show warning if `allow_negative_balance = false`)

---

### Page 5: `/hr/leave-management` — Leave Management Dashboard

**Summary cards (top row):**
| Total Active Employees | On Leave Today | Pending Approvals | Leaves This Month |

**Main table — Employee Leave Summary:**
| Staff ID | Name | Dept | Country | Annual (Taken/Remaining) | Sick (Taken/Remaining) | Pending | Last Updated |

- Filters: Department, Country, Year (default current year), Leave Type
- Search: employee name or staff ID
- Row click → Employee Profile → Leave Records tab

**Pending Approvals tab:**
- Table: Employee | Leave Type | Start | End | Days | Applied Date | Reason | Actions
- Actions: Approve button | Reject button (with comment modal)
- Visible to: hr_leave_manage and managers (scoped to direct reports for managers)

**Export button:** Download current table view as CSV (calls existing csv_ops tool if available, or generates client-side)

---

## Phase 10 — Config Block

Add to `config/config.yaml` under a new `hr:` key. Do not modify any existing keys.

```yaml
hr:
  staff_id_format: "{COUNTRY}-{DEPT}-{SEQ:04d}"   # e.g. SG-SLS-0001
  default_leave_entitlements:
    annual_leave_days: 14
    sick_leave_days: 14
    other_leave_days: 0
  leave_rules:
    allow_half_days: true
    allow_negative_balance: false
    min_advance_notice_days: 1
    max_advance_booking_days: 365
  approval:
    auto_approve_if_no_manager: false
    escalation_after_days: 3
  notifications:
    notify_manager_on_application: true
    notify_employee_on_decision: true
  reports:
    monthly_report_teams_channel: "hr"
    monthly_report_email_recipients: []
```

---

## Phase 11 — Tests (`tests/test_hr_module.py`)

```python
# DB / tools
test_create_employee_generates_staff_id()
test_create_employee_creates_leave_balances()
test_create_employee_links_user_id()
test_apply_leave_updates_pending_balance()
test_apply_leave_blocks_insufficient_balance()
test_apply_leave_blocks_overlapping_dates()
test_approve_leave_moves_pending_to_taken()
test_cancel_pending_leave_restores_balance()
test_cancel_past_consumed_leave_is_blocked()
test_employee_scoping_cannot_see_others()
test_manager_sees_direct_reports_only()
test_hr_staff_sees_all()
test_hr_audit_log_on_create()
test_hr_audit_log_on_status_change()

# API
test_post_employee_requires_hr_permission()
test_get_employee_self_allowed()
test_patch_status_requires_hr_permission()
test_leave_dashboard_requires_hr_reports()
test_cancel_consumed_leave_returns_400()

# Agent
test_hr_agent_routes_apply_leave_message()
test_hr_agent_routes_balance_check_message()
test_hr_agent_routes_cancel_leave_message()
test_hr_agent_routes_manager_approval_message()
```

---

## Phase 12 — Docs Update

After all code is written and tests pass, append to these docs only — do not modify unrelated sections:

- **MEMORY.md** → add `hr_employees`, `hr_leave_types`, `hr_leave_applications`, `hr_leave_balances`, `hr_audit_log` to the Core Tables section
- **AGENTS.md** → add new HR workflows to the existing HR Agent section
- **TOOLS.md** → add hr_ops.py to the `/database` tools table
- **SECURITY.md** → add `hr_read`, `hr_write`, `hr_employee_manage`, `hr_leave_manage`, `hr_admin`, `hr_reports`, `hr_self_service` to the Permission → Tool Mapping table

---

## Hard Rules

```
❌ DO NOT restart FastAPI, Celery worker, or Celery Beat
❌ DO NOT alter or drop any existing DB table
❌ DO NOT rewrite the existing HR Agent — only extend it
❌ DO NOT modify any existing agent, tool, or API endpoint
❌ DO NOT remove any existing role or permission from roles.yaml
❌ DO NOT reference React Native / mobile app — this is Portal (web) only
✅ All new DB tables use IF NOT EXISTS
✅ All API endpoints follow existing response envelope: {"success", "data", "error"}
✅ All write operations logged to hr_audit_log
✅ All tools enforce user_id scoping
✅ Portal pages follow the exact component/page pattern of existing portal pages
✅ Run: pytest tests/test_hr_module.py -v before declaring done
```

---

## Execution Order

```
Phase 0  → Audit (mandatory)
Phase 1  → DB migration
Phase 2  → Seed leave types
Phase 3  → RBAC update
Phase 4  → hr_ops.py tools
Phase 5  → /hr API router
Phase 6  → User ↔ Employee linking (additive patch to admin.py)
Phase 7  → Update existing HR Agent (extend, do not rewrite)
Phase 8  → Portal sidebar navigation
Phase 9  → Portal pages (5 pages / components)
Phase 10 → config.yaml hr block
Phase 11 → Tests
Phase 12 → Docs update
```
