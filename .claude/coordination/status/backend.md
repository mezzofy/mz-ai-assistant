# Context Checkpoint: Backend Agent
**Date:** 2026-03-11
**Project:** mz-ai-assistant
**Session:** 17 (FEAT-013/BUG-013 — Contacts + diagnostic + write logging)
**Context:** ~30% at checkpoint

## Completed This Session (Session 17)

- ✅ `config.py` → Added `Contacts.Read` + `Contacts.ReadWrite` to `MS365_DELEGATED_SCOPES`
- ✅ `personal_ms_ops.py` → 4 new contact tools (get/search/detail/create), `personal_check_token_scopes` diagnostic, ERROR logging on all write handler failures
- ✅ `llm_manager.py` → "Contacts" added to personal MS capabilities in system prompt
- Commit: `36bf87f`

## Notes
- Tool count: 18 → 24 (5 new tools)
- User must disconnect + reconnect MS account to get Contacts scopes
- Use `personal_check_token_scopes` in Chat to diagnose write scope issues

---

<!-- Previous session below -->
**Session:** 16 (BUG-010 — MS OAuth scope fix)
**Context:** ~10% at checkpoint
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
