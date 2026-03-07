# Plan: HRAgent Companion Config — Backend Tasks

**Date:** 2026-03-07
**Agent:** Backend Agent
**Status:** Ready to implement
**Commit target:** Same EC2 deploy batch as task-lifecycle fix (b320cf6)

---

## Context

`hr_agent.py` was committed in a previous session. It is fully functional code but cannot be
activated because 4 config/support files still reference only the original 5 departments.
These gaps would cause runtime errors:

| Gap | Impact at runtime |
|-----|-------------------|
| `hr` missing from `roles.yaml` departments | JWT auth rejects HR users |
| `hr_viewer`/`hr_manager` missing from `rbac.py` VALID_ROLES | User creation/validation rejects HR roles |
| `hr` missing from `rbac.py` VALID_DEPARTMENTS | Department-scoped queries reject HR |
| No `notifications.hr_manager_email` in `config.example.yaml` | Weekly summary skips email silently (already guarded, but config template is wrong) |
| No `hr` in `config.example.yaml` `agents.available` | HR agent not started on EC2 |
| No `hr` in `teams.channels` in `config.example.yaml` | Teams delivery to `#hr` fails at channel lookup |
| No HR beat jobs in `beat_schedule.py` | Automated weekly/monthly reports never fire |

---

## Files to Modify (Backend Agent Only)

| # | File | Change |
|---|------|--------|
| 1 | `server/config/roles.yaml` | Add `hr` dept; `hr_viewer` / `hr_manager` roles; permission_tool_map entries |
| 2 | `server/app/core/rbac.py` | Add `hr_viewer`, `hr_manager` to VALID_ROLES; `hr` to VALID_DEPARTMENTS |
| 3 | `server/app/tasks/beat_schedule.py` | Add 2 HR scheduled jobs |
| 4 | `server/config/config.example.yaml` | Add `teams.channels.hr`, `notifications` section, `hr` in `agents.available` |

One additional file has a minor update needed:
| 5 | `server/app/tools/communication/teams_ops.py` | Add `hr` to `teams_read_messages` enum (consistency) |

---

## Task 1 — `server/config/roles.yaml`

### 1A — Add `hr` to departments list

```yaml
departments:
  - finance
  - sales
  - marketing
  - support
  - management
  - hr                    # ADD THIS
```

### 1B — Add HR roles block (after support_manager, before management)

```yaml
  # ── HR Department ─────────────────────────────────────────
  hr_viewer:
    department: hr
    permissions:
      - hr_read

  hr_manager:
    department: hr
    permissions:
      - hr_read
      - hr_write
      - email_send
      - calendar_access
      - scheduler_manage         # Can create scheduled HR reports
```

### 1C — Add `hr_read` to executive role permissions

The `executive` role should have read access to all departments.
Add `hr_read` after `support_read`:

```yaml
  executive:
    department: management
    permissions:
      - management_read
      - management_admin
      - finance_read
      - sales_read
      - marketing_read
      - support_read
      - hr_read                  # ADD THIS — executive can view HR data
      - audit_read
      - email_send
      - calendar_access
      - scheduler_manage
      - teams_post
```

### 1D — Add HR entries to `permission_tool_map`

Append after `management_read` block (before end of file):

```yaml
  hr_read:
    - query_analytics            # Used by hr_agent for leave, payroll, recruitment queries
    - query_hr_data
  hr_write:
    - update_hr_record
```

---

## Task 2 — `server/app/core/rbac.py`

### 2A — Add HR roles to VALID_ROLES (lines 80–86)

Old:
```python
VALID_ROLES = {
    "finance_viewer", "finance_manager",
    "sales_rep", "sales_manager",
    "marketing_creator", "marketing_manager",
    "support_agent", "support_manager",
    "executive", "admin",
}
```

New:
```python
VALID_ROLES = {
    "finance_viewer", "finance_manager",
    "sales_rep", "sales_manager",
    "marketing_creator", "marketing_manager",
    "support_agent", "support_manager",
    "hr_viewer", "hr_manager",
    "executive", "admin",
}
```

### 2B — Add `hr` to VALID_DEPARTMENTS (line 88)

Old:
```python
VALID_DEPARTMENTS = {"finance", "sales", "marketing", "support", "management"}
```

New:
```python
VALID_DEPARTMENTS = {"finance", "sales", "marketing", "support", "management", "hr"}
```

---

## Task 3 — `server/app/tasks/beat_schedule.py`

Add two jobs inside `STATIC_BEAT_SCHEDULE`, after the `weekly-support-summary` block
(before the closing `}`):

### 3A — Weekly HR summary (Friday 5PM SGT = 09:00 UTC)

```python
    # Weekly HR summary — Friday 5PM SGT (09:00 UTC)
    "weekly-hr-summary": {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=9, minute=0, day_of_week=5),  # 5PM SGT = 09:00 UTC
        "args": [{
            "agent": "hr",
            "source": "scheduler",
            "department": "hr",
            "user_id": "system",
            "event": "weekly_hr_summary",
            "message": "Generate weekly HR summary covering headcount, leave, recruitment, and payroll",
            "deliver_to": {
                "teams_channel": "hr",
            },
        }],
    },
```

### 3B — Monthly headcount report (1st of month 9AM SGT = 01:00 UTC)

```python
    # Monthly headcount report — 1st of month 9AM SGT (01:00 UTC)
    "monthly-headcount": {
        "task": "app.tasks.tasks.process_agent_task",
        "schedule": crontab(hour=1, minute=0, day_of_month=1),  # 9AM SGT = 01:00 UTC
        "args": [{
            "agent": "hr",
            "source": "scheduler",
            "department": "hr",
            "user_id": "system",
            "event": "monthly_headcount",
            "message": "Generate monthly headcount report with department breakdown and attrition analysis",
            "deliver_to": {
                "teams_channel": "hr",
            },
        }],
    },
```

**Note on `event` field:** `hr_agent.execute()` checks `task.get("event", "")` with
`if "weekly_hr_summary" in event` and `if "monthly_headcount" in event`. These exact
event strings must be present in the args dict for scheduler routing to work.

---

## Task 4 — `server/config/config.example.yaml`

### 4A — Add `hr` channel to `teams.channels` (after `management:`)

```yaml
  channels:
    general: "19:general@thread.tacv2"
    sales: "19:sales@thread.tacv2"
    finance: "19:finance@thread.tacv2"
    marketing: "19:marketing@thread.tacv2"
    support: "19:support@thread.tacv2"
    management: "19:management@thread.tacv2"
    hr: "19:hr@thread.tacv2"           # ADD THIS
```

### 4B — Add `notifications` section

Add after the `teams:` block and before `celery:`:

```yaml
# Notifications
notifications:
  hr_manager_email: "${HR_MANAGER_EMAIL}"   # Recipient for weekly HR summary + monthly headcount emails
```

### 4C — Add `hr` to `agents.available`

Old:
```yaml
agents:
  enabled: true
  auto_select: true
  available:
    - finance
    - sales
    - marketing
    - support
    - management
```

New:
```yaml
agents:
  enabled: true
  auto_select: true
  available:
    - finance
    - sales
    - marketing
    - support
    - management
    - hr
```

---

## Task 5 — `server/app/tools/communication/teams_ops.py`

### 5A — Add `hr` to `teams_read_messages` enum

Two places in `get_tools()`:

**In description string** (line ~134):
```python
"description": "Channel to read. One of: general, sales, finance, marketing, support, management, hr.",
```

**In enum list** (line ~135):
```python
"enum": ["general", "sales", "finance", "marketing", "support", "management", "hr"],
```

---

## EC2 Deployment After These Changes

After Backend Agent completes and commits:

```bash
ssh -i mz-ai-key.pem ubuntu@3.1.255.48
cd /home/ubuntu/mz-ai-assistant
git pull

# Add HR_MANAGER_EMAIL to .env
echo "HR_MANAGER_EMAIL=hr-manager@mezzofy.com" >> server/.env

# Restart API + workers
sudo systemctl restart mezzofy-api
sudo systemctl restart mezzofy-celery-worker
sudo systemctl restart mezzofy-celery-beat
```

---

## Verification Checklist

- [ ] `python -c "from app.core.rbac import VALID_ROLES; assert 'hr_manager' in VALID_ROLES"` passes
- [ ] `python -c "from app.core.rbac import VALID_DEPARTMENTS; assert 'hr' in VALID_DEPARTMENTS"` passes
- [ ] `python -c "from app.tasks.beat_schedule import STATIC_BEAT_SCHEDULE; assert 'weekly-hr-summary' in STATIC_BEAT_SCHEDULE"` passes
- [ ] HR user with role `hr_manager` can authenticate and receive `hr_read`, `hr_write` permissions in JWT
- [ ] Celery Beat log shows `weekly-hr-summary` and `monthly-headcount` in schedule at startup
- [ ] `config.example.yaml` has `teams.channels.hr`, `notifications.hr_manager_email`, `hr` in `agents.available`
