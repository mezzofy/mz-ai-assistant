# Claude Code Prompt — Sales Lead Automation (Scheduled Background Tasks)

> **Session strategy:** Feed this prompt as a **single session** to Claude Code CLI.
> The implementation spans multiple files — Claude Code will create them all in sequence.
> Do NOT split across sessions; interdependencies require a shared context.

---

## CONTEXT

You are building the **Sales Lead Automation** module for the Mezzofy AI Assistant backend.
The project stack is: **FastAPI · Celery · Celery Beat · Redis · PostgreSQL · MS Graph API**.
The server lives at `/server/` and follows the architecture defined in the project spec files.

The goal is a fully automated, scheduled Sales Lead ingestion and management pipeline that runs as **Celery background tasks**, with no manual intervention required for daily operations.

---

## OBJECTIVE

Implement four scheduled automation workflows for the Sales department:

| # | Workflow | Trigger | Description |
|---|----------|---------|-------------|
| 1 | **Email Lead Ingestion** | Daily 9:00 AM HKT | Read emails from `hello@mezzofy.com` and `sales@mezzofy.com` from the previous day. Extract leads and insert new records into CRM. |
| 2 | **Ticket Lead Ingestion** | Daily 9:00 AM HKT | Read support/contact tickets (from the website Contact Form) created in the previous day. Extract leads and insert new records into CRM. |
| 3 | **Web/LinkedIn Lead Research** | Weekly Monday 9:00 AM HKT · Manual trigger | Use web scraping and LinkedIn tools to research and discover new potential leads. Insert into CRM. |
| 4 | **Daily CRM Status Report** | Daily 9:00 AM HKT | Summarise new leads, their current status, and assigned PIC from the CRM. Post digest to MS Teams `#sales` channel and send to each PIC via Outlook. Allow PICs to update status and add remarks via the mobile app API. |

All times are **HKT (UTC+8)**. Cron expressions must account for the UTC offset.

---

## PHASE 1 — DATABASE AUDIT & SCHEMA EXTENSION

### Step 1.1 — Audit `sales_leads` Table

Open `scripts/migrate.py` and review the current `sales_leads` table definition.

Confirm or add the following columns. **Do not drop existing columns.** Use `ALTER TABLE … ADD COLUMN IF NOT EXISTS` for any new columns:

```sql
-- Required columns (add if missing)
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
company_name        TEXT NOT NULL
contact_name        TEXT
contact_email       TEXT
contact_phone       TEXT
industry            TEXT
location            TEXT
source              TEXT NOT NULL   -- 'email' | 'ticket' | 'linkedin' | 'web' | 'referral' | 'manual'
source_ref          TEXT            -- Original email ID, ticket ID, or LinkedIn URL — for dedup
status              TEXT NOT NULL DEFAULT 'new'
                    -- Lifecycle: new → contacted → qualified → proposal → closed_won | closed_lost | disqualified
assigned_to         UUID REFERENCES users(id)   -- PIC (sales rep)
notes               TEXT            -- Free-text remarks by PIC
last_status_update  TIMESTAMPTZ     -- Timestamp of most recent status change
follow_up_date      DATE            -- Scheduled follow-up date
created_at          TIMESTAMPTZ DEFAULT NOW()
last_contacted      TIMESTAMPTZ
updated_at          TIMESTAMPTZ DEFAULT NOW()
```

Also confirm or add a **dedup index** to prevent duplicate ingestion:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_leads_source_ref
    ON sales_leads (source, source_ref)
    WHERE source_ref IS NOT NULL;
```

Add a trigger to auto-update `updated_at`:

```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sales_leads_updated_at ON sales_leads;
CREATE TRIGGER sales_leads_updated_at
    BEFORE UPDATE ON sales_leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### Step 1.2 — Audit Scheduled Jobs & Lead Workflow

Review `scheduler/beat_schedule.py`. Confirm the existing `daily-lead-followup` job is present.

We will **add four new jobs** in Phase 3. Do not remove the existing job.

---

## PHASE 2 — CRM TOOL EXTENSIONS

### Step 2.1 — Extend `crm_ops.py`

File: `server/tools/database/crm_ops.py`

Add or update the following tool methods. Follow the existing `BaseTool` pattern — each method must return `{"success": True, "output": ...}` or `{"success": False, "error": ...}`.

#### `check_duplicate_lead(source: str, source_ref: str) → bool`

Query `sales_leads` for an existing row matching `(source, source_ref)`. Return `True` if duplicate found. Used to skip re-insertion during ingestion.

```python
async def check_duplicate_lead(source: str, source_ref: str) -> bool:
    result = await db.fetchrow(
        "SELECT id FROM sales_leads WHERE source = $1 AND source_ref = $2",
        source, source_ref
    )
    return result is not None
```

#### `create_lead_safe(lead_data: dict) → dict`

Like `create_lead` but first calls `check_duplicate_lead`. If duplicate, return `{"success": True, "skipped": True, "reason": "duplicate"}`. Otherwise insert and return `{"success": True, "skipped": False, "lead_id": ...}`.

#### `get_new_leads_summary(assigned_to: UUID | None, since: datetime) → list[dict]`

Return all leads created or updated since `since`, optionally filtered by `assigned_to`. Used for the daily status report.

#### `update_lead_status(lead_id: UUID, new_status: str, remarks: str | None, updated_by: UUID) → dict`

Update `status`, append to `notes` with timestamp prefix, set `last_status_update = NOW()`. Log to `audit_log`. Return updated lead record.

Valid status transitions (enforce via allowlist):
```
new → contacted | disqualified
contacted → qualified | closed_lost | disqualified
qualified → proposal | closed_lost | disqualified
proposal → closed_won | closed_lost
```

Reject invalid transitions with `{"success": False, "error": "Invalid status transition: X → Y"}`.

#### `bulk_assign_leads(lead_ids: list[UUID], assign_to: UUID, assigned_by: UUID) → dict`

Bulk update `assigned_to` on multiple leads. Log each assignment to `audit_log`.

---

## PHASE 3 — CELERY TASK IMPLEMENTATIONS

### File: `server/scheduler/tasks/sales_lead_tasks.py`

Create this new file. Import patterns should match the existing `tasks.py`. All tasks use `@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)`.

---

### Task 3.1 — Email Lead Ingestion

```
Task name: "sales.ingest_leads_from_email"
Trigger:   Celery Beat — Daily 01:00 UTC (= 09:00 HKT)
```

**Workflow:**

```
1. Determine date window: yesterday 00:00 HKT → yesterday 23:59 HKT (convert to UTC for Graph API filter)

2. For each mailbox in ["hello@mezzofy.com", "sales@mezzofy.com"]:
   a. Call outlook_read_emails(
        mailbox=address,
        received_after=window_start_utc,
        received_before=window_end_utc,
        folder="Inbox",
        max_results=100
      )
   b. For each email:
      - Skip if sender domain is @mezzofy.com (internal)
      - Skip if subject matches any spam/OOO pattern (regex list in config)
      - source_ref = email["id"]  (MS Graph message ID)
      - Check duplicate via check_duplicate_lead("email", source_ref)
      - If not duplicate:
          · Call LLM (Claude) with extraction prompt (see Prompt A below)
          · Parse JSON response → lead_data dict
          · Set lead_data["source"] = "email"
          · Set lead_data["source_ref"] = source_ref
          · Set lead_data["status"] = "new"
          · Call create_lead_safe(lead_data)

3. Collect counts: total_processed, inserted, skipped_duplicate, skipped_internal, failed

4. Post summary to MS Teams #sales:
   "📧 Email Lead Ingestion — {date}
    Mailboxes scanned: hello@, sales@
    New leads inserted: {inserted}
    Duplicates skipped: {skipped_duplicate}
    Internal/spam skipped: {skipped_internal}"

5. Audit log entry: source="scheduler", action="email_lead_ingestion", metadata={counts}
```

**Prompt A — LLM Lead Extraction from Email:**

```python
EXTRACT_LEAD_FROM_EMAIL_PROMPT = """
You are a sales data extractor. Given the following email, extract structured lead information.

Email Subject: {subject}
Email From: {from_name} <{from_email}>
Email Body:
{body_text}

Extract and return ONLY a valid JSON object with these fields:
{{
  "company_name": "string or null",
  "contact_name": "string or null",
  "contact_email": "string — use the sender email if not found in body",
  "contact_phone": "string or null",
  "industry": "string or null — infer from context if possible",
  "location": "string or null — city/country",
  "notes": "string — 1-2 sentence summary of the inquiry"
}}

Rules:
- If company_name cannot be determined, use the sender's email domain (strip TLD).
- Never invent information not present in the email.
- Return ONLY the JSON object, no explanation, no markdown fences.
"""
```

---

### Task 3.2 — Ticket Lead Ingestion

```
Task name: "sales.ingest_leads_from_tickets"
Trigger:   Celery Beat — Daily 01:00 UTC (= 09:00 HKT), runs AFTER email ingestion (add 5 min offset or use chain)
```

**Assumptions:**
- Contact form submissions are stored in a PostgreSQL table named `support_tickets`.
- The table has columns: `id`, `type` (= 'contact_form' | 'support' | ...), `subject`, `body`, `contact_name`, `contact_email`, `contact_phone`, `company`, `created_at`, `source_channel`.
- Only tickets with `type IN ('contact_form', 'new_lead', 'sales_inquiry')` are candidates.

> **If the tickets table schema differs, read the actual schema first via `query_db("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'support_tickets'")` and adapt accordingly.**

**Workflow:**

```
1. Determine date window: yesterday 00:00 HKT → yesterday 23:59 HKT

2. Query tickets:
   SELECT id, type, subject, body, contact_name, contact_email,
          contact_phone, company, source_channel, created_at
   FROM support_tickets
   WHERE type IN ('contact_form', 'new_lead', 'sales_inquiry')
     AND created_at BETWEEN $window_start AND $window_end

3. For each ticket:
   - source_ref = "ticket:" + str(ticket["id"])
   - Check duplicate via check_duplicate_lead("ticket", source_ref)
   - If not duplicate:
       · If body is substantial (>50 chars), call LLM for enrichment (Prompt B)
       · Otherwise use ticket fields directly
       · Build lead_data:
           company_name = ticket["company"] or LLM-extracted
           contact_name = ticket["contact_name"]
           contact_email = ticket["contact_email"]
           contact_phone = ticket["contact_phone"]
           industry = LLM-extracted or None
           location = LLM-extracted or None
           source = "ticket"
           source_ref = source_ref
           notes = f"Via {ticket['source_channel']} contact form. Subject: {ticket['subject']}"
           status = "new"
       · Call create_lead_safe(lead_data)

4. Post summary to MS Teams #sales:
   "📋 Ticket Lead Ingestion — {date}
    Tickets scanned: {total}
    New leads inserted: {inserted}
    Duplicates skipped: {skipped}"

5. Audit log entry
```

**Prompt B — LLM Lead Enrichment from Ticket:**

```python
EXTRACT_LEAD_FROM_TICKET_PROMPT = """
You are a sales data extractor. Given a website contact form submission, extract structured information.

Ticket Subject: {subject}
Contact Name: {contact_name}
Contact Email: {contact_email}
Message Body:
{body}

Extract and return ONLY a valid JSON object:
{{
  "company_name": "string or null",
  "industry": "string or null — infer from context",
  "location": "string or null — city/country",
  "notes": "string — 1-2 sentence summary of what they are looking for"
}}

Rules:
- If company not stated, infer from email domain.
- Never invent information.
- Return ONLY the JSON object.
"""
```

---

### Task 3.3 — Web / LinkedIn Lead Research

```
Task name:      "sales.research_new_leads"
Scheduled:      Celery Beat — Weekly, Monday 01:00 UTC (= Monday 09:00 HKT)
Manual trigger: POST /sales/leads/research  (see Phase 4 API endpoint)
```

**Workflow:**

```
1. Load research targets from config (config.yaml → sales.lead_research.targets):
   Each target defines:
     - query: "F&B companies Singapore"
     - source: "linkedin" | "web" | "both"
     - industry: "F&B"
     - location: "Singapore"
     - max_results: 20

   Default targets if config not set:
   [
     {"query": "loyalty program F&B Singapore", "source": "linkedin", "industry": "F&B", "location": "Singapore", "max_results": 15},
     {"query": "retail chain Hong Kong loyalty", "source": "linkedin", "industry": "Retail", "location": "Hong Kong", "max_results": 15},
     {"query": "mezzofy competitor customers asia", "source": "web", "industry": null, "location": "Asia", "max_results": 10}
   ]

2. For each target:
   a. If source includes "linkedin":
      - Call linkedin_search(query=target["query"], max_results=target["max_results"])
      - For each result: Call linkedin_extract(profile_url) if available
   b. If source includes "web":
      - Call scrape_url / extract_contact_info on top search results
   c. Deduplicate results within the batch (by company domain or LinkedIn URL)

3. For each discovered company/contact:
   - source_ref = linkedin_url OR website_domain OR company_name_slug
   - Check duplicate via check_duplicate_lead("linkedin"|"web", source_ref)
   - If not duplicate:
       · Call LLM (Prompt C) to assess lead quality and build structured record
       · If LLM scores lead quality < 3/5 → skip (log as low_quality)
       · Otherwise: create_lead_safe(lead_data)

4. Post summary to MS Teams #sales:
   "🔍 Lead Research — {date}
    Targets researched: {num_targets}
    Profiles discovered: {total_discovered}
    New leads inserted: {inserted}
    Low quality skipped: {low_quality}
    Duplicates skipped: {duplicates}"

5. Audit log entry: source="scheduler"|"manual", action="lead_research"
```

**Prompt C — LLM Lead Quality Assessment and Structuring:**

```python
ASSESS_AND_STRUCTURE_LEAD_PROMPT = """
You are a Mezzofy sales analyst. Mezzofy sells loyalty program and customer engagement SaaS to F&B, Retail, and service businesses in Asia-Pacific.

Evaluate the following discovered company/contact as a potential Mezzofy lead.

Company: {company_name}
Industry: {industry}
Location: {location}
Description: {description}
Website: {website}
LinkedIn URL: {linkedin_url}
Contact Name: {contact_name}
Contact Email: {contact_email}

Return ONLY a valid JSON object:
{{
  "company_name": "string",
  "contact_name": "string or null",
  "contact_email": "string or null",
  "contact_phone": "string or null",
  "industry": "string",
  "location": "string",
  "notes": "string — why this is a good lead, 1-2 sentences",
  "quality_score": integer 1-5,
  "quality_reason": "string — one sentence explanation of score"
}}

Scoring guide:
5 = Perfect fit (F&B/Retail chain, Asia, no obvious loyalty system)
4 = Good fit (right industry, right region)
3 = Possible fit (adjacent industry or unclear region)
2 = Weak fit (wrong industry or very small)
1 = Not a fit (B2B SaaS, government, wrong geography)

Return ONLY the JSON object.
"""
```

---

### Task 3.4 — Daily CRM Status Digest

```
Task name: "sales.daily_crm_digest"
Trigger:   Celery Beat — Daily 01:00 UTC (= 09:00 HKT)
```

**Workflow:**

```
1. Query new/updated leads:
   SELECT sl.*, u.name AS pic_name, u.email AS pic_email
   FROM sales_leads sl
   LEFT JOIN users u ON sl.assigned_to = u.id
   WHERE sl.created_at >= NOW() - INTERVAL '24 hours'
      OR sl.last_status_update >= NOW() - INTERVAL '24 hours'
   ORDER BY sl.created_at DESC

2. Group leads by assigned_to (PIC):
   - Group A: Unassigned (assigned_to IS NULL)
   - Group B-N: Each PIC UUID → their leads

3. Build overall digest (for #sales Teams channel):
   - Total new leads (last 24h)
   - Breakdown by source (email / ticket / linkedin / web)
   - Breakdown by status (new / contacted / qualified / proposal / closed_won / closed_lost)
   - Top 5 unassigned leads (company name + source + notes snippet)
   - Leads needing follow-up today (follow_up_date = today)

4. Post overall digest to MS Teams #sales channel

5. For each PIC with leads:
   - Build personalised email with their lead list (HTML table: company, status, last_contacted, follow_up_date, notes)
   - Include CTA link: "Update Status" → deep link to mobile app CRM screen for that lead
   - Send via outlook_send_email to pic_email

6. Push notification (optional, if PIC has mobile app):
   - "You have {n} leads needing attention today" → push via push_ops.py

7. Audit log entry: source="scheduler", action="daily_crm_digest"
```

---

## PHASE 4 — API ENDPOINTS

### File: `server/app/routers/sales_leads.py`

Create a new FastAPI router. Register it in `server/app/main.py` under the prefix `/sales/leads`.

All endpoints require JWT auth. RBAC rules:
- `sales_read`: GET endpoints (all sales staff)
- `sales_write`: PATCH/POST endpoints (own leads only for reps; all leads for managers)
- `sales_admin`: Bulk operations, manual triggers (managers and above)

---

#### `GET /sales/leads`

List leads. Query params:
- `status` — filter by status (optional)
- `assigned_to` — filter by PIC user_id (managers only; reps auto-filtered to self)
- `source` — filter by source
- `since` — ISO datetime filter on `created_at`
- `page`, `page_size` (default 20)

Response: `{ leads: [...], total: int, page: int }`

---

#### `GET /sales/leads/{lead_id}`

Get single lead detail. Sales reps can only fetch their own leads.

---

#### `PATCH /sales/leads/{lead_id}/status`

PIC updates status and/or adds remarks.

Request body:
```json
{
  "new_status": "contacted",
  "remarks": "Called John, interested in demo next week."
}
```

- Validate status transition via allowlist (reuse `update_lead_status` from crm_ops).
- Auto-set `last_contacted = NOW()` when transitioning away from `new`.
- Return updated lead record.

---

#### `PATCH /sales/leads/{lead_id}/assign`

Assign lead to a PIC. Managers only.

Request body:
```json
{ "assign_to": "user-uuid" }
```

---

#### `POST /sales/leads/research`

Manually trigger the Lead Research task (Task 3.3) as a Celery background task.

Request body (optional):
```json
{
  "targets": [
    { "query": "hotel loyalty Hong Kong", "source": "linkedin", "max_results": 10 }
  ]
}
```

If `targets` is omitted, use the default targets from config.

Response: `{ "task_id": "celery-task-uuid", "status": "queued" }`

The endpoint returns immediately. Client can poll `GET /tasks/{task_id}/status` for progress.

---

#### `GET /sales/leads/digest/preview`

Returns the same data the daily digest task would send, without actually sending emails/Teams messages. Useful for managers to preview. Managers only.

---

## PHASE 5 — CELERY BEAT SCHEDULE REGISTRATION

### File: `server/scheduler/beat_schedule.py`

Add the following entries to `beat_schedule`. All times in UTC:

```python
# Sales Lead Automation — added
"sales-email-lead-ingestion": {
    "task": "sales.ingest_leads_from_email",
    "schedule": crontab(hour=1, minute=0),          # 09:00 HKT daily
    "options": {"queue": "sales"},
},
"sales-ticket-lead-ingestion": {
    "task": "sales.ingest_leads_from_tickets",
    "schedule": crontab(hour=1, minute=10),         # 09:10 HKT daily (after email task)
    "options": {"queue": "sales"},
},
"sales-weekly-lead-research": {
    "task": "sales.research_new_leads",
    "schedule": crontab(hour=1, minute=0, day_of_week=1),  # Monday 09:00 HKT
    "options": {"queue": "sales"},
},
"sales-daily-crm-digest": {
    "task": "sales.daily_crm_digest",
    "schedule": crontab(hour=1, minute=30),         # 09:30 HKT daily (after ingestion completes)
    "options": {"queue": "sales"},
},
```

Also register the new task module in `celery_app.py`:

```python
celery_app.autodiscover_tasks([
    "scheduler.tasks.sales_lead_tasks",   # ← add this
    # ... existing tasks
])
```

---

## PHASE 6 — CONFIG EXTENSIONS

### File: `server/config/config.yaml`

Add the following block under the `sales:` section (create if missing):

```yaml
sales:
  lead_ingestion:
    email_mailboxes:
      - "hello@mezzofy.com"
      - "sales@mezzofy.com"
    internal_domain: "mezzofy.com"
    spam_subject_patterns:
      - "(?i)out of office"
      - "(?i)auto.?reply"
      - "(?i)delivery (failed|failure|status)"
      - "(?i)unsubscribe"
    ticket_lead_types:
      - "contact_form"
      - "new_lead"
      - "sales_inquiry"

  lead_research:
    enabled: true
    targets:
      - query: "loyalty program F&B Singapore"
        source: "linkedin"
        industry: "F&B"
        location: "Singapore"
        max_results: 15
      - query: "retail loyalty program Hong Kong"
        source: "linkedin"
        industry: "Retail"
        location: "Hong Kong"
        max_results: 15
      - query: "restaurant group loyalty Asia Pacific"
        source: "web"
        industry: "F&B"
        location: "Asia"
        max_results: 10
    min_quality_score: 3        # LLM quality score threshold (1-5)

  digest:
    teams_channel: "sales"
    send_pic_emails: true
    send_push_notifications: true
```

---

## PHASE 7 — LEAD LIFECYCLE WORKFLOW DEFINITION

Document the official Sales Lead Management Lifecycle in a new file for team reference.

### File: `server/knowledge/sales/lead_lifecycle.md`

```markdown
# Mezzofy Sales Lead Lifecycle

## Status Flow

new → contacted → qualified → proposal → closed_won
                                       → closed_lost
             ↓                    ↓         ↓
        disqualified         disqualified  disqualified

## Status Definitions

| Status        | Definition                                                    | Who Updates |
|---------------|---------------------------------------------------------------|-------------|
| new           | Lead ingested, not yet contacted. Auto-set on creation.       | System      |
| contacted     | First outreach sent (email, call, LinkedIn message).          | PIC         |
| qualified     | Lead confirmed interest and fits Mezzofy ICP.                 | PIC         |
| proposal      | Formal proposal or demo scheduled/completed.                  | PIC         |
| closed_won    | Deal signed. Customer onboarded.                              | PIC/Manager |
| closed_lost   | Lead declined or went with competitor.                        | PIC/Manager |
| disqualified  | Not a valid lead (wrong industry, spam, internal).            | PIC/System  |

## Lead Sources

| Source   | Ingestion Method                     | Schedule          |
|----------|--------------------------------------|-------------------|
| email    | Outlook inbox scan (hello@, sales@)  | Daily 09:00 HKT   |
| ticket   | Support tickets DB (contact forms)   | Daily 09:10 HKT   |
| linkedin | LinkedIn scraping + LLM research     | Weekly Mon 09:00  |
| web      | Web scraping + LLM research          | Weekly Mon 09:00  |
| referral | Manual entry by sales rep            | On demand         |
| manual   | Direct entry via mobile app          | On demand         |

## Assignment Rules

- All ingested leads start as `assigned_to = NULL`.
- Sales Manager assigns leads to reps via mobile app or bulk assign endpoint.
- Unassigned leads are flagged daily in the CRM digest.
- Reps may only update status and remarks on leads assigned to them.
- Managers can reassign at any time.

## Deduplication

- Each lead has a `source_ref` (email Message ID, ticket ID, LinkedIn URL, or domain).
- System enforces `UNIQUE(source, source_ref)` at DB level.
- Duplicate attempts are silently skipped and logged.
```

---

## PHASE 8 — TESTING

### File: `tests/workflows/test_sales_lead_automation.py`

Write pytest tests for:

```python
# 1. Test email ingestion task
async def test_email_lead_ingestion_inserts_new_lead():
    # Mock outlook_read_emails to return 1 email
    # Mock LLM to return valid JSON lead
    # Assert create_lead_safe called once
    # Assert Teams message posted

async def test_email_lead_ingestion_skips_duplicate():
    # Pre-insert a lead with matching source_ref
    # Mock outlook_read_emails to return same email
    # Assert no new lead inserted

async def test_email_lead_ingestion_skips_internal():
    # Email from name@mezzofy.com
    # Assert skipped, no LLM call

# 2. Test ticket ingestion
async def test_ticket_lead_ingestion_inserts_new_lead():
    # Insert a test ticket row
    # Run task
    # Assert lead created in sales_leads

# 3. Test status update API
async def test_patch_lead_status_valid_transition():
    # Create lead with status="new"
    # PATCH with new_status="contacted"
    # Assert 200, status updated, notes appended

async def test_patch_lead_status_invalid_transition():
    # Create lead with status="new"
    # PATCH with new_status="closed_won"  (invalid jump)
    # Assert 400, error message

# 4. Test dedup index
async def test_dedup_index_prevents_duplicate():
    # Insert lead with source="email", source_ref="msg_001"
    # Attempt second insert same source_ref
    # Assert IntegrityError caught and skipped

# 5. Test manual research trigger
async def test_manual_research_trigger():
    # POST /sales/leads/research
    # Assert 202, task_id returned
    # Assert Celery task enqueued
```

---

## IMPLEMENTATION NOTES

1. **LLM calls in background tasks:** Use `anthropic_client.py` with the existing retry/backoff logic. Model: `claude-3-5-haiku-20241022` for extraction tasks (speed + cost). Claude Sonnet for quality scoring in research task.

2. **Error handling:** Each task must catch exceptions per-item and continue processing. A single bad email must not abort the entire ingestion batch. Collect errors and include in the Teams summary.

3. **Idempotency:** Tasks are idempotent by design — re-running will skip duplicates. Safe to retry on failure.

4. **Rate limits:**
   - MS Graph Outlook read: max 100 emails per call, paginate if needed.
   - LinkedIn scraping: max 50 profiles per session (enforced in `linkedin_ops.py`).
   - LLM calls: batch with `asyncio.gather` with semaphore limit of 5 concurrent calls.

5. **Timezone handling:** Always store datetimes in UTC in PostgreSQL. Convert to HKT only for display in Teams messages and email bodies. Use `pytz.timezone("Asia/Hong_Kong")` for conversion.

6. **Logging:** Every task must log start/end with `logger.info(f"[Task] {task_name} started | run_id={self.request.id}")`. Log counts at completion.

7. **Audit trail:** Every lead insertion and status change must create an entry in `audit_log` with `source="scheduler"` or `source="mobile"` and the relevant `user_id`.

8. **Queue isolation:** All sales tasks run on the `sales` Celery queue. Ensure the Celery worker is started with `--queues sales,default` or configure a dedicated worker.

---

## FILE CREATION CHECKLIST

By the end of this implementation, the following files should exist or be modified:

```
Modified:
  scripts/migrate.py                              ← Schema additions (Phase 1)
  server/tools/database/crm_ops.py               ← New tool methods (Phase 2)
  server/scheduler/beat_schedule.py              ← 4 new scheduled jobs (Phase 5)
  server/scheduler/celery_app.py                 ← Autodiscover new task module
  server/config/config.yaml                      ← sales: block (Phase 6)
  server/app/main.py                             ← Register new router

Created:
  server/scheduler/tasks/sales_lead_tasks.py     ← All 4 Celery tasks (Phase 3)
  server/app/routers/sales_leads.py              ← API endpoints (Phase 4)
  server/knowledge/sales/lead_lifecycle.md       ← Lifecycle documentation (Phase 7)
  tests/workflows/test_sales_lead_automation.py  ← Tests (Phase 8)
```

---

## EXECUTION ORDER FOR CLAUDE CODE

Feed this prompt once. Then implement in this exact order:

1. `scripts/migrate.py` — schema changes
2. `server/tools/database/crm_ops.py` — tool methods
3. `server/scheduler/tasks/sales_lead_tasks.py` — all 4 tasks
4. `server/app/routers/sales_leads.py` — API router
5. `server/scheduler/beat_schedule.py` — schedule entries
6. `server/scheduler/celery_app.py` — autodiscover
7. `server/config/config.yaml` — config block
8. `server/app/main.py` — router registration
9. `server/knowledge/sales/lead_lifecycle.md` — documentation
10. `tests/workflows/test_sales_lead_automation.py` — tests

After each file, confirm it was written successfully before moving to the next.
