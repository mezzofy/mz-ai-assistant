# TOOLS.md — Tool Implementations

**MS 365 Outlook (email + calendar), MS Teams, PDF, PPTX, web scraping, LinkedIn, CRM/lead database, Mezzofy data API, and database tools.**

---

## Overview

```
/server/tools
├── base_tool.py              # Base class (same pattern — name, description, params, execute)
├── tool_executor.py          # Central orchestrator — register, resolve, execute
│
├── /communication            # Microsoft 365 + push notifications
│   ├── outlook_ops.py        # Outlook email (send/read) + calendar (create/read) via MS Graph
│   ├── teams_ops.py          # MS Teams channel messages + DMs via MS Graph
│   └── push_ops.py           # Mobile push notifications (FCM/APNs)
│
├── /document                 # File generation
│   ├── pdf_ops.py            # PDF generation (ReportLab / WeasyPrint)
│   ├── pptx_ops.py           # Slide deck generation (python-pptx)
│   ├── docx_ops.py           # Word documents (python-docx)
│   └── csv_ops.py            # CSV export (pandas)
│
├── /media                    # Media processing (input pipeline)
│   ├── image_ops.py          # OCR, resize, format conversion, vision analysis
│   ├── video_ops.py          # Frame extraction, audio separation, analysis
│   ├── audio_ops.py          # STT transcription (Whisper), format conversion
│   └── speech_ops.py         # Live STT streaming, language detection
│
├── /web                      # Web interaction
│   ├── browser_ops.py        # Playwright headless browser
│   ├── scraping_ops.py       # BeautifulSoup extraction
│   └── linkedin_ops.py       # LinkedIn-specific scraping
│
├── /database                 # Data access
│   ├── db_ops.py             # PostgreSQL queries
│   └── crm_ops.py            # CRM / sales lead CRUD
│
└── /mezzofy                  # Internal Mezzofy systems
    ├── data_ops.py           # Product data, pricing, features
    └── knowledge_ops.py      # Knowledge base search (templates, brand, playbooks)
```

---

## Base Tool Pattern

Same as original spec — all tools share a common interface:

```python
class BaseTool:
    def __init__(self, name, description, parameters, implementation):
        ...

    def get_definition(self) -> dict:
        """OpenAI-compatible function definition for LLM tool calling."""

    async def execute(self, **kwargs) -> dict:
        """Execute with error handling → {success, output} or {success, error}."""
```

---

## Communication Tools (`/communication`)

### Microsoft 365 — Outlook Email & Calendar (`outlook_ops.py`)

All email and calendar operations use the **Microsoft Graph API** (not raw SMTP/IMAP). Authentication is via Azure AD app registration with client credentials flow (application permissions).

**Authentication:**
```python
from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient

credential = ClientSecretCredential(
    tenant_id=config["ms365"]["tenant_id"],
    client_id=config["ms365"]["client_id"],
    client_secret=config["ms365"]["client_secret"],
)
graph_client = GraphServiceClient(credential)
```

#### Email Tools

| Tool | Description |
|------|-------------|
| `outlook_send_email` | Send email via Outlook with HTML body, CC/BCC, attachments |
| `outlook_read_emails` | Read inbox (filter by sender, subject, date, folder) |
| `outlook_batch_send` | Send personalized emails to a list with rate limiting |
| `outlook_reply_email` | Reply to a specific email thread |
| `outlook_search_emails` | Search emails by keyword across folders |

**`outlook_send_email` — Implementation:**
```python
# POST https://graph.microsoft.com/v1.0/users/{sender}/sendMail
async def outlook_send_email(to, subject, body_html, cc=None, bcc=None, attachments=None):
    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body_html},
        "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
    }
    if cc:
        message["ccRecipients"] = [{"emailAddress": {"address": addr}} for addr in cc]
    if attachments:
        message["attachments"] = [_build_attachment(a) for a in attachments]

    await graph_client.users.by_user_id(SENDER_EMAIL).send_mail.post(
        body={"message": message, "saveToSentItems": True}
    )
```

**Key considerations:**
- Sender address: `ai-assistant@mezzofy.com` (configured in Azure AD)
- Rate limiting: max 30 emails per hour to avoid throttling by Microsoft
- All sent emails logged to `email_log` table for audit
- Attachments supported (PDF, PPTX, CSV from generated artifacts)
- HTML email templates loaded from `/knowledge/templates/emails/`
- All emails include "Sent via Mezzofy AI Assistant" footer

#### Calendar Tools

| Tool | Description |
|------|-------------|
| `outlook_create_event` | Create calendar event (meeting, reminder, deadline) |
| `outlook_get_events` | Read calendar events for a date range |
| `outlook_find_free_slots` | Find available time slots for a user |

**`outlook_create_event` — Implementation:**
```python
# POST https://graph.microsoft.com/v1.0/users/{user}/events
async def outlook_create_event(user_email, subject, start, end, body=None, attendees=None):
    event = {
        "subject": subject,
        "start": {"dateTime": start, "timeZone": "Asia/Singapore"},
        "end": {"dateTime": end, "timeZone": "Asia/Singapore"},
    }
    if body:
        event["body"] = {"contentType": "HTML", "content": body}
    if attendees:
        event["attendees"] = [
            {"emailAddress": {"address": a}, "type": "required"}
            for a in attendees
        ]

    await graph_client.users.by_user_id(user_email).events.post(body=event)
```

**Use cases:**
- Sales: "Schedule a follow-up call with ABC Corp next Tuesday at 2PM" → creates Outlook event
- Finance: "Remind me to submit Q1 tax filing by March 15" → creates calendar reminder
- Management: "Block my calendar for a strategy session this Friday 10-12" → creates event

#### MS Graph API Permissions Required

| Permission | Type | Purpose |
|-----------|------|---------|
| `Mail.Send` | Application | Send emails on behalf of users |
| `Mail.Read` | Application | Read inbox for email tools |
| `Mail.ReadWrite` | Application | Move/categorize emails |
| `Calendars.ReadWrite` | Application | Create/read calendar events |

### Microsoft Teams (`teams_ops.py`)

All Teams operations use **Microsoft Graph API**:

| Tool | Description |
|------|-------------|
| `teams_post_message` | Post message to a Teams channel (with optional file attachments) |
| `teams_send_dm` | Send direct message to a user in Teams |
| `teams_list_channels` | List available channels in the Mezzofy team |
| `teams_read_messages` | Read recent messages from a channel |

**`teams_post_message` — Implementation:**
```python
# POST https://graph.microsoft.com/v1.0/teams/{team-id}/channels/{channel-id}/messages
async def teams_post_message(channel_name, text, attachments=None):
    channel_id = CHANNEL_MAP[channel_name]  # "sales" → actual channel ID

    message_body = {
        "body": {
            "contentType": "html",
            "content": text
        }
    }

    if attachments:
        # Upload files to Teams channel first, then reference in message
        message_body["attachments"] = [
            await _upload_and_reference(channel_id, a) for a in attachments
        ]

    await graph_client.teams.by_team_id(TEAM_ID) \
        .channels.by_channel_id(channel_id) \
        .messages.post(body=message_body)
```

**Channel mapping** (configured in config.yaml):

| Channel Name | Used By | Example Posts |
|-------------|---------|---------------|
| `#general` | All | System announcements |
| `#sales` | Sales Agent | Lead reports, follow-up reminders, new customer alerts |
| `#finance` | Finance Agent | Financial statements, monthly summaries |
| `#marketing` | Marketing Agent | Content drafts, campaign updates |
| `#support` | Support Agent | Ticket summaries, escalation alerts |
| `#management` | Management Agent | KPI dashboards, audit alerts |

**Use cases:**
- Scheduled report → posted to department channel with PDF attached
- Webhook event (new customer) → notification posted to #sales
- Agent completes a task → status update posted to relevant channel
- @mention Mezzofy AI bot in Teams → triggers agent workflow, replies in channel

#### MS Graph API Permissions Required

| Permission | Type | Purpose |
|-----------|------|---------|
| `Team.ReadBasic.All` | Application | Read Teams and channel info |
| `ChannelMessage.Send` | Application | Post messages to channels |
| `Chat.ReadWrite` | Application | Send and read DMs |
| `Files.ReadWrite.All` | Application | Upload attachments to Teams |

### Push Notifications (`push_ops.py`)

| Tool | Description |
|------|-------------|
| `send_push` | Send push notification to user's mobile app |

Used to notify users when long-running tasks complete (e.g., "Your pitch deck is ready") or when scheduled jobs deliver results.

---

## Document Tools (`/document`)

### PDF (`pdf_ops.py`)

| Tool | Description |
|------|-------------|
| `create_pdf` | Generate branded PDF from content + template |
| `read_pdf` | Extract text from uploaded PDF |
| `merge_pdfs` | Merge multiple PDFs |

- Uses WeasyPrint (HTML→PDF) for complex layouts with Mezzofy branding
- Fallback to ReportLab for simple text-based PDFs
- Templates in `/knowledge/templates/pdf/` (financial statement, playbook, report)

### PPTX (`pptx_ops.py`)

| Tool | Description |
|------|-------------|
| `create_pptx` | Generate slide deck from content + template |
| `read_pptx` | Extract text/content from uploaded PPTX |

- Uses python-pptx
- Mezzofy-branded slide master in `/knowledge/templates/pptx/`
- Dynamic slide generation: title, content, charts, images, CTA

### DOCX (`docx_ops.py`)

| Tool | Description |
|------|-------------|
| `create_docx` | Generate Word document |
| `read_docx` | Extract text from uploaded DOCX |

### CSV (`csv_ops.py`)

| Tool | Description |
|------|-------------|
| `create_csv` | Export data as CSV |
| `read_csv` | Parse uploaded CSV |

---

## Media Processing Tools (`/media`)

These tools power the server-side input processing pipeline for multi-modal inputs from the mobile app.

### Image (`image_ops.py`)

| Tool | Description | Library |
|------|-------------|---------|
| `ocr_image` | Extract text from image via OCR | Tesseract (pytesseract) |
| `analyze_image` | Describe image content via Vision API | Claude Vision |
| `resize_image` | Resize/compress image | Pillow |
| `extract_exif` | Extract EXIF metadata (GPS, date, device) | Pillow |

### Video (`video_ops.py`)

| Tool | Description | Library |
|------|-------------|---------|
| `extract_key_frames` | Extract frames at interval (default 1 per 5s) | OpenCV |
| `extract_audio_track` | Separate audio from video | FFmpeg / MoviePy |
| `get_video_info` | Get duration, resolution, FPS, codec | OpenCV |
| `analyze_video` | Combine frame + audio analysis | Claude Vision + Whisper |

### Audio (`audio_ops.py`)

| Tool | Description | Library |
|------|-------------|---------|
| `transcribe_audio` | Full audio file → text transcription | Whisper |
| `detect_language` | Detect spoken language | Whisper auto-detect |
| `convert_audio` | Convert between formats (M4A → WAV, etc.) | FFmpeg / pydub |
| `get_audio_info` | Get duration, format, sample rate | pydub |

### Speech (`speech_ops.py`)

| Tool | Description | Library |
|------|-------------|---------|
| `stream_stt` | Real-time speech-to-text from audio chunks | Whisper / Google Speech API |
| `detect_speech_language` | Detect language from speech | Whisper |

**Note:** Speech tools are used via WebSocket streaming, not standard REST tool calls.

---

## Web Tools (`/web`)

### Browser (`browser_ops.py`)

| Tool | Description |
|------|-------------|
| `open_page` | Load URL in headless browser |
| `screenshot_page` | Take screenshot |
| `extract_text` | Get page text content |

Uses Playwright with headless Chromium.

### Scraping (`scraping_ops.py`)

| Tool | Description |
|------|-------------|
| `scrape_url` | Extract content from URL (with optional CSS selector) |
| `extract_tables` | Extract HTML tables as structured data |
| `extract_links` | Get all links from a page |
| `extract_contact_info` | Find emails, phone numbers, addresses on page |

### LinkedIn (`linkedin_ops.py`)

| Tool | Description |
|------|-------------|
| `linkedin_search` | Search companies or people by criteria |
| `linkedin_extract` | Extract profile data from a LinkedIn URL |

**Important constraints:**
- Rate limited (max 50 profiles per session)
- Uses authenticated session (cookie-based)
- Respects LinkedIn's terms — scraping for internal sales use only
- Fallback to LinkedIn API if available
- Long searches enqueued as Celery background tasks

---

## Database Tools (`/database`)

### PostgreSQL (`db_ops.py`)

| Tool | Description |
|------|-------------|
| `query_db` | Execute read-only SQL query (SELECT only) |
| `query_financial` | Query financial tables with date range filters |
| `query_tickets` | Query support ticket tables |
| `query_analytics` | Query usage/analytics tables |

**Security:**
- Only SELECT queries allowed (no INSERT/UPDATE/DELETE via this tool)
- Queries are parameterized (no SQL injection)
- Access scoped by user's department permissions

### CRM / Sales Lead DB (`crm_ops.py`)

| Tool | Description |
|------|-------------|
| `create_lead` | Add new lead to sales_leads table |
| `update_lead` | Update lead status, notes, follow-up date |
| `search_leads` | Search leads by company, industry, status, date |
| `get_lead` | Get full lead details by ID |
| `export_leads` | Export leads matching criteria as CSV |
| `get_pipeline` | Get sales pipeline summary (by stage, by rep) |
| `get_stale_leads` | Get leads with follow_up_date ≤ today (for scheduled follow-ups) |

---

## Mezzofy Internal Tools (`/mezzofy`)

### Data API (`data_ops.py`)

| Tool | Description |
|------|-------------|
| `get_products` | Fetch Mezzofy product catalog (features, pricing, plans) |
| `get_case_studies` | Fetch relevant case studies by industry/use case |
| `get_pricing` | Get current pricing tables |
| `get_feature_specs` | Get detailed feature specifications |

### Knowledge Base (`knowledge_ops.py`)

| Tool | Description |
|------|-------------|
| `search_knowledge` | Search knowledge base by keyword/topic |
| `get_template` | Load a specific template (email, PDF, PPTX) |
| `get_brand_guidelines` | Load brand voice, colors, logo specs |
| `get_playbook` | Load existing playbook content |

---

## Tool Configuration

```yaml
# config/config.yaml → tools section
tools:
  ms365:
    enabled: true
    tenant_id: "${MS365_TENANT_ID}"
    client_id: "${MS365_CLIENT_ID}"
    client_secret: "${MS365_CLIENT_SECRET}"
    sender_email: "ai-assistant@mezzofy.com"
    rate_limit_emails_per_hour: 30

  teams:
    enabled: true
    team_id: "${MS_TEAMS_TEAM_ID}"
    channels:
      general: "19:general@thread.tacv2"
      sales: "19:sales@thread.tacv2"
      finance: "19:finance@thread.tacv2"
      marketing: "19:marketing@thread.tacv2"
      support: "19:support@thread.tacv2"
      management: "19:management@thread.tacv2"
    bot_name: "MezzofyAI"

  calendar:
    enabled: true
    default_timezone: "Asia/Singapore"
    reminder_minutes_before: 15

  browser:
    enabled: true
    headless: true
    timeout_seconds: 30

  linkedin:
    enabled: true
    rate_limit_per_session: 50
    session_cookie: "${LINKEDIN_COOKIE}"

  database:
    enabled: true
    connection_url: "${DATABASE_URL}"
    read_only: true

  knowledge_base:
    enabled: true
    directory: "knowledge"
```

---

## Tool Executor

Registers all tool collections at startup and provides them to the LLM:

```python
class ToolExecutor:
    def _load_all_tools(self):
        # Communication — MS 365
        self._register_tools(OutlookOps(config))     # Email + Calendar
        self._register_tools(TeamsOps(config))        # Teams messages
        self._register_tools(PushOps(config))         # Mobile push
        # Documents
        self._register_tools(PDFOps(config))
        self._register_tools(PPTXOps(config))
        self._register_tools(DocxOps(config))
        self._register_tools(CSVOps(config))
        # Media processing
        self._register_tools(ImageOps(config))
        self._register_tools(VideoOps(config))
        self._register_tools(AudioOps(config))
        self._register_tools(SpeechOps(config))
        # Web
        self._register_tools(BrowserOps(config))
        self._register_tools(ScrapingOps(config))
        self._register_tools(LinkedInOps(config))
        # Database
        self._register_tools(DatabaseOps(config))
        self._register_tools(CRMOps(config))
        # Mezzofy internal
        self._register_tools(MezzofyDataOps(config))
        self._register_tools(KnowledgeOps(config))
```

See [SECURITY.md](SECURITY.md) for permission-based tool access restrictions and MS 365 OAuth details.
