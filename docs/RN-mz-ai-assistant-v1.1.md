# Release Notes — Mezzofy AI Assistant v1.1
**Release Date:** 2026-03-06
**Type:** Feature Release
**Prepared by:** Docs Agent

---

## Overview

Mezzofy AI Assistant v1.1 adds the HR department agent — the 6th department agent on the platform. This release enables HR staff to query payroll, leave, and recruitment data via natural language, and introduces two new automated scheduler jobs and three new webhook event handlers for HR lifecycle events.

---

## What's New

### HR Agent (`hr_agent.py`)

A new department agent handling all HR domain queries and workflows:

- **Payroll queries:** "Show me the payroll summary for March" — queries `payroll_summary` metric from DatabaseOps and returns an LLM-formatted summary
- **Leave and attendance:** "How many leave days do I have?" — queries `leave_attendance` metric and highlights anomalies
- **Recruitment pipeline:** "What's our current hiring pipeline?" — queries `recruitment_pipeline` metric and summarizes open roles, candidate stages, and key metrics
- **General HR queries:** Non-domain messages fall back to `_general_response()` (shared BaseAgent pattern)

### New Scheduler Jobs

| Job Name | Schedule | Action |
|----------|----------|--------|
| `weekly-hr-summary` | Friday 5PM SGT | Queries leave, recruitment, and payroll metrics → PDF → post to #hr Teams channel + email HR manager |
| `monthly-headcount` | 1st of month, 9AM SGT | Queries `headcount_monthly` metric → headcount PDF (dept breakdown, MoM changes, attrition rate) → email HR manager |

Both jobs follow the existing `source="scheduler"` audit log pattern.

### New Webhook Events

| Event | Handler | Action |
|-------|---------|--------|
| `employee_onboarded` | HR Agent | Generates onboarding checklist PDF (IT setup, access, training, 30/60/90-day milestones) → post to #hr Teams channel |
| `employee_offboarded` | HR Agent | Generates exit summary PDF (knowledge transfer, access revocation, equipment return) → post to #hr Teams channel |
| `leave_request_submitted` | HR Agent | Routed to HR Agent for processing |

All webhook handlers follow the existing 200-first pattern (acknowledge → Celery enqueue → async process).

### Router Updates

`server/app/router.py` updated with HR webhook event routing. The three new events map to `"hr"` in the webhook agent dispatch table.

### Agent Registry

`server/app/agents/agent_registry.py` updated:

```python
AGENT_MAP = {
    "finance":    FinanceAgent,
    "hr":         HRAgent,
    "sales":      SalesAgent,
    "marketing":  MarketingAgent,
    "support":    SupportAgent,
    "management": ManagementAgent,
}
```

---

## Test Coverage

- **New tests:** 28 tests in `server/tests/test_hr_agent.py` (all passing)
- **Total suite:** 288 tests passing, 0 failing
- **Test categories:** `can_handle()` routing, payroll/leave/recruitment workflows, scheduler jobs, webhook handlers, permission checks, general fallback

---

## Migration Notes

The following companion configuration changes are **required** and are pending implementation by the Backend Agent:

| File | Change Required |
|------|----------------|
| `server/config/roles.yaml` | Add `hr_viewer` and `hr_manager` roles with `hr_read` / `hr_write` / `email_send` permissions |
| `server/app/core/rbac.py` | Add `"hr"` to `VALID_DEPARTMENTS` and `"hr_viewer"` / `"hr_manager"` to `VALID_ROLES` |
| `server/app/tasks/beat_schedule.py` | Add `weekly-hr-summary` and `monthly-headcount` static jobs to the beat schedule |
| `server/config/config.example.yaml` | Add HR agent section, `#hr` Teams channel ID, and HR manager email for notifications |

Until `roles.yaml` and `rbac.py` are updated, HR users will not have `hr_viewer` / `hr_manager` roles and JWT tokens will not carry `hr_read` / `hr_write` permissions. The agent code is fully functional; the permission gates require the config changes.

---

## Infrastructure Requirements

No new infrastructure changes. Same requirements as v1.0.

---

## Known Limitations (v1.1)

All v1.0 limitations remain (see `RN-mz-ai-assistant-v1.0.md`). Additional v1.1 limitations:

| Limitation | Impact | Planned Fix |
|------------|--------|-------------|
| Companion config changes pending | HR roles not yet in `roles.yaml` / `rbac.py`; Beat jobs not yet in `beat_schedule.py` | Backend Agent task |
| HR webhook events not yet in `webhooks.py` allowed-events list | `employee_onboarded` / `employee_offboarded` / `leave_request_submitted` may be rejected by webhook validation | Backend Agent task |

---

## Upgrade Notes

**From v1.0:** No database schema changes. No new tables required. Upgrade steps:

1. Deploy new server code (pull latest, restart `mezzofy-api.service`)
2. Apply companion config changes listed in Migration Notes above
3. Restart Celery Beat to activate the two new scheduled jobs

---

*Mezzofy AI Assistant v1.1 · Released 2026-03-06*
*Built by Mezzofy Engineering Team*
