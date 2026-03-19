# Mezzofy AI Assistant — Features List v2.0

**Last Updated:** March 19, 2026
**Version:** 2.0.0

---

## Table of Contents

1. [General Features (All Users)](#general-features-all-users)
2. [Personal Microsoft Account Integration](#personal-microsoft-account-integration)
3. [Sales Department Features](#sales-department-features)
4. [Marketing Department Features](#marketing-department-features)
5. [Finance Department Features](#finance-department-features)
6. [Human Resources Department Features](#human-resources-department-features)
7. [Support Department Features](#support-department-features)
8. [Management Department Features](#management-department-features)
9. [Agent Enhancement v2.0 — Multi-Agent Team](#agent-enhancement-v20--multi-agent-team) ⭐ NEW
10. [Special Agents — Research, Developer, Scheduler](#special-agents--research-developer-scheduler) ⭐ NEW
11. [Cross-Department Orchestration](#cross-department-orchestration) ⭐ NEW
12. [RAG Knowledge Namespacing](#rag-knowledge-namespacing) ⭐ NEW
13. [Mission Control Admin Portal](#mission-control-admin-portal) ⭐ NEW
14. [Knowledge Base & Search](#knowledge-base--search)
15. [Database & Analytics Queries](#database--analytics-queries)
16. [File Storage Hierarchy](#file-storage-hierarchy)
17. [Supported File Formats](#supported-file-formats)
18. [Rate Limits & Constraints](#rate-limits--constraints)
19. [Timezone Reference](#timezone-reference)

---

## General Features (All Users)

### Communication & Collaboration

| Feature | Status |
|---------|:------:|
| Send emails via Microsoft Outlook (with CC, BCC, attachments) | ✅ |
| Batch send personalized emails to multiple recipients | ✅ |
| Read and search emails from Outlook inbox | ✅ |
| Reply to email threads | ✅ |
| Post messages to Microsoft Teams channels | ✅ |
| Send direct messages to Teams users | ✅ |
| Read messages from Teams channels | ✅ |
| Create and manage calendar events in Outlook | ✅ |
| Find available meeting time slots | ✅ |
| Create online Teams meetings with auto-generated links | ❌ |

### Document Generation & Processing

| Feature | Status |
|---------|:------:|
| Generate branded PDF reports with custom styling | ✅ |
| Create PowerPoint presentations with multiple slide types | ✅ |
| Generate Word documents with structured content | ✅ |
| Create CSV files for data export | ✅ |
| Create plain text files | ✅ |
| Read and extract text from PDFs, PPTX, DOCX, CSV, TXT files | ✅ |
| Merge multiple PDF files into one document | ✅ |
| File storage options: Personal, Department, or Company-wide folders | ✅ |
| Search user files across all accessible folders | ✅ |

### Image Processing

| Feature | Status |
|---------|:------:|
| OCR text extraction from images (supports multiple languages) | ✅ |
| AI-powered image analysis and description | ✅ |
| Resize and compress images | ✅ |
| Extract EXIF metadata (GPS, camera info, timestamps) | ✅ |
| Direct image analysis via Anthropic Files API (JPEG, PNG, WebP) | ✅ |

### Video & Audio Processing

| Feature | Status |
|---------|:------:|
| Extract key frames from videos for visual analysis | ✅ |
| Extract audio tracks from video files | ✅ |
| Get video metadata (duration, resolution, codec, FPS) | ✅ |
| Full video analysis (visual + audio transcription) | ✅ |
| Transcribe audio files to text using OpenAI Whisper | ✅ |
| Detect spoken language in audio | ✅ |
| Convert audio between formats (MP3, WAV, M4A, OGG, FLAC) | ✅ |
| Get audio file metadata | ✅ |

### Web Research & Scraping

| Feature | Status |
|---------|:------:|
| Open and load web pages in headless browser | ✅ |
| Take full-page screenshots of websites | ✅ |
| Extract visible text from web pages | ✅ |
| Scrape web content with CSS selector filtering | ✅ |
| Extract HTML tables from web pages | ✅ |
| Extract all hyperlinks from pages | ✅ |
| Extract contact information (emails, phones, addresses) | ✅ |

### LinkedIn Research

| Feature | Status |
|---------|:------:|
| Search LinkedIn for people or companies (requires Session ID) | ✅ |
| Extract structured profile data from LinkedIn URLs (requires Session ID) | ✅ |

### Push Notifications

| Feature | Status |
|---------|:------:|
| Send mobile push notifications to users via Firebase | ✅ |

---

## Personal Microsoft Account Integration

*(Requires user to connect personal Microsoft account in Settings)*

### Personal Email

| Feature | Status |
|---------|:------:|
| Read emails from personal Outlook/Hotmail/Microsoft 365 inbox | ✅ |
| Search personal emails by keyword | ✅ |
| Send emails from personal account | ✅ |
| Get detailed email information by message ID | ✅ |

### Personal Calendar

| Feature | Status |
|---------|:------:|
| View personal calendar events | ✅ |
| Create events in personal calendar | ✅ |
| Update existing calendar events | ✅ |
| Delete calendar events | ✅ |
| Find free time slots in personal calendar | ✅ |

### Personal OneNote

| Feature | Status |
|---------|:------:|
| List OneNote notebooks | ✅ |
| View OneNote pages | ✅ |
| Search OneNote pages | ✅ |
| Create new OneNote pages | ✅ |

### Personal Teams

| Feature | Status |
|---------|:------:|
| List personal Teams chats (1:1 and group) | ✅ |
| Read messages from Teams chats | ✅ |
| Send messages to Teams chats | ✅ |
| List joined Teams | ✅ |
| Read channel messages from personal Teams | ✅ |

### Personal Contacts *(v1.18.0)*

| Feature | Status |
|---------|:------:|
| List personal Microsoft contacts | ✅ |
| Search contacts by name or email | ✅ |
| View detailed contact information | ✅ |
| Create new contacts | ✅ |

### Diagnostics

| Feature | Status |
|---------|:------:|
| Check Microsoft Graph permissions and token scopes | ✅ |

---

## Sales Department Features

### CRM & Lead Management

| Feature | Status |
|---------|:------:|
| Create new sales leads in CRM | ✅ |
| Update lead status, notes, and follow-up dates | ✅ |
| Search leads by company, status, industry, or assigned rep | ✅ |
| Get full details for individual leads | ✅ |
| Export leads to CSV with filters | ✅ |
| Get sales pipeline summary (by status or rep) | ✅ |
| Identify stale/overdue leads requiring follow-up | ✅ |
| Email lead auto-ingestion (v1.26.0) | ✅ |

### Product & Sales Content

| Feature | Status |
|---------|:------:|
| Fetch Mezzofy product catalog and features | ✅ |
| Retrieve case studies filtered by industry or use case | ✅ |
| Get pricing tables by plan tier (multi-currency) | ✅ |
| Get detailed feature specifications | ✅ |
| Access sales playbooks (cold outreach, upsell, objection handling) | ✅ |
| Load email templates for campaigns | ✅ |

### Sales Agent Skills *(v2.0)*

| Skill | Description |
|-------|-------------|
| `linkedin_prospecting` | Search LinkedIn, save leads to CRM, send intro emails |
| `email_outreach` | Compose and batch-send personalized sales emails |
| `pitch_deck_generation` | Generate branded sales decks (PPTX) |
| `web_research` | Competitive intelligence and prospect research |

---

## Marketing Department Features

### Campaign Management

| Feature | Status |
|---------|:------:|
| Batch send personalized email campaigns (30/hour limit) | ✅ |
| Post marketing updates to Teams channels | ✅ |
| Generate branded marketing materials (PDF, PPTX, DOCX) | ✅ |

### Content & Brand

| Feature | Status |
|---------|:------:|
| Access Mezzofy brand guidelines (colors, voice, logo, typography) | ✅ |
| Load marketing email templates | ✅ |
| Access marketing playbooks | ✅ |
| Generate customer case studies | ✅ |

### Research & Analytics

| Feature | Status |
|---------|:------:|
| Web scraping for competitive research | ✅ |
| LinkedIn company and people search | ✅ |
| Extract contact information from websites | ✅ |
| Query analytics and usage data | ✅ |

### Marketing Agent Skills *(v2.0)*

| Skill | Description |
|-------|-------------|
| `content_generation` | AI-written marketing copy, blog posts, and campaign content |
| `web_research` | Market research and competitive analysis |

---

## Finance Department Features

### Financial Data Access

| Feature | Status |
|---------|:------:|
| Query financial data tables with date ranges | ✅ |
| Filter by specific metrics (revenue, orders, refunds) | ✅ |
| Export financial reports to CSV | ✅ |
| Generate branded financial PDF reports | ✅ |
| Access restricted finance data (requires `finance_read` permission) | ✅ |

### Reporting

| Feature | Status |
|---------|:------:|
| Create financial summaries in PowerPoint | ✅ |
| Generate Word documents for financial analysis | ✅ |
| Merge multiple financial PDFs | ✅ |
| Query analytics for financial KPIs | ✅ |

### Finance Agent Skills *(v2.0)*

| Skill | Description |
|-------|-------------|
| `financial_reporting` | Financial summaries, KPI reports, revenue analysis |
| `data_analysis` | Data aggregation and trend analysis |

---

## Human Resources Department Features

### HR Data Access

| Feature | Status |
|---------|:------:|
| Query personal data tables | ✅ |
| Leave management (apply, amend, approve) | ✅ |
| Access restricted HR data (requires `hr_read` permission) | ✅ |

### Reporting

| Feature | Status |
|---------|:------:|
| Create Organization Chart | ✅ |
| Generate Leave reports | ✅ |
| Export HR reports to CSV | ✅ |

### HR Agent Skills *(v2.0)*

| Skill | Description |
|-------|-------------|
| `data_analysis` | HR analytics, leave trends, headcount reporting |
| `email_outreach` | HR communications and employee notifications |

---

## Support Department Features

### Ticket Management

*(Requires connection to Mz Tickets App)*

| Feature | Status |
|---------|:------:|
| Query support tickets by status, assignee, or date range | ✅ |
| Filter tickets (open, in_progress, resolved, closed) | ✅ |
| Export ticket data to CSV | ✅ |
| Generate support performance reports | ✅ |

### Customer Communication

| Feature | Status |
|---------|:------:|
| Send support emails via Outlook | ✅ |
| Post updates to support Teams channel | ✅ |
| Access support playbooks and scripts | ✅ |
| Create ticket summary documents | ✅ |

### Support Agent Skills *(v2.0)*

| Skill | Description |
|-------|-------------|
| `data_analysis` | Ticket trend analysis and SLA reporting |
| `email_outreach` | Customer support email communications |

---

## Management Department Features

### Executive Access

| Feature | Status |
|---------|:------:|
| Full access to all department features | ✅ |
| Query any database (financial, tickets, analytics, CRM) | ✅ |
| Company-wide file storage permissions | ✅ |
| Access to all Teams channels | ✅ |
| View complete sales pipeline across all reps | ✅ |
| Export company-wide reports | ✅ |

### Strategic Tools

| Feature | Status |
|---------|:------:|
| Search entire knowledge base (brand, playbooks, templates) | ✅ |
| Access all case studies and product specifications | ✅ |
| Generate executive summary presentations | ✅ |
| Create board reports and strategic documents | ✅ |
| Query usage analytics across all departments | ✅ |
| Automated weekly KPI report (Monday 9AM SGT) | ✅ |
| LinkedIn prospecting → CRM save → intro email workflow | ✅ |

### Management Agent Skills *(v2.0)*

| Skill | Description |
|-------|-------------|
| `data_analysis` | Cross-department KPI aggregation |
| `web_research` | Executive research and competitive intelligence |

---

## Legal Department Features *(v1.34.0)* ⭐ NEW

### Document Review & Analysis

| Feature | Status |
|---------|:------:|
| Review uploaded legal documents (PDF, DOCX) | ✅ |
| Contract review: NDAs, MOUs, shareholder agreements, term sheets, employment contracts, vendor agreements | ✅ |
| Identify document type, parties, key dates, and governing law automatically | ✅ |
| Structured review: Executive Summary, Key Terms, Risk Flags, Missing Clauses, Jurisdiction Notes, Recommended Actions | ✅ |
| Generate branded PDF review report | ✅ |

### Contract Drafting & Generation

| Feature | Status |
|---------|:------:|
| Generate business contracts from natural language descriptions | ✅ |
| NDA, Service Agreement, Consultancy Agreement | ✅ |
| Employment Contract, Vendor/Supplier Agreement, MOU, Letter of Intent | ✅ |
| IP Assignment, Distribution Agreement, Shareholders Agreement (basic), Joint Venture Agreement (basic) | ✅ |
| Output in Word (DOCX) + PDF formats | ✅ |
| Customise jurisdiction-specific clauses | ✅ |

### Jurisdiction Coverage

| Jurisdiction | Arbitration Body | Status |
|-------------|:----------------:|:------:|
| Singapore — PDPA, Companies Act, Employment Act | SIAC | ✅ |
| Hong Kong — Companies Ordinance, Employment Ordinance | HKIAC | ✅ |
| Malaysia — Companies Act 2016, PDPA MY, Employment Act 1955 | AIAC | ✅ |
| UAE / Dubai (onshore, DIFC, ADGM) | DIAC / DIFC-LCIA | ✅ |
| Saudi Arabia — with Shari'ah law considerations | SCCA | ✅ |
| Qatar (onshore + QFC) | QICCA | ✅ |
| Cayman Islands — Exempted Companies, ELP, fund structures | Grand Court / London | ✅ |

### Legal Research & Advisory

| Feature | Status |
|---------|:------:|
| Jurisdiction-specific legal Q&A | ✅ |
| Compare legal frameworks across jurisdictions side-by-side | ✅ |
| Regulatory compliance checks for business activities | ✅ |
| Recommend best jurisdiction for business structures or transactions | ✅ |
| Clause extraction (indemnity, liability caps, termination, IP clauses, etc.) | ✅ |

### Legal Risk Assessment

| Feature | Status |
|---------|:------:|
| Legal risk matrix (Critical / High / Medium / Low severity) | ✅ |
| Jurisdiction-specific risk flags | ✅ |
| Recommended mitigations per risk item | ✅ |

### Legal Agent Skills *(v1.34.0)*

| Skill | Description |
|-------|-------------|
| `document_review` | Extract, parse, and analyse legal documents (PDF, DOCX) |
| `contract_drafting` | Generate business contracts from templates and parameters |
| `legal_research` | Research jurisdiction-specific laws and regulations |
| `jurisdiction_advisory` | Jurisdiction advisory for SG, HK, MY, UAE, KSA, QA, Cayman |

> **Important:** All Leo (Legal Agent) outputs include a mandatory AI disclaimer — analysis is for reference only and does not constitute professional legal advice. Consult a qualified solicitor for binding decisions.

---

## Agent Enhancement v2.0 — Multi-Agent Team

*(v1.20.0 — Released March 2026)*

The AI Assistant now runs as a **team of 10 persistent AI agents**, each with a unique identity, assigned skills, and private knowledge namespace stored in the database.

### What's New in v2.0

| Component | Description |
|-----------|-------------|
| **Agents Table** | PostgreSQL `agents` table stores each agent's identity, skills, LLM model, memory namespace, and orchestrator flag |
| **AgentRegistry** | Database-backed singleton — loads all 10 agents at startup, supports skill-based discovery (`find_by_skill`, `get_by_department`) |
| **agent_task_log** | Every agent task is logged with parent/child chain — full delegation tracking and audit trail |
| **delegate_task()** | BaseAgent method to spawn child tasks on other agents via Celery with `parent_task_id` linking |
| **_load_knowledge()** | Each agent loads only its own private namespace + shared knowledge — no cross-agent data leakage |
| **requires_skill()** | Runtime skill capability check before executing skill-dependent workflows |

### The 10 Agent Team

| Agent Name | Persona | Department | Is Orchestrator |
|-----------|---------|:----------:|:---------------:|
| Management Agent | Max | management | ✅ Yes |
| Finance Agent | Fiona | finance | ❌ |
| Sales Agent | Sam | sales | ❌ |
| Marketing Agent | Maya | marketing | ❌ |
| Support Agent | Suki | support | ❌ |
| HR Agent | Hana | hr | ❌ |
| Legal Agent | Leo | legal | ❌ |
| Research Agent | Rex | research | ❌ |
| Developer Agent | Dev | developer | ❌ |
| Scheduler Agent | Sched | scheduler | ❌ |

---

## Special Agents — Research, Developer, Scheduler, Legal

*(v1.23.0–v1.34.0)*

These four agents handle specialized tasks that go beyond standard department workflows.

### Research Agent *(v1.23.0)*

**Persona:** Rex | **Trigger:** Message contains research keywords → `task["agent"] = "research"`

| Feature | Status |
|---------|:------:|
| Agentic web-search loop (up to 8 iterations) | ✅ |
| Claude native `web_search_20250305` tool support | ✅ |
| Kimi `$web_search` fallback (when KIMI_API_KEY set) | ✅ |
| Live step-by-step progress broadcast to mobile app | ✅ |
| Strip "research:" prefix from message automatically | ✅ |
| Multi-source research synthesis with citation tracking | ✅ |
| Source credibility scoring (high / medium / low tier) | ✅ |
| Claim verification against provided sources | ✅ |

**Skills:** `deep_research`, `source_verification`, `web_research`, `data_analysis`

**Sample prompts:**
- `"Research our top 5 competitors in Singapore"`
- `"research: What is the market size for coupon exchanges in Southeast Asia?"`

---

### Developer Agent *(v1.24.0)*

**Persona:** Dev | **Trigger:** Message contains code/build keywords → `task["agent"] = "developer"`

| Feature | Status |
|---------|:------:|
| Runs Claude Code CLI as headless subprocess | ✅ |
| Streams structured JSON output (thinking, tool_call, tool_result, done) | ✅ |
| Configurable work directory and 5-minute timeout | ✅ |
| Live step events broadcast to mobile app | ✅ |
| Code generation from natural language descriptions | ✅ |
| Static code review with severity-rated issue detection | ✅ |
| Safety scanning for dangerous patterns | ✅ |
| Code execution in isolated environment | ✅ |
| API integration code generation | ✅ |
| Unit test generation | ✅ |

**Skills:** `code_generation`, `code_review`, `code_execution`, `api_integration`, `test_generation`

**Sample prompts:**
- `"Build a Python script to process our leads CSV"`
- `"developer: Write unit tests for our scheduler module"`

---

### Scheduler Agent *(v1.25.0)*

**Persona:** Sched | **Trigger:** Scheduler keywords → `task["agent"] = "scheduler"`

| Feature | Status |
|---------|:------:|
| Natural language job creation (no cron syntax required) | ✅ |
| Create recurring scheduled jobs for any department agent | ✅ |
| List active scheduled jobs | ✅ |
| Delete / deactivate scheduled jobs | ✅ |
| Trigger a job immediately on demand | ✅ |
| SGT/HKT ↔ UTC automatic timezone conversion | ✅ |
| Cron expression validation and next-run preview | ✅ |
| Natural language → cron expression conversion | ✅ |
| Job health reports and failure detection | ✅ |
| Run history from agent_task_log | ✅ |
| Celery Beat live sync status | ✅ |
| Force next_run recalculation for stale jobs | ✅ |

**Skills:** `schedule_management`, `cron_validation`, `job_monitoring`, `beat_sync`

**Limits:** 10 active jobs per user · Minimum 15-minute interval

**Sample prompts:**
- `"Schedule a weekly sales report every Monday at 9am SGT"`
- `"List my scheduled jobs"`
- `"Delete the finance report job"`

---

### Legal Agent *(v1.34.0)*

**Persona:** Leo | **Trigger:** Message contains legal keywords (contract, NDA, agreement, legal advice, governing law, etc.) → `task["agent"] = "legal"` · Also delegatable from Management Agent

**Cross-departmental:** Any department can invoke Leo — Sales (vendor agreements), HR (employment contracts), Finance (investment agreements), Management (shareholder agreements).

| Feature | Status |
|---------|:------:|
| Legal document review (PDF, DOCX) with structured analysis | ✅ |
| Contract drafting: 11 contract types across 7 jurisdictions | ✅ |
| Auto-detect document type, parties, governing law | ✅ |
| Clause extraction as structured JSON | ✅ |
| Legal risk matrix (Critical / High / Medium / Low) | ✅ |
| Jurisdiction-specific advisory (SG, HK, MY, UAE, KSA, QA, Cayman) | ✅ |
| Cross-jurisdiction comparison | ✅ |
| Regulatory compliance checks | ✅ |
| Output: PDF review report + DOCX + PDF contract | ✅ |
| Mandatory AI legal disclaimer on all outputs | ✅ |

**Skills:** `document_review`, `contract_drafting`, `legal_research`, `jurisdiction_advisory`

**Sample prompts:**
- `"Review this NDA and flag any risk areas"` *(attach PDF/DOCX)*
- `"Draft a service agreement between Mezzofy and XYZ Corp under Singapore law"`
- `"What are the data protection obligations for a fintech company in UAE?"`

---

## Cross-Department Orchestration

*(v2.0 — ManagementAgent `plan_and_orchestrate`)*

When a Management user sends a request that spans multiple departments, the Management Agent automatically orchestrates a multi-agent plan.

### Trigger Keywords

Any of these phrases in a message triggers orchestration:

| Keyword Pattern | Example |
|----------------|---------|
| `compare` | "Compare sales and finance performance this quarter" |
| `versus` / `vs` | "Sales vs marketing ROI" |
| `across departments` | "Report across all departments" |
| `all departments` | "All departments summary" |
| `cross-department` | "Cross-department KPI" |
| `and sales` / `sales and` | "Finance and sales overview" |
| `and finance` / `finance and` | "Marketing and finance metrics" |
| `multiple departments` | "Multiple departments report" |
| `every department` | "Every department performance" |

### Orchestration Flow

```
Step 1 — Decompose
  LLM breaks the task into sub-tasks, each assigned to one specialist agent
  Returns a JSON plan: [{step, agent_id, task_description, depends_on_step}]

Step 2 — Log
  Writes the plan to agent_task_log with task_plan (JSONB)
  Each sub-task gets a parent_task_id linking back to the orchestration task

Step 3 — Execute
  Parallel steps → fire-and-forget Celery tasks
  Sequential steps → awaited before next step starts

Step 4 — Synthesise
  LLM collects all sub-task result_summaries and writes an executive report

Step 5 — Deliver
  Posts to Teams #management channel
  Emails CEO and COO (if configured in notifications settings)
```

---

## RAG Knowledge Namespacing

*(v2.0)*

Each agent has a **private knowledge namespace** — it can only access its own department's knowledge plus the shared knowledge base.

| Agent | Private Namespace | Shared Access |
|-------|:----------------:|:-------------:|
| Management Agent | `management/` | ✅ `shared/` |
| Finance Agent | `finance/` | ✅ `shared/` |
| Sales Agent | `sales/` | ✅ `shared/` |
| Marketing Agent | `marketing/` | ✅ `shared/` |
| Support Agent | `support/` | ✅ `shared/` |
| HR Agent | `hr/` | ✅ `shared/` |
| Research Agent | `research/` | ✅ `shared/` |
| Developer Agent | `developer/` | ✅ `shared/` |
| Scheduler Agent | `scheduler/` | ✅ `shared/` |

**Benefit:** Finance data never appears in Sales agent responses; HR knowledge stays private to HR. Namespace isolation is enforced in `BaseAgent._load_knowledge()`.

---

## Mission Control Admin Portal

*(v1.33.0)*

| Feature | Status |
|---------|:------:|
| Admin web portal for managing the AI Assistant | ✅ |
| View and manage all scheduled jobs across users | ✅ |
| Files subfolder display and navigation | ✅ |
| Sales leads management with assigned-to dropdown | ✅ |
| Action alignment and UI improvements | ✅ |

---

## Knowledge Base & Search

### Semantic Search

| Feature | Status |
|---------|:------:|
| Natural language query across knowledge base | ✅ |
| Finds conceptually related content (not just keyword matching) | ✅ |
| Categories: brand, playbooks, product_data, sales, templates | ✅ |

### Keyword Search

| Feature | Status |
|---------|:------:|
| Traditional keyword search in knowledge base | ✅ |
| Filter by category (templates, playbooks, brand, products, FAQs) | ✅ |

### Content Retrieval

| Feature | Status |
|---------|:------:|
| Load specific templates by name and type | ✅ |
| Access brand guidelines by section | ✅ |
| Retrieve playbooks with specific sections | ✅ |
| Get feature specifications | ✅ |
| Load case studies and product data | ✅ |

---

## Database & Analytics Queries

### General Database

| Feature | Status |
|---------|:------:|
| Execute read-only SQL queries (SELECT statements only) | ✅ |
| Parameterized queries for security | ✅ |
| Returns up to 500 rows per query | ✅ |

### Specialized Queries

| Feature | Status |
|---------|:------:|
| Financial data queries (date ranges, metrics) | ✅ |
| Support ticket queries (status, assignee filters) | ✅ |
| Analytics queries (usage, active users, API calls, errors) | ✅ |
| Time period analysis (7d, 30d, 90d, 1y) | ✅ |

---

## File Storage Hierarchy

| Scope | Folder | Visibility | Write Access |
|-------|--------|-----------|:------------:|
| **Personal** | `user/{user_id}/` | Owner only | Owner |
| **Department** | `department/{dept}/` | Dept members | Dept members |
| **Company** | `company/` | All staff | Management only |

---

## Supported File Formats

| Type | Formats |
|------|---------|
| Documents | PDF, PPTX, DOCX, TXT, CSV |
| Images | JPEG, PNG, TIFF, BMP, WEBP |
| Audio | MP3, WAV, M4A, OGG, FLAC, AAC |
| Video | MP4, MOV, AVI |

---

## Rate Limits & Constraints

| Constraint | Limit |
|-----------|-------|
| Batch email sending | 30 recipients/hour |
| LinkedIn search | 50 page loads/session |
| Email retrieval | Up to 100 most recent emails |
| Database queries | 500 rows maximum |
| Scheduled jobs | 10 active jobs per user |
| Minimum job interval | 15 minutes |
| File search results | Up to 50 files |
| Teams message history | Up to 50 messages |
| Research Agent iterations | 8 maximum per query |
| Developer Agent timeout | 300 seconds (5 minutes) |

---

## Timezone Reference

| Timezone | UTC Offset | Cron Example (9AM) |
|----------|:----------:|:-----------------:|
| SGT (Singapore) | +8 | `0 1 * * *` |
| HKT (Hong Kong) | +8 | `0 1 * * *` |
| MYT (Malaysia) | +8 | `0 1 * * *` |
| JST (Japan) | +9 | `0 0 * * *` |
| IST (India) | +5:30 | `30 3 * * *` |
| GMT/UTC | +0 | `0 9 * * *` |

---

*Mezzofy AI Assistant — Powered by Claude (Anthropic) · FastAPI · PostgreSQL · Redis · Celery*
