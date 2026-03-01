# Build Plan: mz-ai-assistant Server v1.0
**Created:** 2026-02-27
**Created by:** Lead Agent
**Project:** `C:\Mezzofy\mz-ai-assistant`
**Status document:** `mz-ai-assistant/docs/STATUS-mz-ai-assistant-20260227.md`

---

## Overview

Build the complete FastAPI server for `mz-ai-assistant` from scratch. The React Native mobile app (`APP/`) is a finished UI prototype with all responses mocked — this plan replaces those mocks with real API calls across 10 sequential phases.

**Total estimated sessions: 23–26**

---

## Project Paths (Absolute)

```
Root:          C:\Mezzofy\mz-ai-assistant\
App (mobile):  C:\Mezzofy\mz-ai-assistant\APP\
Server:        C:\Mezzofy\mz-ai-assistant\server\        ← BUILD TARGET
Spec files:    C:\Mezzofy\mz-ai-assistant\*.md
Status doc:    C:\Mezzofy\mz-ai-assistant\docs\STATUS-mz-ai-assistant-20260227.md
```

---

## Server Directory Target Structure

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry + startup + shutdown
│   ├── gateway.py                 # Request validation + auth check + rate limit
│   ├── router.py                  # Intent detection → agent routing
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py                # POST /auth/login, /auth/refresh, /auth/logout
│   │   ├── chat.py                # POST /chat/send, /chat/send-media, /chat/send-url,
│   │   │                          #   GET /chat/history, WS /chat/ws
│   │   ├── files.py               # GET /files/{id}, POST /files/upload
│   │   └── admin.py               # GET/POST/PUT/DELETE /admin/users, GET /admin/usage
│   │
│   ├── input/
│   │   ├── __init__.py
│   │   ├── input_router.py        # Detect content type → dispatch to handler
│   │   ├── text_handler.py        # Plain text passthrough
│   │   ├── image_handler.py       # Vision analysis, OCR (Tesseract + Claude Vision)
│   │   ├── video_handler.py       # Frame extraction + audio transcription
│   │   ├── camera_handler.py      # Live camera frames via WebSocket
│   │   ├── speech_handler.py      # Live STT via WebSocket (Whisper streaming)
│   │   ├── audio_handler.py       # Audio file → transcription (Whisper)
│   │   ├── file_handler.py        # PDF/DOCX/PPTX/CSV text extraction
│   │   └── url_handler.py         # Playwright fetch + BeautifulSoup scrape
│   │
│   ├── output/
│   │   ├── __init__.py
│   │   ├── output_formatter.py    # Format LLM response for mobile app
│   │   └── stream_handler.py      # SSE / WebSocket streaming output
│   │
│   ├── context/
│   │   ├── __init__.py
│   │   ├── session_manager.py     # Conversation history (PostgreSQL)
│   │   └── artifact_manager.py    # Generated file storage (EBS / S3)
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── anthropic_client.py    # Claude API client (tool use, vision, streaming)
│   │   ├── kimi_client.py         # Kimi (Moonshot) API client
│   │   └── llm_manager.py         # Language detection → route to Claude or Kimi; failover
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py          # Abstract agent: run() → tool loop (max 5 iter)
│   │   ├── sales_agent.py         # CRM pipeline, LinkedIn outreach, proposals
│   │   ├── marketing_agent.py     # Campaigns, content, social media
│   │   ├── operations_agent.py    # Scheduling, document automation, vendor comms
│   │   ├── finance_agent.py       # Reports, invoices, budgets
│   │   └── management_agent.py    # KPIs, cross-dept insights, board reports
│   │
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── presentation_skill.yaml + presentation_skill.py
│   │   ├── email_skill.yaml + email_skill.py
│   │   ├── linkedin_skill.yaml + linkedin_skill.py
│   │   ├── data_analysis_skill.yaml + data_analysis_skill.py
│   │   ├── document_skill.yaml + document_skill.py
│   │   ├── scheduling_skill.yaml + scheduling_skill.py
│   │   └── reporting_skill.yaml + reporting_skill.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── communication/
│   │   │   ├── outlook_ops.py     # send_email, list_emails, create_draft, reply
│   │   │   ├── teams_ops.py       # post_message, create_meeting, get_messages
│   │   │   └── push_ops.py        # send_push_notification, schedule_push
│   │   ├── document/
│   │   │   ├── pdf_ops.py         # create_pdf, merge_pdfs, extract_text_from_pdf
│   │   │   ├── pptx_ops.py        # create_presentation, add_slide, export_pdf
│   │   │   ├── docx_ops.py        # create_document, append_section, export_pdf
│   │   │   └── csv_ops.py         # create_csv, append_rows, read_csv
│   │   ├── media/
│   │   │   ├── image_ops.py       # ocr_image, analyze_image, compress_image
│   │   │   ├── video_ops.py       # extract_frames, transcribe_video, compress_video
│   │   │   ├── audio_ops.py       # transcribe_audio, noise_reduce, detect_language
│   │   │   └── speech_ops.py      # stream_transcription (WebSocket Whisper)
│   │   ├── web/
│   │   │   ├── browser_ops.py     # fetch_url, take_screenshot, fill_form (Playwright)
│   │   │   ├── scraping_ops.py    # scrape_text, extract_links, parse_table
│   │   │   └── linkedin_ops.py    # search_companies, get_profile, send_connection_request
│   │   └── database/
│   │       ├── db_ops.py          # execute_query, bulk_insert, get_schema (read-only)
│   │       ├── crm_ops.py         # create_lead, update_lead, search_leads (dept-scoped)
│   │       └── data_ops.py        # aggregate_by_dept, get_kpi_metrics, export_to_csv
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── auth.py                # JWT creation, validation, refresh token logic
│   │   ├── dependencies.py        # FastAPI Depends: get_current_user, require_role
│   │   ├── rbac.py                # Role-based access control matrix
│   │   ├── rate_limiter.py        # Redis sliding window rate limiter
│   │   ├── audit.py               # Audit log writer → PostgreSQL audit_log table
│   │   └── database.py            # SQLAlchemy engine, session factory, base model
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py          # Celery app init (Redis broker + backend)
│   │   ├── tasks.py               # Background tasks: process_media, run_report, etc.
│   │   ├── beat_schedule.py       # 5 Celery Beat schedules
│   │   └── webhook_tasks.py       # Async webhook event processors
│   │
│   └── webhooks/
│       ├── __init__.py
│       ├── webhooks.py            # POST /webhooks/mezzofy, /webhooks/generic
│       └── scheduler.py           # CRUD /scheduler/jobs API
│
├── scripts/
│   ├── migrate.py                 # CREATE TABLE for all 9 tables
│   ├── seed.py                    # Insert default users + roles
│   └── test.py                    # Connection tests: PostgreSQL + Redis
│
├── config/
│   ├── config.example.yaml        # All config keys (no real values)
│   ├── roles.yaml                 # 10 RBAC roles with permissions
│   └── nginx.conf                 # Nginx SSL termination + proxy config
│
├── requirements.txt               # All Python dependencies (from CONFIG.md)
└── setup.sh                       # Full EC2 setup script (apt, pip, systemd, etc.)
```

---

## Phase 0: Server Scaffold + DB Schema
**Agent:** Infra
**Sessions:** 2
**Depends on:** Nothing (first phase)
**Spec files to read first:** `INFRASTRUCTURE.md`, `CONFIG.md`, `MEMORY.md`

### Session 0-A: Directory Scaffold + Config Files

**Goal:** Create the complete server directory tree and all non-Python config files.

**Deliverables:**
```
server/
├── requirements.txt               ← All packages from CONFIG.md
├── setup.sh                       ← EC2 bootstrap script
├── config/
│   ├── config.example.yaml        ← All config keys with placeholder values
│   ├── roles.yaml                 ← 10 RBAC roles (from SECURITY.md)
│   └── nginx.conf                 ← Nginx SSL proxy config
├── app/                           ← All __init__.py stubs + placeholder files
│   ├── __init__.py
│   ├── main.py                    ← Stub (Phase 1 fills this)
│   ├── api/, input/, output/, context/, llm/, agents/, skills/, tools/, core/, tasks/, webhooks/
│   └── (all __init__.py stubs)
└── scripts/
    └── test.py                    ← PostgreSQL + Redis connection test
```

**What goes in each file:**
- `requirements.txt`: Match exactly what CONFIG.md specifies — fastapi, uvicorn, sqlalchemy, psycopg2-binary, redis, celery, anthropic, openai (for Kimi), python-jose, passlib, python-multipart, playwright, pytesseract, pdfplumber, python-pptx, python-docx, whisper, httpx, beautifulsoup4, pydantic, python-dotenv, boto3, pillow, moviepy, pytest, pytest-asyncio, httpx (test client)
- `config.example.yaml`: Keys for database_url, redis_url, secret_key, anthropic_api_key, moonshot_api_key (Kimi), ms_graph_client_id, ms_graph_client_secret, ms_graph_tenant_id, allowed_origins, artifact_storage_path, s3_bucket (optional), log_level
- `roles.yaml`: All 10 roles from SECURITY.md with their permission arrays
- `nginx.conf`: Upstream to 127.0.0.1:8000 (uvicorn), SSL termination, WebSocket upgrade headers, /data/ static file serving
- `setup.sh`: apt install python3.11, postgresql-15, redis-server, nginx, tesseract-ocr, ffmpeg; pip install -r requirements.txt; playwright install chromium; systemd service files for FastAPI + Celery worker + Celery Beat

**Session 0-A quality check before ending:** All directories exist; all `__init__.py` files exist; `requirements.txt` has all packages; `roles.yaml` has all 10 roles.

### Session 0-B: Database Schema + Scripts

**Goal:** Create `migrate.py` (9 tables), `seed.py` (default users), and verify with `test.py`.

**The 9 PostgreSQL tables (from MEMORY.md + INFRASTRUCTURE.md):**

```sql
-- 1. users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    department VARCHAR(100) NOT NULL,
    role VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- 2. conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    content_type VARCHAR(50) DEFAULT 'text',
    tool_results JSONB,
    agent_used VARCHAR(100),
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conversations_user_session ON conversations(user_id, session_id);
CREATE INDEX idx_conversations_created ON conversations(created_at);

-- 3. sales_leads
CREATE TABLE sales_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    industry VARCHAR(100),
    location VARCHAR(255),
    source VARCHAR(50) CHECK (source IN ('linkedin', 'website', 'referral', 'event', 'manual')),
    status VARCHAR(50) DEFAULT 'new' CHECK (status IN ('new','contacted','qualified','proposal','closed_won','closed_lost')),
    assigned_to UUID REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_contacted TIMESTAMPTZ,
    follow_up_date TIMESTAMPTZ
);
CREATE INDEX idx_leads_assigned_to ON sales_leads(assigned_to);
CREATE INDEX idx_leads_status ON sales_leads(status);

-- 4. artifacts
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255),
    file_name VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_size_bytes BIGINT,
    download_url VARCHAR(1000),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_artifacts_user ON artifacts(user_id);

-- 5. audit_log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(255) NOT NULL,
    resource VARCHAR(255),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_created ON audit_log(created_at);

-- 6. llm_usage
CREATE TABLE llm_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    session_id VARCHAR(255),
    model VARCHAR(100) NOT NULL,
    department VARCHAR(100),
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(10, 6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_llm_usage_user ON llm_usage(user_id);
CREATE INDEX idx_llm_usage_dept ON llm_usage(department);

-- 7. email_log
CREATE TABLE email_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    recipient_email VARCHAR(255) NOT NULL,
    subject VARCHAR(500),
    status VARCHAR(50) DEFAULT 'sent' CHECK (status IN ('sent','failed','draft')),
    ms_graph_message_id VARCHAR(500),
    sent_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_email_log_user ON email_log(user_id);

-- 8. scheduled_jobs
CREATE TABLE scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    cron_expression VARCHAR(100) NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    task_params JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. webhook_events
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(100) NOT NULL,
    event_type VARCHAR(100),
    payload JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'received' CHECK (status IN ('received','processing','processed','failed')),
    celery_task_id VARCHAR(255),
    processed_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_webhook_status ON webhook_events(status);
```

**seed.py:** Insert 1 admin user per department (5 departments × 2 roles = 10 users). Use `passlib` to hash passwords. Read from `config.yaml` or env vars for default password.

**test.py:** Test PostgreSQL connection (SELECT 1), test Redis connection (PING), test that all 9 tables exist (SELECT table_name FROM information_schema.tables WHERE table_schema='public'), print PASS/FAIL for each.

**Phase 0 Quality Gate (Lead reviews):**
- [ ] `python server/scripts/migrate.py` runs without errors
- [ ] `python server/scripts/test.py` prints PASS for PostgreSQL, Redis, and all 9 tables
- [ ] `roles.yaml` contains all 10 roles from SECURITY.md
- [ ] `requirements.txt` contains all packages from CONFIG.md
- [ ] `setup.sh` is executable and has all installation steps
- [ ] All `__init__.py` stubs exist in every subdirectory

---

## Phase 1: Auth + Security Layer
**Agent:** Backend
**Sessions:** 2
**Depends on:** Phase 0 complete + quality gate PASS
**Spec files to read first:** `SECURITY.md`, `CONFIG.md`, `APP.md`

### Session 1-A: Core Auth + Database

**Deliverables:**
- `app/core/database.py` — SQLAlchemy async engine, session factory, Base declarative model
- `app/core/auth.py` — JWT access token (15min) + refresh token (7d) creation and validation using `python-jose`; decode and verify; `HS256` algorithm
- `app/core/dependencies.py` — FastAPI Depends functions: `get_db()`, `get_current_user()`, `require_role(roles: list[str])`
- `app/core/rbac.py` — RBAC permission matrix loaded from `roles.yaml`; `check_permission(role, action, resource)` function
- `app/api/auth.py` — Three endpoints:
  - `POST /auth/login` — verify email+password, return `{access_token, refresh_token, user_info}`
  - `POST /auth/refresh` — accept refresh token, return new access token
  - `POST /auth/logout` — blacklist refresh token in Redis

### Session 1-B: Rate Limiting + Audit + Main App

**Deliverables:**
- `app/core/rate_limiter.py` — Redis sliding window: 60 req/min per user (chat), 10 req/min per IP (auth). FastAPI middleware + per-route override.
- `app/core/audit.py` — `log_action(user_id, action, resource, details, ip, success)` → INSERT into `audit_log` table asynchronously
- `app/main.py` — FastAPI app init: CORS (allowed_origins from config), include all routers (`auth`, `chat`, `files`, `admin`, `webhooks`, `scheduler`), startup event (test DB connection, test Redis), shutdown event, health check `GET /health`
- `app/gateway.py` — Middleware that runs on every `/chat/*` request: extract JWT from `Authorization: Bearer`, validate, load user, check rate limit, call audit log, attach `request.state.user`

**Phase 1 Quality Gate (Lead reviews):**
- [ ] `POST /auth/login` with valid credentials returns `{access_token, refresh_token, user_info}`
- [ ] `POST /auth/login` with wrong password returns 401
- [ ] `GET /chat/history` without token returns 401
- [ ] `GET /admin/users` with sales role returns 403 (wrong role)
- [ ] `POST /auth/login` 11 times in 1 minute returns 429 on the 11th
- [ ] `GET /health` returns `{status: "ok"}`

---

## Phase 2: Communication + Document Tools
**Agent:** Backend
**Sessions:** 2
**Depends on:** Phase 1 complete + quality gate PASS
**Spec files to read first:** `TOOLS.md` (communication section + document section)
**Note:** Phase 2 and Phase 3 can run in parallel (independent directories)

### Session 2-A: MS Graph Communication Tools

**Deliverables:**
- `app/tools/communication/outlook_ops.py`:
  - `send_email(to, subject, body, cc=None, attachments=None)` — via MS Graph `POST /me/sendMail`
  - `list_emails(folder='inbox', limit=20, unread_only=False)` — via MS Graph `GET /me/messages`
  - `create_draft(to, subject, body)` — via MS Graph `POST /me/messages`
  - `reply_email(message_id, body)` — via MS Graph `POST /me/messages/{id}/reply`
  - Log all sends to `email_log` table
- `app/tools/communication/teams_ops.py`:
  - `post_message(channel_id, content)` — via MS Graph `POST /teams/{id}/channels/{id}/messages`
  - `create_meeting(subject, attendees, start, end, body=None)` — via MS Graph Calendar API
  - `get_messages(channel_id, limit=20)` — via MS Graph
- `app/tools/communication/push_ops.py`:
  - `send_push_notification(user_id, title, body, data=None)` — Firebase FCM or APNs
  - `schedule_push(user_id, title, body, send_at)` — enqueue Celery task with eta

### Session 2-B: Document Generation Tools

**Deliverables:**
- `app/tools/document/pdf_ops.py`:
  - `create_pdf(title, sections: list[dict], output_path)` — using `reportlab` or `weasyprint`
  - `merge_pdfs(pdf_paths: list[str], output_path)` — using `pypdf2` or `pdfplumber`
  - `extract_text_from_pdf(file_path)` — using `pdfplumber`
- `app/tools/document/pptx_ops.py`:
  - `create_presentation(title, slides: list[dict], template=None, output_path)` — using `python-pptx`
  - `add_slide(pptx_path, slide_data: dict)` — append slide to existing PPTX
  - `export_pdf(pptx_path, output_path)` — convert PPTX → PDF via LibreOffice headless
- `app/tools/document/docx_ops.py`:
  - `create_document(title, sections: list[dict], output_path)` — using `python-docx`
  - `append_section(docx_path, heading, content)` — add section to existing DOCX
  - `export_pdf(docx_path, output_path)` — convert DOCX → PDF via LibreOffice headless
- `app/tools/document/csv_ops.py`:
  - `create_csv(headers: list, rows: list[list], output_path)` — using stdlib `csv`
  - `append_rows(csv_path, rows: list[list])` — append rows to existing CSV
  - `read_csv(file_path, limit=1000)` → returns `list[dict]`

All document tools must call `artifact_manager.store()` after creating a file and return the `download_url`.

**Phase 2 Quality Gate (Lead reviews):**
- [ ] `outlook_send_email` to a test address via MS Graph → 200 response, email received, row in `email_log`
- [ ] `create_pdf` produces a valid, openable PDF file
- [ ] `create_presentation` produces a valid PPTX with correct slide content
- [ ] `create_document` produces a valid DOCX
- [ ] `create_csv` produces a valid CSV
- [ ] Artifact stored in DB after each document creation

---

## Phase 3: Media + Web + Database Tools
**Agent:** Backend
**Sessions:** 2
**Depends on:** Phase 1 complete + quality gate PASS
**Spec files to read first:** `TOOLS.md` (media section, web section, database section)
**Note:** Runs in parallel with Phase 2 (independent directories)

### Session 3-A: Media Processing Tools

**Deliverables:**
- `app/tools/media/image_ops.py`:
  - `ocr_image(file_path)` → extracted text string — using `pytesseract`
  - `analyze_image(file_path, prompt)` → description string — using Claude Vision API
  - `compress_image(file_path, quality=85, max_width=1920)` → compressed file path — using `Pillow`
- `app/tools/media/video_ops.py`:
  - `extract_frames(video_path, interval_seconds=5)` → list of frame paths — using `moviepy` or `ffmpeg`
  - `transcribe_video(video_path)` → transcript string — extract audio → Whisper
  - `compress_video(video_path, target_mb=50)` → compressed file path — using `ffmpeg`
- `app/tools/media/audio_ops.py`:
  - `transcribe_audio(file_path, language=None)` → transcript string — using `openai-whisper` (local) or OpenAI Whisper API
  - `detect_language(file_path)` → language code (e.g., 'zh', 'en') — using `whisper` model
  - `noise_reduce(file_path)` → cleaned audio path — using `noisereduce` library
- `app/tools/media/speech_ops.py`:
  - `stream_transcription(websocket, user_id)` — WebSocket handler; receive audio chunks, accumulate, send to Whisper, stream back text tokens

### Session 3-B: Web Scraping + Database + CRM Tools

**Deliverables:**
- `app/tools/web/browser_ops.py`:
  - `fetch_url(url, wait_for=None)` → page HTML string — using Playwright async
  - `take_screenshot(url, output_path)` → screenshot file path
  - `fill_form(url, form_data: dict, submit=True)` → response HTML
- `app/tools/web/scraping_ops.py`:
  - `scrape_text(html_or_url)` → cleaned text — using BeautifulSoup
  - `extract_links(html_or_url, filter_pattern=None)` → list of URLs
  - `parse_table(html_or_url, table_index=0)` → list of dicts (headers as keys)
- `app/tools/web/linkedin_ops.py`:
  - `search_companies(query, location=None, industry=None, limit=10)` → list of company dicts — Playwright scraping (no official API)
  - `get_profile(profile_url)` → profile dict (name, title, company, bio)
  - `send_connection_request(profile_url, message)` → success bool
- `app/tools/database/db_ops.py`:
  - `execute_query(sql, params=None)` → list of dicts — READ ONLY (SELECT only; reject INSERT/UPDATE/DELETE)
  - `bulk_insert(table, rows: list[dict])` → row count — only for approved tables
  - `get_schema(table_name=None)` → schema dict
- `app/tools/database/crm_ops.py`:
  - `create_lead(company_name, contact_name, contact_email, ...)` → lead dict — auto-sets `assigned_to = current_user`
  - `update_lead(lead_id, updates: dict)` → updated lead — users can only update their own leads (management can update any)
  - `search_leads(query, status=None, assigned_to=None)` → list of leads — scoped by department (sales sees all sales leads; others see only their own)
  - `get_lead(lead_id)` → lead dict — scope check
- `app/tools/database/data_ops.py`:
  - `aggregate_by_dept(metric, period='month')` → dict of dept → value — management only
  - `get_kpi_metrics(dept, period='month')` → KPI dict
  - `export_to_csv(query_or_table, filters=None, output_path=None)` → CSV file path + download URL

**Phase 3 Quality Gate (Lead reviews):**
- [ ] `ocr_image` on a photo of text returns the text
- [ ] `transcribe_audio` on a test WAV file returns transcript
- [ ] `scrape_text` on a URL returns readable text content
- [ ] `create_lead` inserts row into DB with `assigned_to = current_user`
- [ ] `search_leads` for a non-sales user only returns their own leads

---

## Phase 4: LLM Layer + Skills + Agents
**Agent:** Backend
**Sessions:** 3
**Depends on:** Phase 2 AND Phase 3 both complete + quality gates PASS
**Spec files to read first:** `LLM.md`, `AGENTS.md`, `SKILLS.md`

### Session 4-A: LLM Clients + Manager

**Deliverables:**
- `app/llm/anthropic_client.py`:
  - `chat(messages, tools=None, system=None, max_tokens=4096, stream=False)` → Claude response or stream
  - `vision(image_path, prompt)` → Claude Vision response
  - `with_tools(messages, tool_definitions, system=None)` → Claude tool-use response (stop reason + tool calls)
  - Use `claude-sonnet-4-6` as default model (from LLM.md)
  - Handle `anthropic.RateLimitError` → retry with exponential backoff (3 attempts)
  - Log tokens to `llm_usage` table
- `app/llm/kimi_client.py`:
  - `chat(messages, system=None, max_tokens=4096)` → Kimi response
  - Uses Moonshot AI API (`moonshot-v1-128k` model)
  - Same interface as `anthropic_client` for drop-in substitution
  - Log tokens to `llm_usage` table
- `app/llm/llm_manager.py`:
  - `detect_language(text)` → 'zh' or 'en' (or other)
  - `route(messages, tools=None, system=None, stream=False, force_model=None)` → response
    - If language == 'zh' → use Kimi
    - Otherwise → use Claude
    - If primary fails → failover to the other
    - Log routing decision to audit_log

### Session 4-B: Skills

**Deliverables (7 skills — each has a YAML definition + Python executor):**

- `presentation_skill`: Given a topic + data, orchestrate: gather data (data_ops) → structure content → create_presentation (pptx_ops) → store artifact → return download_url
- `email_skill`: Given recipients + intent, orchestrate: draft email body (LLM) → send_email (outlook_ops) → log to email_log → return confirmation
- `linkedin_skill`: Given target criteria, orchestrate: search_companies → get_profile for each → filter → return list of prospects
- `data_analysis_skill`: Given a question + data source, orchestrate: execute_query or read_csv → LLM analysis → return insight text + optional chart data
- `document_skill`: Given document type + content spec, orchestrate: structure content (LLM) → create_pdf or create_document → store artifact → return download_url
- `scheduling_skill`: Given meeting spec or reminder spec, orchestrate: create_meeting (teams_ops) or create scheduled_job → return confirmation
- `reporting_skill`: Given report type + period, orchestrate: get_kpi_metrics → aggregate_by_dept → create_pdf → store artifact → send via email_skill → return download_url

Each skill Python file has a `run(params: dict, user_id: str, session_id: str) → dict` function that calls the LLM tool loop.

### Session 4-C: Department Agents

**Deliverables:**
- `app/agents/base_agent.py`:
  - Abstract class with `run(user_message, context, user, session_id)` → response dict
  - Tool loop: call LLM → if tool_use stop reason → execute tool → append result → repeat (max 5 iterations)
  - `get_tools()` → abstract, returns list of tool definitions available to this agent
  - `get_system_prompt()` → abstract, returns agent-specific system prompt
  - `get_available_skills()` → abstract, returns list of skill names this agent can invoke

- `app/agents/sales_agent.py`:
  - Tools: all of `crm_ops`, `linkedin_ops`, `outlook_ops`, `pdf_ops`, `docx_ops`, `browser_ops`
  - Skills: `email_skill`, `linkedin_skill`, `presentation_skill`, `document_skill`
  - System prompt: focused on sales pipeline, lead generation, proposal creation, follow-ups
  - Department scope: only accesses sales leads, sales KPIs

- `app/agents/marketing_agent.py`:
  - Tools: `scraping_ops`, `browser_ops`, `pptx_ops`, `csv_ops`, `data_ops`
  - Skills: `presentation_skill`, `data_analysis_skill`, `document_skill`
  - System prompt: focused on campaigns, content, market analysis, competitor monitoring

- `app/agents/operations_agent.py`:
  - Tools: `teams_ops`, `pdf_ops`, `docx_ops`, `csv_ops`, `db_ops`, `push_ops`
  - Skills: `scheduling_skill`, `document_skill`, `email_skill`
  - System prompt: focused on scheduling, vendor communications, process documentation

- `app/agents/finance_agent.py`:
  - Tools: `data_ops`, `db_ops`, `pdf_ops`, `csv_ops`, `outlook_ops`
  - Skills: `reporting_skill`, `data_analysis_skill`, `document_skill`
  - System prompt: focused on financial reports, invoices, budget tracking, cost analysis
  - Restricted: cannot modify sales leads or send push notifications

- `app/agents/management_agent.py`:
  - Tools: ALL tools (no restrictions)
  - Skills: ALL skills
  - System prompt: focused on cross-departmental KPIs, board reports, strategic insights
  - Access: can see all departments' data (no department scoping)

**Phase 4 Quality Gate (Lead reviews):**
- [ ] LLM Manager routes Chinese text → Kimi; English text → Claude
- [ ] If Claude fails → LLM Manager falls back to Kimi
- [ ] Tool loop in base_agent stops at max 5 iterations
- [ ] Sales agent calls `create_lead` → lead appears in DB
- [ ] Management agent can call `aggregate_by_dept` → returns all departments
- [ ] Sales agent CANNOT call `aggregate_by_dept` (wrong role) → tool returns 403

---

## Phase 5: API Endpoints + Core App Logic
**Agent:** Backend
**Sessions:** 3
**Depends on:** Phase 4 complete + quality gate PASS
**Spec files to read first:** `APP.md` (gateway, router, input, output, context, endpoints sections)

### Session 5-A: Input Pipeline + Context Layer

**Deliverables:**
- `app/input/input_router.py`: Detect content type from `content_type` header or file extension → dispatch to correct handler → return `{processed_text, metadata}`
- `app/input/text_handler.py`: Pass through raw text; detect language
- `app/input/image_handler.py`: Save upload → call `ocr_image` + `analyze_image` → return extracted text + description
- `app/input/audio_handler.py`: Save upload → call `transcribe_audio` → return transcript
- `app/input/file_handler.py`: Save upload → detect type (PDF/DOCX/PPTX/CSV) → extract text using appropriate ops tool → return text content
- `app/input/url_handler.py`: Call `fetch_url` → `scrape_text` → return clean text
- `app/input/video_handler.py`: Save upload → call `transcribe_video` → return transcript + frame count
- `app/input/speech_handler.py`: WebSocket handler for streaming speech → call `stream_transcription` → stream back text
- `app/input/camera_handler.py`: WebSocket handler for camera frames → call `analyze_image` per frame → stream back descriptions
- `app/context/session_manager.py`: `add_interaction()`, `get_history(limit=20)`, `list_sessions()` — read MEMORY.md spec
- `app/context/artifact_manager.py`: `store()`, `get_artifact()`, `list_artifacts()` — read MEMORY.md spec

### Session 5-B: Router + Output + Chat API

**Deliverables:**
- `app/router.py`:
  - `detect_intent(text, user)` → department + intent tags
  - `route_to_agent(intent, user)` → correct agent instance
  - Rules from APP.md: sales keywords → sales_agent; marketing keywords → marketing_agent; etc.
  - Default: route to agent matching user's own department
- `app/output/output_formatter.py`:
  - `format_response(agent_response, artifacts)` → mobile-ready dict
  - Structure: `{message, artifacts: [{name, type, url, size}], actions: [...]}`
- `app/output/stream_handler.py`:
  - Server-Sent Events (SSE) streaming for LLM token-by-token output
  - WebSocket streaming for speech input → text output
- `app/api/chat.py`:
  - `POST /chat/send` — body: `{message, session_id?}` → full pipeline: input → route → agent → output → return response
  - `POST /chat/send-media` — multipart: file + optional text → input_router → agent → output
  - `POST /chat/send-url` — body: `{url, instruction?}` → url_handler → agent → output
  - `GET /chat/history?session_id=X&limit=20` — return conversation history
  - `WS /chat/ws` — WebSocket for streaming speech input + streaming text output

### Session 5-C: Files + Admin APIs

**Deliverables:**
- `app/api/files.py`:
  - `GET /files/{file_id}` — auth required; ownership check; return file stream with correct content-type
  - `POST /files/upload` — multipart upload; save to artifact storage; return `{file_id, download_url}`
- `app/api/admin.py` (management role only):
  - `GET /admin/users` — list all users with pagination
  - `POST /admin/users` — create new user (hashed password)
  - `PUT /admin/users/{id}` — update user (role, department, is_active)
  - `DELETE /admin/users/{id}` — soft delete (set is_active=False)
  - `GET /admin/usage?period=month&dept=sales` — aggregate LLM usage stats

**Phase 5 Quality Gate (Lead reviews):**
- [ ] `POST /chat/send {"message": "Draft a sales proposal for ABC Restaurant"}` → returns formatted response with agent tool calls visible
- [ ] `POST /chat/send-media` with a PDF upload → extracts PDF text, passes to agent, returns response
- [ ] `WS /chat/ws` accepts audio frames and returns streaming transcript
- [ ] `GET /chat/history` returns conversation history in correct format
- [ ] `GET /files/{id}` returns file stream; returns 403 if wrong user

---

## Phase 6: Celery Task Queue + Webhooks
**Agent:** Backend
**Sessions:** 2
**Depends on:** Phase 5 complete + quality gate PASS
**Spec files to read first:** `APP.md` (Celery section, webhooks section, scheduler section)

### Session 6-A: Celery App + Tasks + Beat Schedule

**Deliverables:**
- `app/tasks/celery_app.py`: Celery app init with Redis broker (`redis://localhost:6379/0`) and Redis backend (`redis://localhost:6379/1`); worker concurrency = 4
- `app/tasks/tasks.py`:
  - `process_media_async(file_path, user_id, session_id)` — async media processing (for large files)
  - `run_weekly_kpi_report(dept=None)` — calls `reporting_skill` for each department
  - `run_lead_followup_check()` — query leads with `follow_up_date <= today`; send reminder emails
  - `run_monthly_summary(dept)` — calls `reporting_skill` for monthly summary
  - `send_scheduled_push(user_id, title, body)` — sends push notification at scheduled time
- `app/tasks/beat_schedule.py`:
  ```python
  beat_schedule = {
      'weekly-kpi-report': {
          'task': 'app.tasks.tasks.run_weekly_kpi_report',
          'schedule': crontab(hour=8, minute=0, day_of_week='monday'),
      },
      'lead-followup-check': {
          'task': 'app.tasks.tasks.run_lead_followup_check',
          'schedule': crontab(hour=9, minute=0),  # daily 9am
      },
      'monthly-summary': {
          'task': 'app.tasks.tasks.run_monthly_summary',
          'schedule': crontab(hour=8, minute=30, day_of_month=1),  # 1st of month
      },
  }
  ```

### Session 6-B: Webhooks + Scheduler API

**Deliverables:**
- `app/tasks/webhook_tasks.py`:
  - `process_mezzofy_webhook(event_id, payload)` — handle Mezzofy product events (coupon redeemed, campaign activated, etc.) → update relevant records → notify relevant agent
  - `process_generic_webhook(event_id, payload, source)` — generic handler for any configured webhook source
- `app/webhooks/webhooks.py`:
  - `POST /webhooks/mezzofy` — validate HMAC signature → store in `webhook_events` → enqueue Celery task → return 200 immediately
  - `POST /webhooks/generic` — store → enqueue → return 200 immediately
  - HMAC secret from config; reject invalid signatures with 401
- `app/webhooks/scheduler.py`:
  - `POST /scheduler/jobs` — create new scheduled job (insert into `scheduled_jobs` table + add to Celery Beat dynamic schedule)
  - `GET /scheduler/jobs` — list user's scheduled jobs
  - `PUT /scheduler/jobs/{id}` — update schedule
  - `DELETE /scheduler/jobs/{id}` — deactivate (set `is_active=False` + remove from Beat)

**Phase 6 Quality Gate (Lead reviews):**
- [ ] `celery -A app.tasks.celery_app worker` starts without errors
- [ ] `celery -A app.tasks.celery_app beat` starts and shows schedule
- [ ] `POST /webhooks/mezzofy` with correct HMAC → 200, row in `webhook_events`, Celery task enqueued
- [ ] `POST /webhooks/mezzofy` with wrong HMAC → 401
- [ ] `POST /scheduler/jobs` creates job; appears in `GET /scheduler/jobs`

---

## Phase 7: Server Test Suite
**Agent:** Tester
**Sessions:** 2
**Depends on:** Phase 6 complete + quality gate PASS
**Spec files to read first:** `TESTING.md`

### Session 7-A: Auth + Workflow Tests

**Deliverables (pytest files in `server/tests/`):**
- `tests/test_auth.py`: Login success/fail, token refresh, logout, token expiry, RBAC deny, rate limit
- `tests/test_sales_workflow.py`: Login as sales user → send chat "find leads in F&B Singapore" → verify LinkedIn search called → verify lead created in DB → verify email drafted
- `tests/test_marketing_workflow.py`: Login as marketing user → send chat "analyze competitor pricing" → verify web scrape called → verify analysis response
- `tests/test_operations_workflow.py`: Login as ops user → send chat "schedule team meeting for Friday 3pm" → verify Teams meeting created
- `tests/test_finance_workflow.py`: Login as finance user → send chat "generate monthly P&L report" → verify PDF artifact created + download URL returned
- `tests/test_management_workflow.py`: Login as management user → send chat "show me this week's KPIs across all departments" → verify `aggregate_by_dept` called → verify all departments returned

### Session 7-B: Scheduler + Webhook + Security + LLM Tests

**Deliverables:**
- `tests/test_scheduler.py`: Create job → list jobs → update → delete; Beat fires test task
- `tests/test_webhooks.py`: Valid HMAC → 200; invalid HMAC → 401; Celery task enqueued; `webhook_events` row created
- `tests/test_security.py`: SQL injection in chat message → rejected; XSS in message → sanitized; oversized file upload → 413; expired token → 401; missing scope → 403
- `tests/test_llm.py`: Chinese message → routes to Kimi; English → Claude; Claude failure → falls back to Kimi; tool loop stops at 5 iterations
- `tests/conftest.py`: pytest fixtures — test DB, test Redis, authenticated test clients for each role

**Phase 7 Quality Gate (Lead reviews):**
- [ ] `pytest server/tests/ -v` shows >80% coverage
- [ ] All 5 department workflow tests PASS
- [ ] All security tests PASS
- [ ] LLM routing tests PASS (may use mocked LLM clients)

---

## Phase 8: Mobile API Integration
**Agent:** Mobile
**Sessions:** 3
**Depends on:** Phase 7 complete + quality gate PASS
**Spec files to read first:** `INFRASTRUCTURE.md` (mobile section), `APP.md` (API contracts section)

### Session 8-A: API Client + Auth Store

**Deliverables (all in `APP/src/`):**
- `services/api.ts`: Axios/fetch wrapper with base URL from config; auto-attach `Authorization: Bearer {token}` header; handle 401 → refresh token → retry; handle 429 → show rate limit UI
- `services/auth.ts`: `login(email, password)` → call `POST /auth/login` → store tokens in SecureStore; `logout()` → call `POST /auth/logout` → clear storage; `refreshToken()` → call `POST /auth/refresh`
- `services/websocket.ts`: WebSocket manager for `/chat/ws`; reconnect on disconnect; send audio chunks; receive streaming text tokens
- Update `stores/authStore.ts`: Replace mock login with `auth.ts` calls; persist token in SecureStore
- Update `stores/chatStore.ts`: Replace `DEMO_RESPONSES` with real `POST /chat/send` calls

### Session 8-B: Chat + Files + Media Screens

**Deliverables:**
- `services/chat.ts`: `sendMessage(text, sessionId)` → `POST /chat/send`; `sendMedia(file, text?, sessionId)` → `POST /chat/send-media`; `sendUrl(url, instruction?, sessionId)` → `POST /chat/send-url`; `getHistory(sessionId, limit)` → `GET /chat/history`
- `services/files.ts`: `uploadFile(uri, type)` → `POST /files/upload`; `downloadFile(fileId)` → `GET /files/{id}`; `listArtifacts()` → `GET /chat/history` (artifacts embedded in history)
- `services/media.ts`: Camera frame capture → WebSocket stream; voice recording → WebSocket stream or `POST /chat/send-media`
- Update `screens/ChatScreen.tsx`: Replace mock with `chat.ts` calls; show streaming response; handle attachment buttons (camera, voice, file picker) with real upload
- Update `screens/ChatHistoryScreen.tsx`: Replace mock with `GET /chat/history` sessions list
- Update `screens/FilesScreen.tsx`: Replace mock with `files.ts` artifact list + download

### Session 8-C: Settings + Dashboard + Error Handling

**Deliverables:**
- Update `screens/SettingsScreen.tsx`: Load real user profile from `GET /auth/me` (add this endpoint in Phase 5 if missed); update profile via `PUT /admin/users/{id}` for management
- Update `screens/DashboardScreen.tsx`: If user is management, load `GET /admin/usage` for usage stats; others see their own recent sessions
- `services/errorHandler.ts`: Map API errors to user-friendly messages; handle network offline state; retry logic
- `utils/tokenRefresh.ts`: Intercept 401 → refresh → retry original request (axios interceptor pattern)

**Phase 8 Quality Gate (implicit — Tester reviews in Phase 9):**
- App boots without errors
- Login with real credentials → JWT stored → dashboard loads
- Send "hello" text message → real LLM response appears in chat
- Upload a PDF → processing indicator → response referencing PDF content
- Voice message → transcript appears → LLM responds

---

## Phase 9: End-to-End Tests
**Agent:** Tester
**Sessions:** 1
**Depends on:** Phase 8 complete
**Spec files to read first:** `TESTING.md` (E2E section)

**Deliverables:**
- `tests/e2e/test_mobile_integration.py` or Detox/Maestro scripts:
  - Full login flow: enter credentials → JWT stored → chat screen loads
  - Text message workflow: type message → send → receive real response
  - File upload workflow: pick PDF → upload → get response mentioning file content
  - Chat history: send 3 messages → go to history screen → all 3 visible
  - Department routing: login as sales user → ask about leads → confirm sales_agent was invoked (check audit_log)

---

## Phase 10: Documentation
**Agent:** Docs
**Sessions:** 1
**Depends on:** Phase 9 complete
**Spec files to read first:** All spec files (for accuracy check)

**Deliverables:**
- `server/docs/openapi.yaml` or FastAPI auto-generated `/docs` export
- `server/docs/DEPLOYMENT.md`: Step-by-step EC2 setup using `setup.sh`; how to run migrations; how to start all services; how to configure nginx SSL (Let's Encrypt); environment variable checklist
- `server/docs/API.md`: All endpoints with request/response examples
- `mz-ai-assistant/docs/RN-mz-ai-assistant-v1.0.md`: Release notes for v1.0

---

## Agent Boot Instructions Per Phase

### Infra Agent (Phase 0)
```
Read CLAUDE.md
Read .claude/agents/infra.md
Read .claude/skills/infrastructure-engineer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md  ← THIS FILE
Read mz-ai-assistant/INFRASTRUCTURE.md
Read mz-ai-assistant/CONFIG.md
Read mz-ai-assistant/MEMORY.md
Read mz-ai-assistant/SECURITY.md
Working directory: C:\Mezzofy\mz-ai-assistant\
Goal: Execute Phase 0-A then Phase 0-B as described in this plan
```

### Backend Agent (Phase 1)
```
Read CLAUDE.md
Read .claude/agents/backend.md
Read .claude/skills/backend-developer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md  ← THIS FILE
Read mz-ai-assistant/SECURITY.md
Read mz-ai-assistant/CONFIG.md
Read mz-ai-assistant/APP.md
Working directory: C:\Mezzofy\mz-ai-assistant\server\
Goal: Execute Phase 1-A then Phase 1-B as described in this plan
```

### Backend Agent (Phase 2)
```
Read CLAUDE.md + .claude/agents/backend.md + .claude/skills/backend-developer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Read mz-ai-assistant/TOOLS.md  ← focus: communication + document sections
Goal: Execute Phase 2-A then Phase 2-B
```

### Backend Agent (Phase 3)
```
Read CLAUDE.md + .claude/agents/backend.md + .claude/skills/backend-developer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Read mz-ai-assistant/TOOLS.md  ← focus: media + web + database sections
Goal: Execute Phase 3-A then Phase 3-B
```

### Backend Agent (Phase 4)
```
Read CLAUDE.md + .claude/agents/backend.md + .claude/skills/backend-developer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Read mz-ai-assistant/LLM.md
Read mz-ai-assistant/AGENTS.md
Read mz-ai-assistant/SKILLS.md
Goal: Execute Phase 4-A, 4-B, 4-C
```

### Backend Agent (Phase 5)
```
Read CLAUDE.md + .claude/agents/backend.md + .claude/skills/backend-developer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Read mz-ai-assistant/APP.md  ← focus: gateway, router, input, output, context, endpoints
Goal: Execute Phase 5-A, 5-B, 5-C
```

### Backend Agent (Phase 6)
```
Read CLAUDE.md + .claude/agents/backend.md + .claude/skills/backend-developer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Read mz-ai-assistant/APP.md  ← focus: Celery, webhooks, scheduler sections
Goal: Execute Phase 6-A, 6-B
```

### Tester Agent (Phase 7)
```
Read CLAUDE.md + .claude/agents/tester.md + .claude/skills/test-automation-engineer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Read mz-ai-assistant/TESTING.md
Goal: Execute Phase 7-A, 7-B
```

### Mobile Agent (Phase 8)
```
Read CLAUDE.md + .claude/agents/mobile.md + .claude/skills/mobile-developer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Read mz-ai-assistant/INFRASTRUCTURE.md  ← mobile section
Read mz-ai-assistant/APP.md  ← API contracts section
Working directory: C:\Mezzofy\mz-ai-assistant\APP\
Goal: Execute Phase 8-A, 8-B, 8-C
```

### Tester Agent (Phase 9)
```
Read CLAUDE.md + .claude/agents/tester.md + .claude/skills/test-automation-engineer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Read mz-ai-assistant/TESTING.md
Goal: Execute Phase 9
```

### Docs Agent (Phase 10)
```
Read CLAUDE.md + .claude/agents/docs.md + .claude/skills/api-documenter.md + .claude/skills/technical-writer.md
Read .claude/coordination/plans/mz-ai-assistant-server-v1.0.md
Goal: Execute Phase 10
```

---

## Cross-Phase Notes

### RBAC Roles (10 roles from SECURITY.md — `roles.yaml` must contain all)
```
admin, management, sales_manager, sales_rep, marketing_manager, marketing_rep,
operations_manager, operations_rep, finance_manager, finance_rep
```

### Config Keys (all must be in `config.example.yaml`)
```yaml
database:
  url: postgresql+asyncpg://user:password@localhost:5432/mezzofy_ai

redis:
  url: redis://localhost:6379/0

security:
  secret_key: CHANGE_ME_IN_PRODUCTION
  algorithm: HS256
  access_token_expire_minutes: 15
  refresh_token_expire_days: 7

anthropic:
  api_key: sk-ant-...
  model: claude-sonnet-4-6

moonshot:
  api_key: sk-...
  model: moonshot-v1-128k

microsoft:
  client_id: ...
  client_secret: ...
  tenant_id: ...

storage:
  artifact_path: /data/artifacts
  s3_bucket: null  # set for production scaling

server:
  allowed_origins:
    - http://localhost:8081  # React Native Metro
    - https://yourdomain.com
  log_level: INFO

celery:
  broker_url: redis://localhost:6379/0
  result_backend: redis://localhost:6379/1
  worker_concurrency: 4
```

### Parallel Execution (Phase 2 + Phase 3)
When Phase 1 quality gate passes, Phase 2 and Phase 3 can begin in the same session (two terminal windows, two Backend Agent instances). Both work in independent directories (`tools/communication/`, `tools/document/` vs `tools/media/`, `tools/web/`, `tools/database/`) with no conflicts. Lead Agent reviews both quality gates together before allowing Phase 4 to start.

### Mobile App Mock Locations (Phase 8 reference)
The Mobile Agent should find and replace these patterns in `APP/`:
- `DEMO_RESPONSES` object literals → replace with real `api.ts` calls
- `setTimeout(() => {...}, N)` in store actions → replace with `await api.post(...)` calls
- Hardcoded user data in stores → replace with JWT-decoded user + profile API call
