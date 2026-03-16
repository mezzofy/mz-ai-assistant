# Review: Notification History — v1.30.0
**Date:** 2026-03-16
**Reviewer:** Lead Agent
**Workflow:** change-request
**Decision:** ✅ PASS

---

## Quality Gate Checklist

### Backend (`server/`)

- [x] **DB schema correct** — `notification_log` table: UUID PK, user_id FK with CASCADE, title/body TEXT, data JSONB, sent_at TIMESTAMPTZ DEFAULT NOW(). Follows existing table conventions.
- [x] **Index correct** — `idx_notification_log_user ON (user_id, sent_at DESC)` — composite index matches the query's WHERE + ORDER BY. Efficient for per-user history lookups.
- [x] **Migration idempotent** — `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`. Safe to re-run. Placed correctly after `user_devices` block.
- [x] **log_notification() helper** — Silent-fail pattern (try/except → logger.warning). Opens its own `AsyncSessionLocal` session, commits, closes. Consistent with `get_user_push_targets()` pattern in same file. Lazy imports follow project rule.
- [x] **send_push() integration** — `log_notification()` called only on `result.get("success")`. Correct guard — no false logs on FCM failures. Comment documents the webhook_tasks.py gap clearly.
- [x] **Pydantic models** — `NotificationRecord` (id: UUID, title/body: str, data: Optional[Any], sent_at: datetime) + `NotificationHistoryResponse` (notifications: list, count: int). Matches endpoint contract exactly.
- [x] **Endpoint** — `GET /notifications/history` with `Query(ge=1, le=50)` for validation, plus defensive `min(max(...))` clamp. Parameterized SQL, no injection risk. User_id from JWT (not request body). Already mounted at `/notifications` in main.py — no main.py change needed.
- [x] **Auth** — `Depends(get_current_user)` on history endpoint. Users can only see their own logs.

**P1 issues:** None
**P2 notes:** The redundant `clamped = min(max(limit, 1), 50)` after `Query(ge=1, le=50)` is harmless double-validation. Non-blocking.

---

### Mobile (`APP/`)

- [x] **Types** — `NotificationRecord` + `NotificationHistoryResponse` in `notificationsApi.ts`. Clean, matches backend contract.
- [x] **API function** — `getNotificationHistory(limit=10)` uses `apiFetch` with query param. Correct pattern.
- [x] **Store** — `notificationStore.ts` follows `schedulerStore.ts` pattern exactly: Zustand create, state shape (notifications/loading/error), single `loadNotifications()` action. Clean.
- [x] **Screen structure** — `NotificationHistoryScreen.tsx` follows `ScheduleStatsScreen.tsx` pattern: back chevron header, FlatList + RefreshControl, `useCallback` on renderItem, empty state (bell icon + text), `useEffect` on mount.
- [x] **Card layout** — Bell icon in `accentSoft` bubble + title (bold, flex: 1) + relative time (textDim, right) + body text (2-line muted). Correct visual hierarchy.
- [x] **formatRelativeTime()** — Covers all 5 cases: <60s "Just now", <1h "Nm ago", <24h "Nh ago", <48h "Yesterday", else locale date. Correct thresholds (60, 3600, 86400, 172800).
- [x] **SettingsScreen** — "Notification History" row placed correctly as FIRST item in second group (above Privacy & Security). Uses `notifications-circle-outline` icon. `accent` prop applied. Version string bumped `v1.29.0` → `v1.30.0`.
- [x] **App.tsx** — Import added. `Stack.Screen name="NotificationHistory"` registered after ScheduleStats entry. `animation: 'slide_from_right'` consistent with all other settings screens.
- [x] **Version bump** — `build.gradle` versionCode 37→38, versionName 1.29.0→1.30.0. `package.json` 1.29.0→1.30.0. All three files in sync (build.gradle + package.json + SettingsScreen.tsx).

**P1 issues:** None
**P2 notes:** None

---

### Build

- [x] **APK BUILD SUCCESSFUL** — 38s, release variant, versionCode 38
- [x] **Commits clean** — `0d24e94` (feature) · `ac6e973` (version bump) · `de10d02` (status)

---

## Known Gaps (Documented, Non-Blocking)

| Gap | Severity | Deferred To |
|-----|----------|-------------|
| `webhook_tasks.py` uses `PushOps._send_push()` directly — webhook-triggered pushes not logged | P3 | v1.31.0 |

---

## EC2 Deploy Checklist

```bash
# On EC2:
cd /home/ubuntu/mz-ai-assistant && git pull
cd server && python scripts/migrate.py
# Expected output: ✅ notification_log + ✅ idx_notification_log_user
sudo systemctl restart mezzofy-api.service
```

Verification after deploy:
1. `GET /notifications/history` → `{"notifications": [], "count": 0}` (empty, no pushes yet)
2. Trigger a push via `POST /scheduler/jobs/{id}/run` → check `notification_log` has a row
3. `GET /notifications/history` → returns the logged notification
4. Mobile: Settings → Notification History → card appears with correct title/body/time
5. Pull-to-refresh reloads the list

---

## Decision

**✅ PASS** — v1.30.0 is production-ready. EC2 deploy is the only remaining step.
