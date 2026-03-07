# Context Checkpoint: Backend Agent
**Date:** 2026-03-07
**Project:** mz-ai-assistant
**Session:** 15 (HRAgent companion config)
**Context:** ~30% at checkpoint
**Reason:** Task complete

## Completed This Session
- ✅ `server/config/roles.yaml` — added `hr` to departments; `hr_viewer` + `hr_manager` roles; `hr_read` on executive; `hr_read`/`hr_write` in permission_tool_map
- ✅ `server/app/core/rbac.py` — added `"hr_viewer"`, `"hr_manager"` to VALID_ROLES; `"hr"` to VALID_DEPARTMENTS
- ✅ `server/app/tasks/beat_schedule.py` — added `weekly-hr-summary` (Fri 5PM SGT / 09:00 UTC) and `monthly-headcount` (1st of month 9AM SGT / 01:00 UTC)
- ✅ `server/config/config.example.yaml` — added `teams.channels.hr`, `notifications.hr_manager_email`, `hr` in `agents.available`
- ✅ `server/app/tools/communication/teams_ops.py` — added `hr` to `teams_read_messages` enum
- ✅ Committed: `7cc5187`

## Decisions Made
- `hr_viewer` gets only `hr_read` (read-only, like `finance_viewer`)
- `hr_manager` gets `hr_read + hr_write + email_send + calendar_access + scheduler_manage` (matches `finance_manager` / `support_manager` pattern)
- `executive` gets `hr_read` (consistent with cross-department read access for all other depts)
- Beat job `event` field uses `"weekly_hr_summary"` / `"monthly_headcount"` — exact strings that `hr_agent.execute()` checks with `in`

## Files Modified
- `server/config/roles.yaml` (modified)
- `server/app/core/rbac.py` (modified)
- `server/app/tasks/beat_schedule.py` (modified)
- `server/config/config.example.yaml` (modified)
- `server/app/tools/communication/teams_ops.py` (modified)

## Status
All tasks complete. No follow-up needed from Backend Agent.
EC2 deploy requires: `git pull` + add `HR_MANAGER_EMAIL` to `.env` + restart 3 services.
