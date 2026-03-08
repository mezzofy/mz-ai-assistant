# Review: Mobile Agent — BUG-007 (v1.14.7)
**Reviewer:** Lead Agent
**Date:** 2026-03-08
**Commit:** `2297ec0` — "Release v1.14.7: task progress & session fixes"
**Verdict:** ✅ PASS

---

## Scope Verified

Files modified are all within Mobile Agent's ownership:
- `APP/src/api/chat.ts` ✅
- `APP/src/stores/chatStore.ts` ✅
- `APP/src/screens/ChatScreen.tsx` ✅
- `APP/android/app/build.gradle` ✅
- `APP/package.json` ✅
- `APP/src/screens/SettingsScreen.tsx` ✅
- `.claude/coordination/status/mobile.md` ✅ (agent's own status file)

No scope boundary violations.

---

## Findings

### 🔴 Blockers
*None.*

### 🟡 Warnings
1. **`APP/src/screens/ChatScreen.tsx:466`** — IIFE pattern `(() => { ... })()` in JSX is functional and correctly handles JSON.parse errors, but is unusual. Some ESLint configs will flag it. Not a blocker for this project (no lint config enforcing this), but consider extracting to a named helper `renderStepDesc(task)` if it grows more complex in future.

2. **`APP/src/api/chat.ts:146`** — `started_at` is added to `TaskSummary` but unused in the UI. No blocker — intended for future elapsed-time display. Leave as-is.

### 🟢 Suggestions
1. **`APP/src/screens/ChatScreen.tsx:462`** — `activeTask.progress > 0` intentionally hides "0%" at task start. This is correct UX (avoids the banner flickering "0%" briefly). Accepted by design.

2. The `taskBarText` style is reused for both the title line and the step description line (with `{fontSize: 10, opacity: 0.8}` override). Could be a dedicated `taskBarSubText` style entry for clarity, but the inline override is acceptable.

---

## Fix-by-Fix Assessment

### Fix A — `TaskSummary` interface (`chat.ts:137–147`)
- All three fields correctly typed as optional (`?`) ✅
- Won't break the manual `TaskSummary` constructor in `sendToServer()` (that object omits `progress`/`current_step` — undefined, correct) ✅
- Comments accurate (point to server source `_update_agent_task_step()`) ✅

### Fix B — `pollActiveTask` race guard (`chatStore.ts:369`)
- `if (get().sessionId !== sessionId) { return; }` — correctly placed *after* await, *before* `set()` ✅
- `resetChat()` sets `sessionId: null`; `null !== any_uuid` → stale response discarded ✅
- The `useEffect` in `ChatScreen.tsx` captures `sessionId` at mount time and passes it as argument, so the guard comparison is always against the correct "expected" session ✅

### Fix C — Empty bubble fallback (`chatStore.ts:253`)
- `response.response || 'Task completed.'` — falsy guard catches `""`, `null`, `undefined` ✅
- Applied only in the `!newActiveTask` (sync) branch — does not affect queued task flow ✅
- Consistent with server-side `process_result()` fallback ✅

### Fix D — Session-scoped banner + progress (`ChatScreen.tsx:450–486`)
- `activeTask && activeTask.session_id === sessionId` — correctly handles all cases:
  - New chat ("+"): `sessionId` is `null`, `activeTask.session_id` is non-null → no render ✅
  - Race condition fires: old `session_id` ≠ new `sessionId` → still blocked ✅
  - History restore (BUG-006): both set atomically in `loadHistory()` → match → renders ✅
- Progress line shows only when `progress != null && progress > 0` — avoids "0%" flash ✅
- Step description only shown when `status === 'running'` — correct ✅
- JSON.parse wrapped in try/catch — malformed `current_step` silently ignored ✅
- `<View style={{flex: 1, overflow: 'hidden'}}>` wrapper prevents long text overflowing into close button ✅

### Version Bump
| File | Expected | Actual |
|------|----------|--------|
| `build.gradle` versionCode | 25 | 25 ✅ |
| `build.gradle` versionName | "1.14.7" | "1.14.7" ✅ |
| `package.json` version | "1.14.7" | "1.14.7" ✅ |
| `SettingsScreen.tsx` label | v1.14.7 | v1.14.7 ✅ |

### Build
- Result: BUILD SUCCESSFUL ✅
- Time: 1m 7s (normal range)
- APK size: ~61 MB (consistent with v1.14.4–1.14.6) ✅
- Tasks: 438 actionable, 30 executed, 408 up-to-date ✅

---

## Summary

BUG-007 is a clean, minimal, well-targeted fix. All four root causes addressed with no over-engineering:
- The race condition guard is correct and placed at exactly the right location
- The session-scope check is the right second line of defence (covers the case where Fix B doesn't fire)
- The TypeScript interface extension is non-breaking and accurately typed
- The version bump is consistent across all 3 required files

The build is green and APK size is consistent with previous versions.

## Next Steps
- [ ] Deploy APK to test device and verify:
  1. Progress % increments in banner during a long task
  2. "+" new chat → banner disappears and stays gone
  3. History → open session with task → banner shows; "+" → banner disappears
  4. No blank assistant bubbles on sync responses
- [ ] Optionally: push `eric-design` branch to remote for backup
- [ ] Update mobile status checkpoint to "BUILD VERIFIED" after device test
