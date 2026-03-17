# Plan: BUG — Notification History Empty

## Date
2026-03-17

## Root Cause

`notification_log` table was added in v1.30.0 but `migrate.py` was never run on EC2 after that deploy.

`log_notification()` in `push_ops.py` fails silently (bare try/except), so:
- FCM push IS delivered → device receives it ✅
- DB INSERT fails (table not found) → swallowed → nothing logged
- `GET /notifications/history` returns `[]` → screen shows "No notifications yet"

Secondary: stale comment in `push_ops.py` lines 263–264 references pre-Session-19 behavior (says `webhook_tasks.py` calls `_send_push()` directly, but that was fixed in Session 19).

## Fix

### Phase 1: EC2 Migration (Human Action — do this NOW)

SSH to EC2 and run:

```bash
cd /home/ubuntu/mz-ai-assistant/server
source venv/bin/activate
python scripts/migrate.py
```

Expected output:
```
  ✅ notification_log
  ✅ idx_notification_log_user
```

This creates the table with `CREATE TABLE IF NOT EXISTS` — safe to re-run.

No service restart needed after migration.

### Phase 2: Backend — Remove Stale Comment (1 file, 1 edit)

**File:** `server/app/tools/communication/push_ops.py`

Remove lines 263–264 (the stale NOTE comment):
```python
    # NOTE: webhook_tasks.py calls PushOps._send_push() directly and does not go
    # through this function — that path does not log to notification_log in v1.30.0.
```

This was true in v1.30.0 but was fixed in Session 19 (commit 320d979). The comment is now wrong and misleading.

After removing: commit + push to GitHub, then `git pull` on EC2. No service restart needed (comment-only change).

## Verification (After Phase 1)

1. SSH to EC2 and confirm table exists:
   ```bash
   sudo -u postgres psql -d mezzofy_ai -c "SELECT COUNT(*) FROM notification_log;"
   ```
   Expected: `0` (empty but table exists)

2. Trigger a push notification (e.g., run a scheduled task or chat task that completes)

3. Check table has a row:
   ```bash
   sudo -u postgres psql -d mezzofy_ai -c "SELECT title, body, sent_at FROM notification_log ORDER BY sent_at DESC LIMIT 5;"
   ```

4. Open Notification History screen on mobile → should show the notification

## Files to Modify

| File | Change |
|------|--------|
| `server/app/tools/communication/push_ops.py` | Remove stale comment (lines 263–264) |

No DB schema changes (migration is additive `CREATE TABLE IF NOT EXISTS`).
No API changes.
No mobile changes.

## Agent Assignment

**Phase 1:** Human action only — run `migrate.py` on EC2.

**Phase 2:** Backend Agent (1 file, trivial edit):
```
Open a new terminal → run /boot-backend

Backend tasks:
1. Remove stale comment in server/app/tools/communication/push_ops.py lines 263–264
2. Commit and push
```

After Backend completes: `git pull` on EC2. No restarts needed.
