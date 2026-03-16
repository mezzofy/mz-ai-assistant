# Plan: Fix Webhook Push Logging — v1.31.0
**Workflow:** bug-fix
**Date:** 2026-03-16
**Created by:** Lead Agent

---

## Problem

`webhook_tasks.py:_deliver_results_async()` push path (lines 358–369) has two bugs:

1. **Wrong call pattern:** Uses `PushOps(config).execute("send_push", user_id=..., ...)` but `_send_push()` expects `device_token` — `user_id` is silently ignored. The push never actually sends (error swallowed).
2. **No logging:** Even if FCM succeeded via this path, `log_notification()` is never called — notification_log stays empty for webhook-triggered pushes.

The correct pattern (already established in `tasks.py`) is:
- `get_user_push_targets(user_id)` → look up FCM token(s) from DB, respects push preference
- `send_push(user_id, device_token, platform, title, body)` → FCM + `log_notification()`

---

## Scope

**Agent:** Backend only
**File:** `server/app/tasks/webhook_tasks.py` — one function: `_deliver_results_async()`
**Sessions:** 1

---

## Task

### `server/app/tasks/webhook_tasks.py` — `_deliver_results_async()`

Replace the broken `PushOps` block:

```python
# BEFORE (broken — wrong args, no logging)
if deliver_to.get("push_user_id"):
    try:
        from app.tools.communication.push_ops import PushOps
        push = PushOps(config)
        await push.execute(
            "send_push",
            user_id=deliver_to["push_user_id"],
            title="Task Complete",
            body=(content or "")[:100],
        )
    except Exception as e:
        logger.warning(f"Push delivery failed: {e}")
```

With the correct pattern:

```python
# AFTER (correct — uses get_user_push_targets + send_push → logs notification)
if deliver_to.get("push_user_id"):
    try:
        from app.tools.communication.push_ops import get_user_push_targets, send_push
        push_user_id = deliver_to["push_user_id"]
        push_title = deliver_to.get("push_title", "Task Complete")
        push_body = (content or "")[:100]
        targets = await get_user_push_targets(push_user_id)
        for target in targets:
            await send_push(
                user_id=push_user_id,
                device_token=target["device_token"],
                platform=target["platform"],
                title=push_title,
                body=push_body,
            )
    except Exception as e:
        logger.warning(f"Push delivery failed: {e}")
```

Note: `push_title` sourced from `deliver_to.get("push_title", "Task Complete")` — allows callers to customise the notification title without breaking existing webhook payloads that don't include it.

---

## Acceptance Criteria

1. Webhook event with `deliver_to.push_user_id` set → `notification_log` receives a row
2. Existing webhook events without `push_user_id` → no change in behaviour
3. User with `push_notifications_enabled = false` → no push sent, no log entry (handled by `get_user_push_targets` returning `[]`)
4. No new DB migrations required

---

## Quality Gate

Lead reviews `_deliver_results_async()` diff before merge.
