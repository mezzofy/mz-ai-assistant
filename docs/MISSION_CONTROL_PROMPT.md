# Claude Code CLI Prompt — Mission Control Portal
## Mezzofy AI Assistant · Admin Web Application

---

## PREAMBLE — Read Before Writing Any Code

You are building the **Mezzofy AI Assistant Mission Control Portal** — a secure, internally-hosted admin web application for `admin@mezzofy.com` only.

Before writing a single line of code, you must:
1. **Audit** the existing codebase: read `server/app/api/auth.py`, `server/app/api/admin.py`, `server/app/main.py`, `server/app/gateway.py`, `server/app/models/` (or equivalent schema files), and `server/config/.env.example`.
2. **Identify** all existing API endpoints, DB tables (`users`, `conversations`, `llm_usage`, `scheduled_jobs`, `artifacts`, `audit_log`), JWT auth flow, OTP mechanism (if present), and any admin-scoped routes.
3. **List gaps** — endpoints or DB columns that the portal needs but do not yet exist.
4. Only after the audit: implement gaps additively, then build the portal.

**Hard rules — never break these:**
- Do NOT restart FastAPI, Celery workers, or Celery Beat.
- Do NOT modify any existing working endpoint or DB migration.
- Do NOT store `admin@mezzofy.com` credentials in code or frontend assets.
- All new backend code must be additive (new files or new routes appended to existing routers).
- Portal runs on a separate port/path (`/admin-portal`) distinct from the mobile API.

---

## PHASE 0 — Codebase Audit

```
Audit checklist — report findings before proceeding:

[ ] server/app/api/auth.py          — existing login/OTP/refresh flow
[ ] server/app/api/admin.py         — existing admin endpoints
[ ] server/app/models/ or migrate.py — DB schema: users, llm_usage, scheduled_jobs,
                                        conversations, artifacts, audit_log
[ ] server/scheduler/beat_schedule.py — Celery Beat job definitions
[ ] server/app/main.py              — registered routers, middleware, CORS
[ ] server/config/.env.example      — available env vars
[ ] Any existing /admin/* routes     — avoid conflicts

Report:
- Which OTP mechanism exists (TOTP/email/SMS)?  
- Does llm_usage have cost + token columns per model?
- Does scheduled_jobs have run_history JSON or separate table?
- Is there a system_metrics endpoint already?
- Does the users table have invite_token, invited_at, password_reset_token columns?
```

---

## PHASE 1 — Backend: New Admin API Endpoints

### Location
All new endpoints go in `server/app/api/admin_portal.py` (new file).  
Register the router in `main.py` under prefix `/api/admin-portal` with `tags=["admin-portal"]`.

### Auth Middleware
Create `server/app/middleware/admin_only.py`:
- Validates JWT (reuse existing `verify_token` utility).
- Enforces `email == "admin@mezzofy.com"` and `role == "admin"` — return HTTP 403 otherwise.
- Apply this middleware to **every** `/api/admin-portal/*` route.

### 1.1 Authentication Endpoints (if OTP flow gaps exist)

```
POST /api/admin-portal/auth/login
  Body: { email, password }
  Logic: validate against users table (bcrypt), enforce admin@mezzofy.com only,
         generate 6-digit OTP, store in Redis with TTL=300s key="admin_otp:{user_id}",
         send OTP via existing outlook_send_email tool to admin@mezzofy.com
  Response: { message: "OTP sent", session_token: <temp_jwt_15min> }

POST /api/admin-portal/auth/verify-otp
  Body: { session_token, otp }
  Logic: verify temp JWT, check Redis OTP match, delete Redis key on success,
         issue full access_token (1h) + refresh_token (7d) with role:"admin"
  Response: { access_token, refresh_token, user }

POST /api/admin-portal/auth/refresh
  Body: { refresh_token }
  Response: { access_token }

POST /api/admin-portal/auth/logout
  Logic: blacklist refresh_token in Redis (key="blacklist:{jti}", TTL=7d)
```

### 1.2 Dashboard Endpoints

```
GET /api/admin-portal/dashboard/sessions
  Returns: active AI sessions from conversations table joined with users,
           fields: session_id, user_id, user_name, department, agent_used,
                   model_used, total_tokens, estimated_cost_usd, last_active,
                   message_count, is_active (last_active within 30 min)

GET /api/admin-portal/dashboard/llm-usage
  Query params: ?period=today|week|month
  Returns: per-model token usage and cost from llm_usage table,
           fields: model_name, total_tokens, total_cost_usd, request_count,
                   avg_tokens_per_request, daily_budget_usd, usage_pct_of_budget
  Budget thresholds loaded from config: admin_portal.llm_budgets in config.yaml

GET /api/admin-portal/dashboard/system-vitals
  Returns: real-time EC2 metrics via psutil (install if not present):
           cpu_percent, memory_used_gb, memory_total_gb, memory_pct,
           disk_used_gb, disk_total_gb, disk_pct, load_avg_1m, load_avg_5m,
           uptime_seconds
  Also returns: redis_connected (bool), postgres_connected (bool),
                celery_active_workers (int), celery_queued_tasks (int)

GET /api/admin-portal/dashboard/agent-status
  Returns: for each agent (finance, sales, marketing, support, management, hr):
           agent_name, is_busy (has active Celery task), current_task (or null),
           tasks_completed_today, last_active_at
  Source: query Celery inspect API + agent_tasks table (if exists) or active tasks from Redis
```

### 1.3 Scheduled Tasks Endpoints

```
GET /api/admin-portal/scheduler/jobs
  Returns: all rows from scheduled_jobs table with user info joined,
           fields: id, name, description, schedule_type, cron_expression,
                   created_by_email, department, is_active, last_run_at,
                   next_run_at, run_count, last_status

GET /api/admin-portal/scheduler/jobs/{job_id}/history
  Returns: execution history (last 50 runs), fields: run_at, status,
           duration_ms, output_summary, error_message

POST /api/admin-portal/scheduler/jobs/{job_id}/trigger
  Logic: manually enqueue the Celery task for immediate execution,
         record in run history as source="manual_admin_trigger"
  Response: { task_id, queued_at }

PATCH /api/admin-portal/scheduler/jobs/{job_id}/toggle
  Logic: set is_active = true/false in scheduled_jobs, update Celery Beat schedule
  Response: { id, is_active }
```

### 1.4 Agents & Skills Endpoints

```
GET /api/admin-portal/agents
  Returns: static + dynamic agent info:
           agent_name, display_name, department, description,
           associated_skills: [{ skill_name, description, tool_count }],
           rag_memory_count (count of knowledge files loaded for this agent),
           tasks_today, status (idle/busy)

GET /api/admin-portal/agents/{agent_name}/rag-memory
  Returns: list of knowledge base documents for this agent from /knowledge/ dir,
           fields: filename, size_bytes, last_modified, chunk_count (if indexed)
```

### 1.5 Files & Folders Endpoints

```
GET /api/admin-portal/files
  Query params: ?user_id=&type=&page=&per_page=20
  Returns: paginated list from artifacts table joined with users,
           fields: id, filename, file_type, size_bytes, created_at,
                   owner_email, download_url (signed or direct), department

DELETE /api/admin-portal/files/{file_id}
  Logic: delete artifact record + file from EBS/S3, audit log entry
```

### 1.6 User Management Endpoints

```
GET /api/admin-portal/users
  Returns: all users from users table,
           fields: id, email, name, department, role, is_active,
                   created_at, last_login_at, session_count

POST /api/admin-portal/users
  Body: { email, name, department, role }
  Logic: create user row with is_active=false, generate invite_token (UUID4),
         store invite_token + invited_at in users table (add columns if missing),
         send invite email via outlook_send_email with link:
         https://{PORTAL_DOMAIN}/mobile-invite?token={invite_token}
         Email includes: app download instructions + one-time password setup link
  Response: { user_id, invite_sent_at }

GET /api/admin-portal/users/{user_id}
  Returns: full user profile + recent sessions + usage stats

PATCH /api/admin-portal/users/{user_id}
  Body: { name?, department?, role?, is_active? }
  Logic: update users table, audit log entry

DELETE /api/admin-portal/users/{user_id}
  Logic: soft-delete (set is_active=false, deleted_at=now()),
         revoke all active sessions (blacklist tokens in Redis),
         audit log entry. Never hard-delete.
```

### 1.7 DB Migration Additions (additive only)

If the following columns do not exist, add them via a new Alembic migration
`server/alembic/versions/XXXX_admin_portal_additions.py`:

```sql
-- users table additions
ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_token VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- llm_usage additions (if cost tracking columns missing)
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,6) DEFAULT 0;
ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS model_name VARCHAR(64);
```

### 1.8 Config Block

Add to `server/config/config.yaml` under `admin_portal:` key:

```yaml
admin_portal:
  allowed_email: "admin@mezzofy.com"
  otp_ttl_seconds: 300
  session_idle_minutes: 30        # threshold for "active session"
  portal_domain: ""               # set in .env as PORTAL_DOMAIN
  llm_budgets:
    claude-haiku: { daily_usd: 10.0 }
    claude-sonnet: { daily_usd: 50.0 }
    claude-opus: { daily_usd: 100.0 }
    kimi: { daily_usd: 20.0 }
  file_retention_days: 90
```

---

## PHASE 2 — Frontend: React Web Application

### Stack
- **React 18** + **TypeScript** + **Vite**
- **TailwindCSS** (utility classes only, no component libraries that add bloat)
- **React Router v6** (SPA routing)
- **Axios** (HTTP client with interceptors for JWT refresh)
- **Recharts** (charts for LLM usage, system vitals)
- **React Query / TanStack Query** (server state, polling)

### Location
`/portal/` directory at repo root (sibling to `/server/` and `/mobile/`).

### File Structure

```
/portal
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── src/
    ├── main.tsx
    ├── App.tsx                         # Router setup
    ├── api/
    │   ├── client.ts                   # Axios instance + JWT interceptor
    │   ├── auth.ts
    │   ├── dashboard.ts
    │   ├── scheduler.ts
    │   ├── agents.ts
    │   ├── files.ts
    │   └── users.ts
    ├── hooks/
    │   ├── useAuth.ts
    │   └── usePolling.ts               # React Query polling helper
    ├── stores/
    │   └── authStore.ts                # Zustand for auth state
    ├── components/
    │   ├── layout/
    │   │   ├── AppShell.tsx            # Sidebar + topbar wrapper
    │   │   ├── Sidebar.tsx
    │   │   └── TopBar.tsx
    │   ├── ui/
    │   │   ├── Badge.tsx
    │   │   ├── Button.tsx
    │   │   ├── Card.tsx
    │   │   ├── Modal.tsx
    │   │   ├── Table.tsx
    │   │   ├── Input.tsx
    │   │   └── StatusDot.tsx
    │   └── pixels/
    │       ├── AgentOffice.tsx         # Pixel art office scene (canvas/SVG)
    │       └── AgentSprite.tsx         # Individual agent pixel character
    └── pages/
        ├── LoginPage.tsx
        ├── OtpPage.tsx
        ├── DashboardPage.tsx
        ├── SchedulerPage.tsx
        ├── AgentsPage.tsx
        ├── FilesPage.tsx
        └── UsersPage.tsx
```

---

## PHASE 3 — Design System & Theme

### Color Palette (Dark Theme — matches mobile app aesthetic)

```
Background:       #0A0E1A   (deep navy — primary bg)
Surface:          #111827   (card bg)
Surface-2:        #1C2333   (elevated card / sidebar)
Border:           #2D3748   (subtle divider)
Accent-Primary:   #6C63FF   (Mezzofy purple — primary CTA, active states)
Accent-Secondary: #00D4AA   (teal — success, online indicators)
Accent-Warning:   #F59E0B   (amber — warnings, approaching quota)
Accent-Danger:    #EF4444   (red — errors, critical alerts)
Text-Primary:     #F1F5F9   (white-ish)
Text-Secondary:   #94A3B8   (muted)
Text-Muted:       #475569   (labels)

Pixel art palette (for agent office scene):
  Floor:   #1E2A3A tiles
  Desk:    #2D4A2D green felt
  Wall:    #152030
  Accent:  #6C63FF neon trim
```

### Typography
- Headings: `'Space Grotesk', sans-serif` (CDN import)
- Body: `'Inter', sans-serif`
- Monospace (tokens, cron): `'JetBrains Mono', monospace`

### Component Design Rules
- All cards: `rounded-xl border border-[#2D3748] bg-[#111827]`
- Hover states: `hover:border-[#6C63FF] transition-colors duration-200`
- Active nav item: left border `border-l-2 border-[#6C63FF] bg-[#1C2333]`
- Buttons primary: `bg-[#6C63FF] hover:bg-[#5A52E0] text-white rounded-lg px-4 py-2`
- Status dots: 8px circle, pulse animation when active
- All tables: sticky header, alternating row bg `#0A0E1A / #111827`

---

## PHASE 4 — Page Specifications

### 4.1 Login Page (`/login`)

Layout: centered card on full-screen dark bg with subtle animated grid pattern.

```
┌─────────────────────────────────┐
│  🤖  Mezzofy Mission Control    │  (logo + title)
│                                 │
│  [Email input]                  │
│  [Password input]               │
│  [Login →] button               │
│                                 │
│  "Restricted to admin only"     │  (muted caption)
└─────────────────────────────────┘
```

- On submit: POST `/api/admin-portal/auth/login`
- On success: navigate to `/verify-otp`, store `session_token` in memory (NOT localStorage)
- On error: inline error message, no toast

### 4.2 OTP Page (`/verify-otp`)

```
┌─────────────────────────────────┐
│  Check your email               │
│  Enter the 6-digit code sent    │
│  to admin@mezzofy.com           │
│                                 │
│  [  ] [  ] [  ] [  ] [  ] [  ] │  (6 separate digit inputs, auto-advance)
│                                 │
│  [Verify Code] button           │
│  [Resend code] link (60s timer) │
└─────────────────────────────────┘
```

- Auto-focuses next box on digit entry
- On success: store `access_token` + `refresh_token` in memory via Zustand, navigate to `/dashboard`
- Axios interceptor auto-refreshes access_token before expiry

### 4.3 Dashboard Page (`/dashboard`)

#### Section A — Session Monitor (top table)
Polling: every 30 seconds via React Query.

Columns: User · Department · Agent · Model · Tokens · Est. Cost · Last Active · Status

Status badge: `● Active` (green pulse) or `○ Idle` (grey), based on last_active threshold.

#### Section B — LLM Fuel Gauges

Horizontal gauge bars, one per model. For each:
```
claude-sonnet    ████████░░░░░░░░  $34.20 / $50.00  (68%)
                 [WARNING at 80%] [CRITICAL at 95%]
```
Color: green → amber (80%) → red (95%).  
Data polling: every 60 seconds.

#### Section C — System Vitals

4 cards in a 2×2 grid:
- **CPU** — radial gauge (0–100%), current % + 1m/5m load avg
- **Memory** — horizontal bar, GB used / total
- **Disk** — horizontal bar, GB used / total  
- **Services** — status dot grid: FastAPI · PostgreSQL · Redis · Celery Workers (N/4) · Celery Beat

Polling: every 15 seconds.

#### Section D — Agent Office (Pixel Art)

Full-width panel below vitals. Rendered on an HTML `<canvas>` (800×400px, scaled responsively).

**Office layout:**
```
┌──────────────────────────────────────────────────────────────┐
│  MEZZOFY AI — OPERATIONS FLOOR                               │
│                                                              │
│  [Manager Desk - center-top]                                 │
│       👔 Manager                                             │
│      "Overseeing all ops"                                    │
│                                                              │
│  [Finance]  [Sales]   [Marketing]  [Support]  [HR]          │
│    💰 Fin    🎯 Sales   📣 Mktg      🎧 Supp   👥 HR         │
│   "Idle"   "Working"   "Idle"      "Idle"    "Working"      │
└──────────────────────────────────────────────────────────────┘
```

**Pixel art specs:**
- Each agent: 16×16 pixel sprite, hand-drawn style using canvas `fillRect` calls
- Each agent has a unique colour palette and hat/icon:
  - **Manager** (center-top, larger desk): dark suit, glasses, purple tie
  - **Finance**: green visor cap, calculator on desk
  - **Sales**: blue blazer, phone headset
  - **Marketing**: orange beret, laptop
  - **Support**: teal headset, ticket stack
  - **HR**: pink folder, nameplate
- Agent name rendered above sprite in `'JetBrains Mono'` 8px
- When agent `is_busy=true`: animated speech bubble appears (`●●●` typing dots, CSS keyframe)
- When `is_busy=false`: speech bubble hidden, agent sprite in "idle" seated animation (1px bob, 2s loop)
- Floor tiles: 8×8 checkerboard pattern `#1E2A3A / #162030`
- Desk sprites: 24×12px green felt rectangles with monitor sprites
- Neon trim on walls: `#6C63FF` 1px border glow
- Agent office data polls from `/api/admin-portal/dashboard/agent-status` every 20 seconds

### 4.4 Scheduled Tasks Page (`/scheduler`)

Two panels side by side (on desktop), stacked on mobile.

**Left — Jobs Table:**
Columns: Name · Owner · Department · Schedule · Last Run · Next Run · Status · Actions

Status badges: `Active` (green) · `Paused` (grey) · `Failed` (red)

Row actions:
- ▶ Manual trigger → POST trigger endpoint → shows toast "Task queued"
- ⏸ Pause/Resume toggle
- 🔍 View history (opens right panel)

**Right — Run History Panel:**
Triggered by clicking a job row.  
Shows last 50 executions as timeline:
```
● 2026-03-18 09:00  ✓ Success  (1m 23s)
● 2026-03-11 09:00  ✓ Success  (1m 41s)  
● 2026-03-04 09:00  ✗ Failed   — "DB timeout"
```

### 4.5 Agents & Skills Page (`/agents`)

Grid of agent cards (3 columns desktop, 1 mobile).

Each card:
```
┌─────────────────────────────┐
│  🎯 Sales Agent             │
│  Department: Sales          │
│  Status: ● Idle             │
│  Tasks today: 14            │
│                             │
│  Skills (3):                │
│  • linkedin_prospecting     │
│  • email_outreach           │
│  • pitch_deck_generation    │
│                             │
│  RAG Memory: 12 documents   │
│  [View Memory ›]            │
└─────────────────────────────┘
```

Clicking "View Memory" expands an accordion panel listing knowledge files:
filename · size · last_modified.

### 4.6 Files & Folders Page (`/files`)

Full-width table with filters:
- Filter by: User / Department / File Type / Date Range
- Columns: Filename · Type · Size · Owner · Department · Created · Actions
- Actions: ⬇ Download · 🗑 Delete (with confirmation modal)
- Pagination: 20 per page

File type icons (emoji fallback if SVG not available):
📄 PDF · 📊 XLSX · 📝 DOCX · 📽 PPTX · 📦 Other

### 4.7 User Management Page (`/users`)

**User List Table:**
Columns: Avatar (initials) · Name · Email · Department · Role · Status · Last Login · Actions

Actions: ✏ Edit · 🗑 Delete

**Create User Modal (+ New User button top-right):**
```
┌──────────────────────────────────┐
│  Create New User                 │
│                                  │
│  Full Name:    [____________]    │
│  Email:        [____________]    │
│  Department:   [Dropdown    ▾]   │
│  Role:         [Dropdown    ▾]   │
│                                  │
│  [Cancel]          [Send Invite] │
└──────────────────────────────────┘
```

On "Send Invite": POST create user → success toast "Invite sent to user@mezzofy.com".

**Edit User Modal:**
Pre-filled form. Editable: Name, Department, Role, Active status toggle.

**Delete Confirmation Modal:**
```
"Deactivate [Name]? This will revoke all active sessions. This cannot be undone."
[Cancel]  [Deactivate]
```

---

## PHASE 5 — Security Implementation

### Frontend Security
- `access_token` and `refresh_token` stored in **Zustand in-memory state only** — never `localStorage`, never `sessionStorage`, never cookies.
- On page refresh: user must re-authenticate (this is intentional for admin security).
- Axios request interceptor: if 401 received, attempt silent refresh via `/auth/refresh`. If refresh fails, clear state + redirect to `/login`.
- All API calls use HTTPS only. The Vite dev proxy rewrites `/api` to the FastAPI server.
- Route guard: `<AdminRoute>` wrapper component checks auth state; redirects to `/login` if unauthenticated.

### Backend Security
- Admin-only middleware (Phase 1) applied to all portal routes.
- OTP stored in Redis with TTL — never in DB.
- Rate limit login attempts: max 5/minute per IP via existing Redis rate limiter.
- All portal actions written to `audit_log` table with `source="admin_portal"`.
- `deleted_at` soft-delete pattern — no hard deletes on users.

---

## PHASE 6 — Build & Deployment

### Development
```bash
# Install portal deps
cd portal && npm install

# Vite dev server with proxy to FastAPI
npm run dev
# Runs on http://localhost:5173
# Proxies /api/* → http://localhost:8000
```

### Production Build
```bash
cd portal && npm run build
# Output: portal/dist/
```

### Nginx Config Addition (append to existing nginx.conf — do NOT replace it)
```nginx
# Mission Control Portal — serve built React app
location /mission-control {
    alias /home/ubuntu/mezzofy-ai-assistant/portal/dist;
    try_files $uri $uri/ /mission-control/index.html;
}

# Admin portal API proxy
location /api/admin-portal/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### Vite Config
```typescript
// vite.config.ts
export default defineConfig({
  base: '/mission-control/',
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

---

## PHASE 7 — Dependencies to Install

### Backend (append to requirements.txt — check for existing before adding)
```
psutil==5.9.8          # EC2 system vitals (CPU, memory, disk)
```

### Frontend (portal/package.json)
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.22.0",
    "axios": "^1.6.7",
    "@tanstack/react-query": "^5.20.0",
    "zustand": "^4.5.0",
    "recharts": "^2.12.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "vite": "^5.1.0",
    "@vitejs/plugin-react": "^4.2.1",
    "tailwindcss": "^3.4.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.35",
    "@types/react": "^18.2.55",
    "@types/react-dom": "^18.2.19"
  }
}
```

---

## PHASE 8 — Testing

Create `server/tests/test_admin_portal.py`:

```python
# Tests to include:
# 1. test_login_wrong_email_rejected       — non-admin email returns 403
# 2. test_login_admin_otp_flow             — full login+OTP flow returns tokens
# 3. test_portal_route_without_token_401   — unauthenticated requests rejected
# 4. test_portal_route_wrong_role_403      — non-admin JWT rejected
# 5. test_create_user_sends_invite         — POST /users creates row + invite_token
# 6. test_delete_user_soft_deletes         — DELETE sets deleted_at, not hard delete
# 7. test_system_vitals_returns_metrics    — GET /system-vitals returns cpu/mem/disk
# 8. test_manual_trigger_queues_task       — POST /trigger returns task_id
```

Run with: `pytest server/tests/test_admin_portal.py -v`

---

## EXECUTION ORDER

Execute phases in strict sequence. Do not start the next phase until the current one is verified:

```
Phase 0 → Audit codebase, report findings
Phase 1 → Backend endpoints + migration (run: alembic upgrade head)
Phase 2 → Scaffold React app (npm create vite@latest portal -- --template react-ts)
Phase 3 → Apply design system (tailwind.config.ts + global CSS vars)
Phase 4 → Build all 7 pages
Phase 5 → Security layer (frontend guards + backend middleware)
Phase 6 → Nginx config append + vite.config.ts base path
Phase 7 → Verify all deps installed (pip + npm)
Phase 8 → Run pytest suite, fix any failures
```

**Final verification checklist:**
- [ ] `admin@mezzofy.com` can log in with Email+Password → OTP → Dashboard
- [ ] No other email can access any `/api/admin-portal/*` route
- [ ] Agent office pixel art renders with correct agents (Finance, Sales, Marketing, Support, HR, Manager)
- [ ] Busy agents show animated speech bubble
- [ ] LLM fuel gauges show warning colours at 80%/95% thresholds
- [ ] Create user → invite email sent via Outlook
- [ ] Manual task trigger enqueues Celery task
- [ ] All actions logged in audit_log with source="admin_portal"
- [ ] Existing FastAPI routes unmodified, services not restarted
