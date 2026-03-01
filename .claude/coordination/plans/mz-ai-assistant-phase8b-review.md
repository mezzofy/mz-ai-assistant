# Phase 8B Quality Gate Review
**Reviewer:** Lead Agent
**Date:** 2026-02-28
**Session Reviewed:** 8B (Chat API + chatStore + ChatScreen real API wiring)
**Decision:** ✅ PASS (after fix) — hooks violation resolved by Mobile Agent in 8B-fix session

---

## Files Reviewed

| File | Status | Notes |
|------|--------|-------|
| `APP/src/stores/authStore.ts` | ✅ PASS | ISSUE-1 fix correct — `freshAccess` re-read after getMeApi() |
| `APP/src/api/chat.ts` | ✅ PASS | Types correct, routing correct, FormData guard correct |
| `APP/src/api/websocket.ts` | ✅ PASS | MzWebSocket correct, singleton correct, typed messages match server |
| `APP/src/stores/chatStore.ts` | ✅ PASS | Routing correct, atomic set, explicit `let response: ChatResponse` |
| `APP/src/screens/ChatScreen.tsx` | ❌ REVISE | Rules of Hooks violation: 2x useEffect after null guard |

---

## Issue Found: ChatScreen.tsx — useEffect Hooks After Null Guard

**Severity:** High (Rules of Hooks violation)
**File:** `APP/src/screens/ChatScreen.tsx`
**Lines:** 32–53 (two `useEffect` calls)

### The Violation

The component declares 5 hooks before the null guard (lines 14–23) ✅, then places 2 `useEffect` hooks AFTER `if (!user) return null` (lines 26–28) ❌:

```
Line 14: useAuthStore(...)        ← Hook #1 ✅
Line 15: useChatStore()           ← Hook #2 ✅
Line 21: useState('')             ← Hook #3 ✅
Line 22: useRef(null)             ← Hook #4 ✅
Line 23: useRef(null)             ← Hook #5 ✅
Line 26: if (!user) return null   ← CONDITIONAL RETURN
Line 32: useEffect(...)           ← Hook #6 ❌ CONDITIONAL — violation!
Line 36: useEffect(...)           ← Hook #7 ❌ CONDITIONAL — violation!
```

When `user` is null, React runs 5 hooks. When `user` is not null, React runs 7 hooks. React requires the same hooks to run every render. This inconsistency violates the Rules of Hooks.

The `useChatStore()` violation was fixed in 8B, but the two `useEffect` calls were not moved.

### The Fix

Move both `useEffect` blocks to BEFORE `if (!user) return null`.

**Structure after fix:**
```tsx
export const ChatScreen = ({navigation}) => {
  // Hook #1
  const user = useAuthStore(s => s.user);
  // Hook #2
  const { messages, isTyping, ... } = useChatStore();
  // Hook #3
  const [input, setInput] = useState('');
  // Hook #4
  const scrollRef = useRef<ScrollView>(null);
  // Hook #5
  const timerRef = useRef<...>(null);

  // Hook #6 — scroll effect
  useEffect(() => {
    scrollRef.current?.scrollToEnd({animated: true});
  }, [messages, isTyping]);

  // Hook #7 — recording timer
  useEffect(() => {
    if (recording) {
      timerRef.current = setInterval(
        () => setRecordTime(useChatStore.getState().recordTime + 1),
        1000,
      );
    } else {
      if (timerRef.current) { clearInterval(timerRef.current); }
      setRecordTime(0);
    }
    return () => {
      if (timerRef.current) { clearInterval(timerRef.current); }
    };
  }, [recording]);

  // Null guard AFTER ALL hooks
  if (!user) { return null; }

  // ... rest of component
};
```

---

## Passing Items (Confirmed)

### ISSUE-1 Fix (authStore.ts:77–98) ✅
- `const freshAccess = await getAccessToken()` on line 85 — correctly re-reads after `getMeApi()` returns
- `accessToken: freshAccess` on line 90 — stores the potentially-refreshed token
- Fix is minimal and correct

### chat.ts ✅
- `ChatArtifact`: `{id: string|null, type, name, download_url: string|null}` — matches `processor.py` exactly
- `ChatResponse`: `{session_id, response, input_processed, artifacts, agent_used, tools_used, success}` — complete
- `sendTextApi`, `sendUrlApi` — clean body serialization, no Content-Type issues (not FormData)
- `sendMediaApi` — RN FormData object pattern `{uri, name, type}` correct; no manual Content-Type set
- `getSessionsApi`, `getHistoryApi` — clean, correct paths

### websocket.ts ✅
- Inbound types match `format_ws_message()` in server `output_formatter.py`
- Connection timeout (10s) via Promise resolve/reject
- Singleton `mzWs` correctly placed at module level
- `_send` silently drops when not connected — safe
- All outbound message types match server handler in `chat.py`

### chatStore.ts ✅
- `(set, get)` signature — `get()` used to read `sessionId` before API call ✅
- `let response: ChatResponse` explicit annotation — avoids TS strict implicit any ✅
- `sendToServer` routing:
  - `mode === 'url'` → `sendUrlApi` ✅
  - `media && mode !== 'text' && mode !== 'speech'` → `sendTextApi` with `[mode: name]` description ✅
  - text/speech → `sendTextApi` ✅
- Atomic `set(s => ...)` for assistant response + `sessionId` + `isTyping: false` ✅
- `loadSessions` / `loadHistory` — silent fail (correct — callers show empty state) ✅
- `resetChat` resets all state cleanly ✅
- No `DEMO_RESPONSES` import anywhere ✅

### ChatScreen.tsx (except hooks issue) ✅
- `DEMO_RESPONSES` not imported — removed ✅
- No `setTimeout` mock for chat responses ✅
- `handleSend` calls `sendToServer()` correctly ✅
- Error banner renders when `chatError` is set, dismisses via `clearError()` ✅
- `handleNewChat` calls `resetChat()` + `setSessionId(null)` ✅
- Speech mode stub sends via real `sendToServer` (not setTimeout) ✅
- `BRAND.accentSoft` on line 384 — pre-existing bug from 8A, acceptable, defer ✅

---

## Decision: REVISE

**Assign to:** Mobile Agent (1 small fix)
**Scope:** Move 2 `useEffect` blocks (lines 32–53) to above `if (!user) return null` in ChatScreen.tsx

After fix confirmed: Re-run `npx tsc --noEmit` → 0 new errors → Phase 8C authorized.

---

## Phase 8C Authorization (Pending Fix)

Once ChatScreen.tsx hooks violation is resolved, Mobile Agent is authorized to start Phase 8C:

1. Create `APP/src/api/files.ts` (listFilesApi, uploadFileApi, deleteFileApi)
2. Update `APP/src/screens/FilesScreen.tsx` — real `GET /files/` on mount
3. Update `APP/src/screens/HistoryScreen.tsx` — real `GET /chat/sessions` via `chatStore.loadSessions()`
4. Update `APP/src/screens/CameraScreen.tsx` — real WS camera frames via `mzWs.sendCameraFrame()`

Ref: `.claude/coordination/plans/mz-ai-assistant-phase8-plan.md` (Session 8C section)
