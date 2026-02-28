# Mezzofy AI Assistant — Setup & Master Reference

**Internal AI assistant for Mezzofy team operations — Finance, Sales, Marketing, Support & Management — via React Native mobile app backed by AWS-hosted AI server.**

---

## Project Overview

Mezzofy AI Assistant is a company-wide tool that enables every department to automate daily operations through natural language requests on a mobile app. The system runs on AWS EC2 with EBS storage, uses Claude and Kimi as LLM backends, integrates with Microsoft 365 (Outlook email + calendar) and Microsoft Teams, and exposes a secure REST/WebSocket API consumed by React Native apps on iOS and Android.

### What Each Department Gets

| Department | Example Use Cases |
|-----------|-------------------|
| **Finance** | "Generate the latest financial statement as PDF and send it to the CEO" |
| **Sales** | "Search LinkedIn for new leads in F&B industry in Singapore, generate a prospect list, and send intro emails" |
| **Sales** | "Create a pitch deck for [customer] using our latest product data" |
| **Marketing** | "Generate website content and a playbook for our new coupon feature to send to customers" |
| **Support** | "Summarize this week's support tickets and flag recurring issues" |
| **Management** | "Give me a dashboard of team KPIs across all departments this month" |
| **All** | Scheduled reports auto-delivered to MS Teams / Outlook every Monday at 9AM |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  MOBILE APP (React Native — iOS & Android)                   │
│                                                              │
│  INPUT MODES:                                                │
│  💬 Chat (Text)  │  📷 Image  │  🎥 Video  │  📹 Live Camera│
│  🎤 Live Speech  │  🔊 Audio  │  📎 Files  │  🌐 URL/Web   │
│                                                              │
│  • Department-based UI     • Multi-modal message composer    │
│  • File viewer / PDF       • Camera + mic integration        │
│  • Push notifications      • In-app browser + web scraping   │
└──────────────────────┬──────────────────────────────────────┘
                       │  HTTPS REST + WebSocket
                       │  (multipart uploads for media/files)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  API GATEWAY  (AWS EC2 — FastAPI + Nginx)                    │
│  • JWT authentication                                        │
│  • Role-based access control (RBAC)                          │
│  • Rate limiting                                             │
│  • Request logging                                           │
│  • Input type detection + media processing pipeline          │
│  • Webhook ingestion endpoint                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼──────────────┐
          │            │              │
          ▼            ▼              ▼
┌──────────────┐ ┌──────────┐ ┌────────────────┐
│  ROUTING     │ │ WEBHOOK  │ │  SCHEDULER     │
│  LAYER       │ │ HANDLER  │ │  (Celery Beat) │
│  • Classify  │ │ • MS     │ │  • Cron jobs   │
│  • Select    │ │   Teams  │ │  • Recurring   │
│    agent     │ │ • Mezzofy│ │    reports     │
│  • Tools     │ │   events │ │  • Auto        │
│    needed    │ │ • Custom │ │    follow-ups  │
└──────┬───────┘ └────┬─────┘ └───────┬────────┘
       │              │               │
       └──────────────┼───────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  LLM DECISION LAYER                                          │
│  ┌─────────────────┐       ┌─────────────────┐              │
│  │ Claude (Anthropic)      │ Kimi (Moonshot)  │              │
│  │ • Complex reasoning     │ • Chinese content │              │
│  │ • Document generation   │ • Asia-Pacific    │              │
│  │ • Code / analysis       │   market research │              │
│  └─────────────────┘       └─────────────────┘              │
│              │                      │                         │
│              ▼                      ▼                         │
│         TOOL ORCHESTRATION                                   │
│         • Which tools? What order? Parallel/Serial?          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  TASK QUEUE  (Celery + Redis)                                │
│  • Long-running jobs (LinkedIn scraping, video processing)   │
│  • Scheduled jobs (weekly reports, lead follow-ups)          │
│  • Concurrent user requests without blocking                 │
│  • Progress tracking → WebSocket status updates              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  TOOL EXECUTION                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Outlook  │ │ MS Teams │ │   PDF    │ │  Web     │       │
│  │ Email +  │ │ Messages │ │ Generator│ │ Scraper  │       │
│  │ Calendar │ │ + Notify │ │          │ │          │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  PPTX    │ │  CRM /   │ │ Mezzofy  │ │ Database │       │
│  │ Generator│ │ Lead DB  │ │ Data API │ │  Query   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Image   │ │  Video   │ │  Audio   │ │ LinkedIn │       │
│  │ Analysis │ │ Analysis │ │  STT     │ │ Scraper  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  DATA & MEMORY LAYER  (AWS EBS + PostgreSQL)                 │
│  • Conversation history                                      │
│  • Sales lead database / CRM                                 │
│  • Scheduled jobs registry                                   │
│  • Generated files (S3 or EBS)                               │
│  • Mezzofy knowledge base (product data, templates)          │
│  • Audit logs                                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  OUTPUT LAYER                                                │
│  PDF │ PPTX │ Outlook Email │ DOCX │ CSV │ MS Teams Message  │
│  Push Notification │ Calendar Event                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Documentation Index

| Document | Description |
|----------|-------------|
| **[APP.md](APP.md)** | Core server — FastAPI gateway, REST/WebSocket API, Router, Input/Output, Webhooks, Scheduler |
| **[LLM.md](LLM.md)** | LLM layer — Claude (Anthropic) + Kimi (Moonshot), model routing logic |
| **[AGENTS.md](AGENTS.md)** | Department agents — Finance, Sales, Marketing, Support, Management |
| **[SKILLS.md](SKILLS.md)** | Skills — LinkedIn prospecting, financial reporting, pitch decks, content gen, email outreach |
| **[TOOLS.md](TOOLS.md)** | Tools — MS 365 Outlook (email + calendar), MS Teams, PDF, PPTX, web scraping, CRM/lead DB, Mezzofy data API |
| **[CONFIG.md](CONFIG.md)** | Configuration — config.yaml, .env, roles.yaml, requirements, AWS settings |
| **[INFRASTRUCTURE.md](INFRASTRUCTURE.md)** | AWS EC2/EBS, folder structure, deployment, DB migrations, React Native app |
| **[SECURITY.md](SECURITY.md)** | JWT auth, RBAC, MS 365 OAuth, department permissions, API security, data encryption |
| **[MEMORY.md](MEMORY.md)** | PostgreSQL schema, sales lead CRM, conversation history, scheduled jobs, knowledge base, file storage |
| **[TESTING.md](TESTING.md)** | Department workflow tests, API tests, scheduler tests, webhook tests, success criteria |

---

## Folder Structure

```
mezzofy-ai-assistant/
│
├── /server                           # Backend (Python — AWS EC2)
│   ├── /app                          # Core application
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── gateway.py               # Request processing + routing
│   │   ├── router.py                # Intent classification → agent
│   │   ├── /api                     # REST API endpoints
│   │   │   ├── auth.py              # Login, JWT, refresh tokens
│   │   │   ├── chat.py              # Conversation endpoints
│   │   │   ├── files.py             # File upload/download
│   │   │   ├── webhooks.py          # Webhook ingestion (MS Teams, Mezzofy, custom)
│   │   │   ├── scheduler.py         # Scheduled job CRUD API
│   │   │   └── admin.py             # User/role management
│   │   ├── /input                   # Multi-modal input processors
│   │   │   └── (8 handlers — text, image, video, camera, speech, audio, file, URL)
│   │   ├── /llm                     # LLM clients
│   │   │   ├── llm_manager.py       # Orchestrator
│   │   │   ├── anthropic_client.py  # Claude
│   │   │   └── kimi_client.py       # Kimi / Moonshot
│   │   ├── /output                  # Output generators
│   │   └── /context                 # Session + artifact management
│   │
│   ├── /agents                      # Department agents
│   │   ├── base_agent.py
│   │   ├── finance_agent.py
│   │   ├── sales_agent.py
│   │   ├── marketing_agent.py
│   │   ├── support_agent.py
│   │   └── management_agent.py
│   │
│   ├── /skills                      # Modular skills
│   │   └── /available               # YAML + Python skill pairs
│   ├── /tools                       # Tool implementations
│   │   ├── /communication           # MS 365 Outlook email + calendar, MS Teams, push
│   │   │   ├── outlook_ops.py       # Send/read email, create/read calendar events
│   │   │   ├── teams_ops.py         # Post messages, send DMs, channel notifications
│   │   │   └── push_ops.py          # Mobile push notifications
│   │   ├── /document                # PDF, PPTX, DOCX, CSV
│   │   ├── /media                   # Image, video, audio, speech processing
│   │   ├── /web                     # Browser, scraping, LinkedIn
│   │   ├── /database                # PostgreSQL, CRM queries
│   │   └── /mezzofy                 # Internal data API
│   │
│   ├── /scheduler                   # Celery task queue + scheduled jobs
│   │   ├── celery_app.py            # Celery configuration + Redis broker
│   │   ├── tasks.py                 # Background task definitions
│   │   ├── beat_schedule.py         # Recurring job schedules (cron)
│   │   └── webhook_tasks.py         # Webhook-triggered async tasks
│   │
│   ├── /knowledge                   # Mezzofy knowledge base
│   ├── /config
│   ├── /scripts
│   ├── /logs
│   ├── requirements.txt
│   └── Dockerfile
│
├── /mobile                           # React Native (iOS + Android)
│   ├── /src
│   │   ├── /screens                 # Login, Chat, Files, Settings
│   │   ├── /components
│   │   ├── /services                # API client, auth, push
│   │   └── /stores
│   ├── package.json
│   └── app.json
│
└── README.md
```

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| AWS EC2 | t3.xlarge+ with Ubuntu 22.04 |
| AWS EBS | Persistent storage for DB + files |
| Python 3.10+ | Server backend |
| PostgreSQL 15+ | Primary database |
| Redis 7+ | Task queue broker + rate limiting + caching |
| Celery 5+ | Background task queue + scheduler |
| Node.js 18+ | React Native development |
| Xcode / Android Studio | Mobile app builds |

### API Keys & Credentials Required

| Key | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY` | Claude — primary LLM |
| `KIMI_API_KEY` | Kimi / Moonshot — secondary LLM |
| `MS365_CLIENT_ID` | Microsoft 365 app registration (Azure AD) |
| `MS365_CLIENT_SECRET` | Microsoft 365 app secret |
| `MS365_TENANT_ID` | Azure AD tenant ID |
| `JWT_SECRET` | Auth token signing |
| `DATABASE_URL` | PostgreSQL connection |

### Microsoft 365 Setup

The assistant uses Microsoft Graph API for Outlook email, calendar, and MS Teams:

1. **Register app** in Azure AD (portal.azure.com → App registrations)
2. **API permissions** required:
   - `Mail.Send` — send emails via Outlook
   - `Mail.Read` — read inbox
   - `Calendars.ReadWrite` — create/read calendar events
   - `Team.ReadBasic.All` — read Teams channels
   - `ChannelMessage.Send` — post to Teams channels
   - `Chat.ReadWrite` — send DMs in Teams
3. **Grant admin consent** for the Mezzofy tenant
4. **Add credentials** to `.env` (client ID, secret, tenant ID)

---

## Build Order

1. **Infrastructure** → [INFRASTRUCTURE.md](INFRASTRUCTURE.md)
2. **Configuration** → [CONFIG.md](CONFIG.md)
3. **Security** → [SECURITY.md](SECURITY.md)
4. **Tools** → [TOOLS.md](TOOLS.md) — including MS 365 + Teams integration
5. **Skills** → [SKILLS.md](SKILLS.md)
6. **LLM Layer** → [LLM.md](LLM.md)
7. **Agents** → [AGENTS.md](AGENTS.md)
8. **Memory** → [MEMORY.md](MEMORY.md) — including scheduled_jobs table
9. **Task Queue & Scheduler** → [APP.md](APP.md) — Celery + Beat setup
10. **App / API** → [APP.md](APP.md) — including webhook endpoints
11. **Testing** → [TESTING.md](TESTING.md)
12. **Mobile App** → [INFRASTRUCTURE.md](INFRASTRUCTURE.md)

---

## Example Workflows

### Finance: Generate & Send Financial Statement
```
Finance user → "Generate the latest financial statement and send to CEO"
→ Finance Agent → database_query (fetch data) → pdf_generator → outlook_send_email
→ Output: "Financial statement sent to CEO via Outlook ✓" + downloadable PDF
```

### Sales: LinkedIn Lead Generation
```
Sales user → "Find 20 F&B companies in Singapore on LinkedIn and send intro emails"
→ Sales Agent → linkedin_scraper → crm_save (leads) → outlook_compose_email → outlook_send_email
→ Output: "23 leads found, 20 emails sent via Outlook, saved to CRM" + CSV export
```

### Sales: Auto-Generate Pitch Deck
```
Sales user → "Create a pitch deck for ABC Restaurant Group"
→ Sales Agent → mezzofy_data (products) → web_research (customer) → pptx_generator
→ Output: "Deck ready" + pitch_ABC_Restaurant.pptx
```

### Marketing: Content & Playbook
```
Marketing user → "Write website content and playbook for our new loyalty feature"
→ Marketing Agent → mezzofy_data (feature specs) → content_generator → pdf_generator
→ Output: website copy .md + playbook .pdf
```

### Scheduled: Weekly KPI Report (Automatic)
```
Every Monday 9:00 AM → Celery Beat triggers "weekly_kpi_report" job
→ Management Agent → cross-department DB queries → pdf_generator
→ teams_post_message → post PDF to #management Teams channel
→ outlook_send_email → email PDF to all executives
```

### Webhook: New Mezzofy Customer Sign-Up
```
Mezzofy product → POST /webhooks/mezzofy (event: "customer_signed_up")
→ Webhook handler → Sales Agent → crm_save → outlook_compose_email (welcome email)
→ teams_post_message → notify #sales channel: "New customer: ABC Corp"
```

### Scheduled: Auto Follow-Up on Stale Leads
```
Daily 10:00 AM → Celery Beat triggers "follow_up_stale_leads" job
→ Sales Agent → crm_query (leads with follow_up_date = today)
→ outlook_compose_email → send follow-up emails
→ crm_update → update last_contacted
→ teams_post_message → notify sales rep in Teams
```
