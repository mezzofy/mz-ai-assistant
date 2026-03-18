# Release Notes — v1.32.0
**Date:** 2026-03-18
**Branch:** eric-design
**Commit:** 548b202
**Type:** Bug Fix + Feature

---

## Summary

Implements shared folder delivery for scheduled tasks (BUG-022). Users can now configure scheduled jobs to save output files directly to a department's shared folder. The mobile app correctly displays the delivery target instead of showing "→ No delivery configured".

---

## Changes

### Backend

**`server/app/webhooks/scheduler.py`**
- Added `SharedFolderDTO` model: `department`, `filename_template`, `file_extension` (default `"txt"`)
- Extended `DeliverToDTO` with optional `shared_folder: SharedFolderDTO` field
- Pydantic previously silently stripped unknown `shared_folder` fields — now persisted to DB on create/update

**`server/app/tasks/webhook_tasks.py`**
- Added shared folder delivery block in `_deliver_results_async()`
- Resolves `DDMMYY` placeholder in filename template to actual run date (`%d%m%y`)
- Writes content to `{artifacts_dir}/{department}/shared/{filename}`
- Registers file in `artifacts` table with `scope="department"` for discovery by `/files/` endpoint

**`server/app/tools/scheduler/scheduler_ops.py`**
- Added two optional tool parameters: `deliver_to_shared_folder_dept` and `deliver_to_filename_template`
- LLM can now create jobs with shared folder delivery via chat (e.g. "save results to sales shared folder as Leads_DDMMYY")

### Mobile

**`APP/src/api/schedulerApi.ts`**
- Extended `ScheduledJob.deliver_to` TypeScript interface with `shared_folder?: { department, filename_template, file_extension? }`

**`APP/src/screens/ScheduleStatsScreen.tsx`**
- Updated `renderDelivery()` with shared folder handler: renders `→ Sales Shared Folder > Leads_DDMMYY.txt`
- Restored `→ No delivery configured` fallback — only shown when **no** delivery is configured (previously removed in `7fecc89`, now correctly scoped)

### Tests

**`server/tests/test_shared_folder_delivery.py`** *(new file)*
- 12 new unit tests covering:
  - `DeliverToDTO` accepts `shared_folder` field and validates defaults
  - `_deliver_results_async()` writes file to correct path and registers artifact
  - Filename template substitution (`DDMMYY` → actual date)
  - `SchedulerOps` tool builds correct `deliver_to` dict with/without shared folder params

---

## Root Cause (BUG-022)

`DeliverToDTO` had no `shared_folder` field. Pydantic silently discarded it on `model_dump()` → `deliver_to` was always saved as `{}` to DB. Mobile had no renderer for the config even if it had been saved.

---

## Migration

**None required.** Existing jobs with `deliver_to = {}` are unaffected.

Job `42f42228` ("Daily Sales Inbox Lead Scan") must be patched manually after deploy:
```bash
# Via AI chat (recommended):
# "Update job 42f42228 deliver_to: sales shared folder, filename Leads_DDMMYY"

# Or direct API call:
curl -X PUT https://<server>/scheduler/jobs/42f42228 \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"deliver_to": {"shared_folder": {"department": "sales", "filename_template": "Leads_DDMMYY", "file_extension": "txt"}}}'
```

---

## Test Results

| Suite | Passed | Notes |
|-------|--------|-------|
| Unit (new) | 12/12 | All shared folder tests pass |
| Unit (full) | 419 passed, 14 pre-existing failures | `croniter` not installed locally — EC2 has it |
| E2E | Not run locally | Requires live server on EC2 |

---

## Deployment Steps

1. `git push origin eric-design` (or merge to main)
2. SSH to EC2: `ssh -i mz-ai-key.pem ubuntu@3.1.255.48`
3. `cd /home/ubuntu/mz-ai-assistant && git pull`
4. `sudo systemctl restart mezzofy-api.service`
5. `sudo systemctl restart mezzofy-celery.service`
6. Verify: `sudo systemctl status mezzofy-api.service`
7. Patch job `42f42228` deliver_to (see Migration above)
8. Trigger job manually via AI chat to verify file appears in `/var/mezzofy/artifacts/sales/shared/`

---

## Verification Checklist

- [ ] Mobile shows `→ Sales Shared Folder > Leads_DDMMYY.txt` for job `42f42228`
- [ ] `run_now` on job `42f42228` creates `Leads_XXXXXX.txt` in sales shared folder
- [ ] File appears in mobile Files tab → Department → Sales
- [ ] Jobs `fbeba62d` and `c466dbb8` (Teams delivery) display unchanged
- [ ] `→ No delivery configured` shown for jobs with empty `deliver_to`

---

## Version Bump

**Target:** v1.32.0
**Previous:** v1.31.0 (BUG-022 webhook push fix)
