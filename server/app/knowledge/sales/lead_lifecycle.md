# Mezzofy Sales Lead Lifecycle

## Status Flow

```
new → contacted → qualified → proposal → closed_won
                                       → closed_lost
             ↓                    ↓         ↓
        disqualified         disqualified  disqualified
```

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

## Valid Transitions

| From      | To (allowed)                              |
|-----------|-------------------------------------------|
| new       | contacted, disqualified                   |
| contacted | qualified, closed_lost, disqualified      |
| qualified | proposal, closed_lost, disqualified       |
| proposal  | closed_won, closed_lost                   |

Any other transition is rejected by the API with HTTP 400.

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
- The `check_duplicate_lead(source, source_ref)` method in `crm_ops.py` is called before every ingestion.

## Scheduled Tasks

| Task Name                        | Schedule         | Queue |
|----------------------------------|------------------|-------|
| sales.ingest_leads_from_email    | Daily 01:00 UTC  | sales |
| sales.ingest_leads_from_tickets  | Daily 01:10 UTC  | sales |
| sales.research_new_leads         | Mon 01:00 UTC    | sales |
| sales.daily_crm_digest           | Daily 01:30 UTC  | sales |

All times are UTC. HKT = UTC+8, so 01:00 UTC = 09:00 HKT.

## API Endpoints

| Method | Path                              | Permission    | Description                       |
|--------|-----------------------------------|---------------|-----------------------------------|
| GET    | /sales/leads                      | sales_read    | List leads (reps: own only)       |
| GET    | /sales/leads/{id}                 | sales_read    | Single lead (reps: own only)      |
| PATCH  | /sales/leads/{id}/status          | sales_write   | Update status + remarks           |
| PATCH  | /sales/leads/{id}/assign          | sales_admin   | Assign to PIC                     |
| POST   | /sales/leads/research             | sales_admin   | Enqueue research task             |
| GET    | /sales/leads/digest/preview       | sales_admin   | Preview digest without sending    |
