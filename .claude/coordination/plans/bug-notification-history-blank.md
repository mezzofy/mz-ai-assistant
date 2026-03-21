# Bug Fix: Notification History Blank (BUG-023)
**Workflow:** bug-fix
**Date:** 2026-03-21
**Created by:** Lead Agent
**Priority:** Medium — UX defect, data not shown

## Symptom
User receives FCM push notification on Android device ("Task Ready — Draft a Merchant Buyer Agreement for Singapore") but the Notification History screen in the mobile app shows "No notifications yet".

## Root Cause

Two separate issues work together to cause this:

### Issue A — `tasks.py` calls `_send_push` (private method) not `send_push` (module-level helper)

`process_chat_task()` and `process_agent_task()` in `tasks.py` import and call `_send_push` (or use a local alias). The module-level `send_push()` function in `push_ops.py` is the one that calls `log_notification()` after FCM delivery. If `tasks.py` is bypassing `send_push()` and calling a different path, `log_notification()` is never called.

### Issue B — `log_notification()` is inside `if result.get("success"):` block

Even on the correct `send_push()` path, `log_notification()` is only called if FCM returns `success: True`. If any exception occurs before or during that check, the log entry is silently skipped. The notification reaches the device but history is never written.

### Why it's silent
`log_notification()` itself has a try/except that logs a warning and continues — so even if it IS called and fails (e.g., DB connection error, wrong user_id type), no error surfaces.

## The Fix

### Fix 1 — `push_ops.py`: Move `log_notification()` outside the success guard

The history should record every notification we **attempt** to send (especially ones that succeed). Change:

```python
# BEFORE
if result.get("success"):
    await log_notification(user_id=user_id, title=title, body=body, data=data)

# AFTER
await log_notification(user_id=user_id, title=title, body=body, data=data)
```

This ensures history is populated regardless of FCM result quirks.

### Fix 2 — `tasks.py`: Ensure push calls go through `send_push()` (the module-level function with logging)

Check `process_chat_task()` and `process_agent_task()` in `tasks.py`. Every push notification send must call the **module-level `send_push()`** (from `push_ops.py`) — NOT `ops._send_push()` or any other path. The module-level `send_push()` is the one that calls `log_notification()`.

If the code currently calls `_send_push(...)` (underscore) or calls `PushOps(config)._send_push(...)` directly, change it to use `send_push(user_id=..., device_token=..., ...)` from the module-level import.

### Fix 3 — `push_ops.py`: Add debug logging before log_notification call

Add a `logger.debug(f"log_notification: user_id={user_id}, title={title}")` line just before the `log_notification()` call so future issues are visible in EC2 logs.

## Files to Modify

| File | Change |
|------|--------|
| `server/app/tools/notification/push_ops.py` (or `server/app/tools/communication/push_ops.py`) | Move `log_notification()` outside `if result.get("success"):` block; add debug log |
| `server/app/tasks/tasks.py` | Ensure `send_push()` module-level function is used (not private method) in `process_chat_task` and `process_agent_task` |

## Acceptance Criteria
- [ ] After fix: sending a push notification via chat task causes a row to appear in `notification_log` table
- [ ] `GET /notifications/history` returns the logged notification
- [ ] Mobile Notification History screen displays the notification
- [ ] No new crash paths introduced
- [ ] Fallback: if `log_notification()` itself fails (DB down), push still sends (try/except stays)

## Verification SQL (run on EC2 after fix)
```sql
SELECT * FROM notification_log ORDER BY sent_at DESC LIMIT 5;
```
Should show rows after next push is triggered.
