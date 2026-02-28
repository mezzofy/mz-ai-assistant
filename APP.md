# APP.md — Core Server Application

**FastAPI server with REST/WebSocket API, request routing, webhook ingestion, task queue, scheduled jobs, and output generation.**

---

## Overview

```
/server/app
├── main.py                  # FastAPI entry point + startup
├── gateway.py               # Request processing + normalization
├── router.py                # Intent classification → agent selection
│
├── /api                     # REST + WebSocket endpoints
│   ├── auth.py              # POST /auth/login, /auth/refresh, /auth/logout
│   ├── chat.py              # POST /chat/send, GET /chat/history, WS /chat/ws
│   ├── files.py             # GET /files/{id}, GET /files/list
│   ├── webhooks.py          # POST /webhooks/{source} — external event ingestion
│   ├── scheduler.py         # GET/POST/DELETE /scheduler/jobs — manage scheduled jobs
│   └── admin.py             # User CRUD, role assignment
│
├── /input                   # Multi-modal input processors
│   ├── __init__.py
│   ├── input_router.py      # Detect input type → dispatch to handler
│   ├── text_handler.py      # Plain text / chat messages
│   ├── image_handler.py     # Image analysis, OCR, description
│   ├── video_handler.py     # Video analysis, frame extraction
│   ├── camera_handler.py    # Live camera stream processing
│   ├── speech_handler.py    # Live speech → real-time STT
│   ├── audio_handler.py     # Audio file → STT transcription
│   ├── file_handler.py      # PDF, DOCX, CSV, PPTX extraction
│   └── url_handler.py       # URL fetch, web scraping, content extraction
│
├── /llm                     # LLM clients (see LLM.md)
├── /output                  # Output generators
│   ├── pdf_output.py        # Financial statements, playbooks, reports
│   ├── pptx_output.py       # Sales pitch decks
│   ├── email_output.py      # Outlook email composition (via MS Graph)
│   ├── calendar_output.py   # Outlook calendar event creation
│   ├── teams_output.py      # MS Teams message posting
│   └── document_output.py   # DOCX, MD, CSV exports
│
└── /context                 # Context management
    ├── processor.py         # Combine tool results → final response
    ├── session_manager.py   # Conversation sessions (PostgreSQL)
    └── artifact_manager.py  # Generated file storage (EBS/S3)

/server/scheduler            # Task queue + scheduled jobs
├── celery_app.py            # Celery configuration + Redis broker
├── tasks.py                 # Background task definitions
├── beat_schedule.py         # Recurring job schedules (cron)
└── webhook_tasks.py         # Webhook-triggered async tasks
```

---

## FastAPI Entry Point (`main.py`)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Mezzofy AI Assistant API", version="1.0.0")

# CORS for mobile app
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Mount route groups
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(files_router, prefix="/files", tags=["files"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(scheduler_router, prefix="/scheduler", tags=["scheduler"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

# Startup: init DB pool, load agents, connect LLM clients, verify MS Graph
@app.on_event("startup")
async def startup():
    await init_database()
    await init_agents()
    await init_llm_clients()
    await init_ms_graph_client()
    await verify_celery_connection()
```

---

## API Endpoints

### Authentication (`/api/auth.py`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/auth/login` | Email + password → JWT token pair | Public |
| POST | `/auth/refresh` | Refresh token → new access token | Authenticated |
| POST | `/auth/logout` | Invalidate tokens | Authenticated |

Returns JWT containing: `user_id`, `department`, `role`, `permissions[]`

### Chat (`/api/chat.py`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/chat/send` | Send text message, get AI response | Authenticated |
| POST | `/chat/send-media` | Send message with image/video/audio/file attachment | Authenticated |
| POST | `/chat/send-url` | Send URL for scraping + analysis | Authenticated |
| GET | `/chat/history/{session_id}` | Get conversation history | Own sessions |
| GET | `/chat/sessions` | List user's chat sessions | Own sessions |
| WS | `/chat/ws` | WebSocket for real-time streaming + live speech/camera | Authenticated |

**POST `/chat/send` — Text message:**
```json
{
    "message": "Generate the latest financial statement and send to CEO",
    "session_id": "optional — creates new if omitted"
}
```

**POST `/chat/send-media` — Multi-modal message (multipart/form-data):**
```
message:       "What does this receipt show?"          (optional text)
session_id:    "sess_abc"                              (optional)
input_type:    "image"                                 (image|video|audio|file)
media_file:    <binary upload>                         (the actual file)
```

Supported `input_type` values and accepted formats:

| input_type | Accepted Formats | Max Size | Processing |
|-----------|-----------------|----------|------------|
| `image` | JPEG, PNG, HEIC, WebP | 20 MB | Vision analysis, OCR, description |
| `video` | MP4, MOV, AVI | 100 MB | Frame extraction, scene analysis, transcription |
| `audio` | MP3, WAV, M4A, OGG | 50 MB | Speech-to-text transcription |
| `file` | PDF, DOCX, PPTX, CSV, XLSX, TXT | 20 MB | Text extraction, parsing |

**POST `/chat/send-url` — URL scraping:**
```json
{
    "url": "https://example.com/about",
    "message": "Summarize this company and find contact info",
    "session_id": "sess_abc"
}
```

**WebSocket `/chat/ws` — Live streaming (speech + camera):**
```
Client connects: WS /chat/ws?token=<JWT>

Client sends:
  {"type": "speech_start"}                            → Begin live STT
  {"type": "speech_audio", "data": "<base64 chunk>"}  → Audio chunks
  {"type": "speech_end"}                              → End STT, process
  {"type": "camera_frame", "data": "<base64 jpeg>"}  → Live camera frame
  {"type": "text", "message": "..."}                  → Text message

Server sends:
  {"type": "transcript", "text": "partial text..."}   → Live STT feedback
  {"type": "status", "message": "Analyzing image..."}  → Progress update
  {"type": "task_progress", "task_id": "...", "progress": 60}  → Background task progress
  {"type": "complete", "response": {...}}              → Final response
```

**Response (all send endpoints):**
```json
{
    "session_id": "sess_abc123",
    "response": "Financial statement generated and emailed to CEO via Outlook.",
    "input_processed": {
        "type": "image",
        "description": "Photo of a receipt from ABC Restaurant",
        "extracted_text": "Total: $142.50..."
    },
    "artifacts": [
        {
            "id": "file_xyz",
            "type": "pdf",
            "name": "financial_statement_Q4_2025.pdf",
            "download_url": "/files/file_xyz"
        }
    ],
    "agent_used": "finance",
    "tools_used": ["database_query", "pdf_generator", "outlook_send_email"]
}
```

### Webhooks (`/api/webhooks.py`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| POST | `/webhooks/mezzofy` | Mezzofy product events (new customer, new order, etc.) | Webhook secret |
| POST | `/webhooks/teams` | MS Teams incoming events (mentions, messages) | MS verification |
| POST | `/webhooks/custom/{source}` | Custom webhook from any external service | Webhook secret |

**How webhooks work:**

```
External service → POST /webhooks/{source}
    │
    ├── 1. Validate webhook signature/secret
    ├── 2. Parse event payload
    ├── 3. Enqueue as Celery task (non-blocking)
    ├── 4. Return 200 OK immediately
    │
    └── Celery worker processes async:
        ├── Route to appropriate agent
        ├── Execute workflow
        └── Deliver output (Teams message, email, push notification)
```

**Mezzofy product webhook payload:**
```json
{
    "event": "customer_signed_up",
    "timestamp": "2026-02-26T10:00:00Z",
    "data": {
        "customer_id": "cust_abc",
        "company_name": "ABC Restaurant Group",
        "email": "info@abcrestaurant.sg",
        "plan": "enterprise",
        "country": "SG"
    },
    "signature": "hmac-sha256-signature"
}
```

**Supported Mezzofy events:**

| Event | Action |
|-------|--------|
| `customer_signed_up` | Create CRM lead → send welcome email → notify #sales in Teams |
| `customer_churned` | Alert management → create follow-up task → notify account manager |
| `order_completed` | Log revenue → update financial data → notify finance if large order |
| `support_ticket_created` | Route to Support Agent → auto-suggest solutions → notify #support Teams |
| `feature_released` | Trigger Marketing Agent → draft announcement content |

**MS Teams webhook payload:**
```json
{
    "type": "message",
    "from": {"id": "user_abc", "name": "John Tan"},
    "channelId": "msteams",
    "text": "@MezzofyAI generate a sales report for this quarter",
    "channelData": {
        "channel": {"id": "19:general@thread.tacv2"},
        "team": {"id": "team_xyz"}
    }
}
```

When someone @mentions the Mezzofy AI bot in Teams, the webhook receives the message and processes it through the same Gateway → Router → Agent pipeline, sending the response back to the Teams channel.

### Scheduler (`/api/scheduler.py`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/scheduler/jobs` | List all scheduled jobs (filtered by department) | Authenticated |
| POST | `/scheduler/jobs` | Create a new scheduled job | Manager+ roles |
| GET | `/scheduler/jobs/{id}` | Get job details + execution history | Authenticated |
| DELETE | `/scheduler/jobs/{id}` | Cancel a scheduled job | Job owner or admin |
| GET | `/scheduler/jobs/{id}/history` | Get past execution results | Authenticated |

**Create scheduled job:**
```json
{
    "name": "Weekly Sales Pipeline Report",
    "description": "Generate pipeline report and post to #sales Teams channel",
    "schedule": {
        "type": "cron",
        "cron": "0 9 * * 1"
    },
    "task": {
        "agent": "sales",
        "message": "Generate a sales pipeline report for last week with lead counts by status",
        "deliver_to": {
            "teams_channel": "sales",
            "email": ["sales-manager@mezzofy.com"]
        }
    },
    "created_by": "user_123",
    "department": "sales"
}
```

**Schedule types:**

| Type | Format | Example |
|------|--------|---------|
| `cron` | Standard cron expression | `0 9 * * 1` (Monday 9AM) |
| `interval` | Every N minutes/hours/days | `{"hours": 24}` |
| `once` | Specific datetime | `"2026-03-01T09:00:00+08:00"` |

### Files (`/api/files.py`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/files/{file_id}` | Download generated file | Owner or permitted |
| GET | `/files/list` | List user's generated files | Own files |
| POST | `/files/upload` | Upload attachment for AI processing | Authenticated |

### Admin (`/api/admin.py`)

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/admin/users` | List all users | Management only |
| POST | `/admin/users` | Create user + assign dept/role | Management only |
| PUT | `/admin/users/{id}` | Update user role/permissions | Management only |
| GET | `/admin/audit` | View audit logs | Management only |
| GET | `/admin/health` | System health dashboard (LLM, DB, Redis, Celery) | Admin only |

---

## Gateway (`gateway.py`)

Processes every incoming request before routing.

### Responsibilities

1. **Authenticate** — Verify JWT, extract user context (department, role, permissions)
2. **Normalize** — Convert request to standard internal format
3. **Enrich** — Add department context, user preferences, session history
4. **Log** — Record request in audit log
5. **Route** — Pass to Router for agent selection

### Standard Internal Format

Every request is normalized to:

```python
{
    "user_id": "user_123",
    "department": "sales",
    "role": "sales_rep",
    "permissions": ["sales_tools", "email_send", "crm_write"],
    "message": "Find leads in Singapore F&B industry",
    "input_type": "text",                # text | image | video | audio | speech | file | url | camera
    "media_content": None,               # Processed media data (when applicable)
    "extracted_text": None,              # Text extracted from media/file/URL
    "session_id": "sess_abc",
    "source": "mobile",                  # mobile | webhook | scheduler | teams
    "attachments": [],
    "conversation_history": [...]        # Last N messages from session
}
```

---

## Input Processing Pipeline (`/input/`)

All non-text inputs go through a processing pipeline before reaching the LLM.

### Input Router (`input_router.py`)

Detects input type and dispatches to the correct handler:

```
Incoming request
    │
    ├── POST /chat/send         →  text_handler
    ├── POST /chat/send-media   →  detect input_type:
    │       ├── image            →  image_handler
    │       ├── video            →  video_handler
    │       ├── audio            →  audio_handler
    │       └── file             →  file_handler
    ├── POST /chat/send-url     →  url_handler
    ├── WS speech_start          →  speech_handler
    └── WS camera_frame          →  camera_handler
```

Each handler returns the standard internal format with `media_content` and `extracted_text` populated for the LLM.

### Image Handler (`image_handler.py`)

Processes uploaded images for analysis:

| Step | Action | Library |
|------|--------|---------|
| 1 | Validate format + size | python-magic, Pillow |
| 2 | Resize if > 2048px | Pillow |
| 3 | OCR text extraction | Tesseract (pytesseract) |
| 4 | Vision analysis | Claude Vision API |
| 5 | Extract EXIF metadata | Pillow |
| 6 | Return combined results | Gateway |

### Video Handler (`video_handler.py`)

Processes uploaded videos — **enqueued as Celery task for long videos:**

| Step | Action | Library |
|------|--------|---------|
| 1 | Validate format + size + duration | python-magic, OpenCV |
| 2 | Extract key frames (1 per 5 seconds) | OpenCV |
| 3 | Separate audio track | FFmpeg / MoviePy |
| 4 | Transcribe audio (Whisper) | openai-whisper |
| 5 | Analyze key frames (Vision API) | Claude Vision |
| 6 | Return transcript + scene descriptions | Gateway |

Videos longer than 60 seconds are processed as background Celery tasks with progress updates sent via WebSocket.

### Camera Handler (`camera_handler.py`)

Handles live camera frames from mobile app via WebSocket:

```
Mobile sends: {"type": "camera_frame", "data": "<base64 JPEG>"}
Server: Rate limit to 1 fps → Vision API → description
Server returns: {"type": "camera_analysis", "description": "Business card: John Tan, CEO..."}
```

### Speech Handler (`speech_handler.py`)

Handles live speech-to-text via WebSocket streaming:

```
Mobile sends: {"type": "speech_start"}
Mobile sends: {"type": "speech_audio", "data": "<base64 audio chunk>"}  (continuous)
Server sends: {"type": "transcript", "text": "Generate the latest...", "is_final": false}
Mobile sends: {"type": "speech_end"}
Server sends: {"type": "transcript", "text": "Generate the latest financial statement", "is_final": true}
Server processes final transcript as a normal text message
```

Supported languages: English, Chinese (Mandarin), Malay — configurable per user.

### Audio Handler (`audio_handler.py`)

Processes uploaded audio files (pre-recorded, not live):

| Step | Action | Library |
|------|--------|---------|
| 1 | Validate format + size + duration | python-magic, pydub |
| 2 | Convert to WAV if needed | FFmpeg / pydub |
| 3 | Transcribe full audio | Whisper |
| 4 | Detect language | Whisper auto-detect |
| 5 | Process transcript as text | Gateway |

### File Handler (`file_handler.py`)

Extracts text content from uploaded documents:

| File Type | Library | Extraction |
|-----------|---------|-----------|
| PDF | pdfplumber | Text + tables + metadata |
| DOCX | python-docx | Text + headings + tables |
| PPTX | python-pptx | Slide text + speaker notes |
| CSV/XLSX | pandas | Structured data as text/JSON |
| TXT | built-in | Raw text |

### URL Handler (`url_handler.py`)

Fetches and processes web page content:

| Step | Action | Library |
|------|--------|---------|
| 1 | Validate URL (block internal/malicious) | urllib |
| 2 | Load page in headless browser | Playwright |
| 3 | Take screenshot | Playwright |
| 4 | Extract text content | BeautifulSoup |
| 5 | Extract structured data (tables, links, contacts) | BeautifulSoup |
| 6 | Return content + screenshot | Gateway |

---

## Router (`router.py`)

Classifies user intent and selects the appropriate department agent.

### Routing Logic

```
Message + Department context + Source
    │
    ├── Source: "webhook" → route by event type mapping
    ├── Source: "scheduler" → route by job's configured agent
    ├── Source: "teams" → route by @mention context + user dept
    ├── Source: "mobile" → standard classification:
    │       ├── Department hint (user's dept) narrows agent selection
    │       ├── LLM classifies intent → confirms agent + required tools
    │       │
    │       ├── finance keywords + finance dept  →  Finance Agent
    │       ├── lead/prospect/pitch/CRM          →  Sales Agent
    │       ├── content/campaign/playbook        →  Marketing Agent
    │       ├── ticket/issue/customer complaint  →  Support Agent
    │       ├── KPI/dashboard/cross-dept         →  Management Agent
    │       └── ambiguous                        →  Ask user for clarification
```

---

## Task Queue & Scheduler (`/scheduler/`)

### Celery Configuration (`celery_app.py`)

```python
from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "mezzofy_ai",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Singapore",
    task_track_started=True,
    task_time_limit=600,            # 10 min hard limit
    task_soft_time_limit=540,       # 9 min soft limit
    worker_concurrency=4,           # 4 concurrent workers
    worker_prefetch_multiplier=1,   # Fair task distribution
)
```

### Background Tasks (`tasks.py`)

Long-running operations are dispatched to Celery workers instead of blocking the API:

```python
@celery_app.task(bind=True, max_retries=3)
def process_agent_task(self, task_data):
    """
    Execute an agent workflow as a background task.
    Used for: LinkedIn scraping, video processing, batch emails,
    webhook-triggered workflows, scheduled reports.
    """
    agent = get_agent(task_data["agent"])
    result = agent.execute(task_data)

    # Deliver results based on task configuration
    if task_data.get("deliver_to"):
        deliver_results(result, task_data["deliver_to"])

    # Notify user via WebSocket if they're connected
    if task_data.get("user_id"):
        notify_user_ws(task_data["user_id"], result)

    return result


@celery_app.task
def process_webhook_event(source, event_type, payload):
    """Process an incoming webhook event asynchronously."""
    handler = WEBHOOK_HANDLERS.get(f"{source}:{event_type}")
    if handler:
        handler(payload)


@celery_app.task
def process_video_upload(file_path, user_id, session_id):
    """Process video uploads as background task with progress updates."""
    # Extract frames, transcribe audio, analyze — send progress via WS
    ...
```

### Recurring Schedules (`beat_schedule.py`)

Pre-configured recurring jobs loaded at startup + user-created jobs from the `scheduled_jobs` table:

```python
# Built-in recurring jobs
CELERY_BEAT_SCHEDULE = {
    # Health check — every 5 minutes
    "system-health-check": {
        "task": "scheduler.tasks.health_check",
        "schedule": crontab(minute="*/5"),
    },

    # Weekly KPI report — Monday 9AM SGT
    "weekly-kpi-report": {
        "task": "scheduler.tasks.process_agent_task",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
        "args": [{
            "agent": "management",
            "message": "Generate weekly KPI dashboard across all departments",
            "deliver_to": {
                "teams_channel": "management",
                "email": ["ceo@mezzofy.com", "coo@mezzofy.com"]
            }
        }]
    },

    # Monthly financial summary — 1st of month 8AM SGT
    "monthly-financial-summary": {
        "task": "scheduler.tasks.process_agent_task",
        "schedule": crontab(hour=8, minute=0, day_of_month=1),
        "args": [{
            "agent": "finance",
            "message": "Generate monthly financial summary for last month",
            "deliver_to": {
                "teams_channel": "finance",
                "email": ["cfo@mezzofy.com"]
            }
        }]
    },

    # Daily stale lead follow-up — weekdays 10AM SGT
    "daily-lead-followup": {
        "task": "scheduler.tasks.process_agent_task",
        "schedule": crontab(hour=10, minute=0, day_of_week="mon-fri"),
        "args": [{
            "agent": "sales",
            "message": "Find all leads with follow_up_date = today and send follow-up emails",
            "deliver_to": {"teams_channel": "sales"}
        }]
    },

    # Weekly support ticket summary — Friday 5PM SGT
    "weekly-support-summary": {
        "task": "scheduler.tasks.process_agent_task",
        "schedule": crontab(hour=17, minute=0, day_of_week=5),
        "args": [{
            "agent": "support",
            "message": "Summarize this week's support tickets and flag recurring issues",
            "deliver_to": {
                "teams_channel": "support",
                "email": ["support-manager@mezzofy.com"]
            }
        }]
    },
}

# User-created jobs are loaded from PostgreSQL scheduled_jobs table
# and merged into the beat schedule at startup
```

### Delivery Methods

When a scheduled job or webhook task completes, results are delivered through configured channels:

```python
def deliver_results(result, deliver_to):
    """Deliver agent results to configured channels."""

    # Post to MS Teams channel
    if deliver_to.get("teams_channel"):
        teams_ops.post_message(
            channel=deliver_to["teams_channel"],
            text=result["content"],
            attachments=result.get("artifacts", [])
        )

    # Send via Outlook email
    if deliver_to.get("email"):
        for recipient in deliver_to["email"]:
            outlook_ops.send_email(
                to=recipient,
                subject=f"[Mezzofy AI] {result.get('title', 'Report')}",
                body=result["content"],
                attachments=result.get("artifacts", [])
            )

    # Mobile push notification
    if deliver_to.get("push_user_id"):
        push_ops.send_push(
            user_id=deliver_to["push_user_id"],
            title="Task Complete",
            body=result["content"][:100]
        )
```

---

## Output Generators (`/output/`)

### PDF Output (`pdf_output.py`)

Generates professional PDFs with Mezzofy branding for financial statements, reports, playbooks. Uses ReportLab or WeasyPrint with HTML templates.

### PPTX Output (`pptx_output.py`)

Generates slide decks from Mezzofy-branded templates. Uses python-pptx. Supports dynamic content insertion into pre-designed layouts.

### Email Output (`email_output.py`) — via MS Graph API

Composes and sends emails through Outlook (Microsoft Graph API, not raw SMTP):

```python
# Uses Microsoft Graph API
# POST https://graph.microsoft.com/v1.0/users/{sender}/sendMail
# Supports: HTML body, attachments, CC/BCC, reply-to
# All sent emails logged in email_log table for audit
```

### Calendar Output (`calendar_output.py`) — via MS Graph API

Creates Outlook calendar events:

```python
# POST https://graph.microsoft.com/v1.0/users/{user}/events
# Used for: scheduling follow-up reminders, meeting requests, deadline alerts
```

### Teams Output (`teams_output.py`) — via MS Graph API

Posts messages and notifications to MS Teams channels:

```python
# POST https://graph.microsoft.com/v1.0/teams/{team}/channels/{channel}/messages
# Used for: report delivery, webhook notifications, agent status updates
```

### Document Output (`document_output.py`)

Generates DOCX (python-docx), Markdown, and CSV exports.

---

## Context Processor (`/context/processor.py`)

Final assembly stage that combines tool results into the response.

### Processing Flow

```
Agent execution complete
    │
    ├── 1. Merge tool results (success checks, output aggregation)
    ├── 2. Store artifacts (PDFs, PPTX, CSVs → EBS/S3, record in DB)
    ├── 3. Update conversation history (PostgreSQL)
    ├── 4. Write audit log entry
    └── 5. Format response for output channel (mobile / Teams / email / push)
```

---

## WebSocket Streaming (`/api/chat.py`)

For long-running tasks, the mobile app connects via WebSocket to receive progress updates:

```
Client → WS /chat/ws (JWT in header)

Server streams:
  {"type": "status", "message": "Searching LinkedIn..."}
  {"type": "status", "message": "Found 23 leads, composing emails..."}
  {"type": "task_queued", "task_id": "celery_xyz", "estimated_seconds": 120}
  {"type": "task_progress", "task_id": "celery_xyz", "progress": 60, "message": "Sending emails..."}
  {"type": "complete", "response": {...}, "artifacts": [...]}
```

This prevents the mobile app from timing out on multi-step workflows. Background Celery tasks push progress updates through WebSocket via Redis pub/sub.

---

## Process Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Nginx (port 443)                                             │
│  SSL termination, rate limiting, static files                │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI (Uvicorn × 4 workers, port 8000)                     │
│  REST API + WebSocket + Webhook ingestion                    │
│  Enqueues long-running tasks to Celery                       │
└──────────┬───────────────────────────────────────────────────┘
           │
     ┌─────┼──────────────┐
     │     │              │
     ▼     ▼              ▼
┌────────┐ ┌────────────┐ ┌──────────────────┐
│ Redis  │ │ Celery     │ │ Celery Beat      │
│ Broker │ │ Workers ×4 │ │ (Scheduler)      │
│        │ │            │ │ Fires cron jobs  │
└────────┘ └────────────┘ └──────────────────┘
```

**Running the full stack:**
```bash
# Terminal 1: FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Terminal 2: Celery workers (background tasks)
celery -A scheduler.celery_app worker --loglevel=info --concurrency=4

# Terminal 3: Celery Beat (scheduled jobs)
celery -A scheduler.celery_app beat --loglevel=info

# All managed by systemd in production (see INFRASTRUCTURE.md)
```

---

## Deployment

The server runs behind Nginx on AWS EC2:

```
Mobile App  → HTTPS → Nginx (SSL, rate limit) → FastAPI (Uvicorn)
MS Teams    → HTTPS → Nginx → /webhooks/teams → Celery worker
Mezzofy App → HTTPS → Nginx → /webhooks/mezzofy → Celery worker
Scheduler   → Celery Beat → Redis → Celery worker → Agent → Output
```

See [INFRASTRUCTURE.md](INFRASTRUCTURE.md) for full AWS deployment details.
