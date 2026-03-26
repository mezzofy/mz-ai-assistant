# Plan: CR — Mobile AI Usage Stats v1.50.0
**Workflow:** change-request
**Date:** 2026-03-26
**Created by:** Lead Agent
**Version:** v1.50.0

---

## Context

The Mobile App `AIUsageStatsScreen` has three problems:

1. **Model names are hardcoded** — `"claude-sonnet-4-6"` and `"Moonshot AI · APAC fallback"` are
   literal strings in the TSX, not read from the server config.

2. **Kimi status dot is always red** — `online={false}` is hardcoded for Kimi.
   Neither Claude nor Kimi's dot reflects the actual `/admin/model-check` test result.

3. **Per-model token rows show raw API model IDs** — `moonshot-v1-8k` instead of
   a friendly label like "Kimi". Kimi token rows only appear once the user has Kimi
   usage in the DB; until then there's no Kimi row at all.

---

## Task Breakdown

| # | Task | Agent | Scope | Depends On | Est. Sessions |
|---|------|-------|-------|-----------|:---:|
| 1 | Add `model_names` to `/admin/health` response | Backend | `server/app/api/admin.py` | — | 1 |
| 2 | Fix model names, status dots, token display | Mobile | `APP/src/` | Task 1 | 1 |

Tasks are sequential — Mobile needs the updated API shape first.

---

## Task 1 — Backend: Add `model_names` to `/admin/health`

**Agent:** Backend
**File:** `server/app/api/admin.py` — `system_health()` endpoint only

### Change

Extend the existing `GET /admin/health` response to include actual model IDs
read from the initialized LLM manager clients:

```json
{
  "status": "ok",
  "services": { ... },
  "connections": { ... },
  "model_names": {
    "claude": "claude-sonnet-4-6",
    "kimi": "moonshot-v1-8k"
  }
}
```

### Implementation Notes

In `system_health()`, after the existing `llm_ok` block:

```python
model_names = {"claude": "unknown", "kimi": "unknown"}
try:
    from app.llm import llm_manager as llm_mod
    mgr = llm_mod.get()
    if mgr is not None:
        model_names["claude"] = mgr.claude.model_name
        model_names["kimi"] = mgr.kimi.model_name
except Exception:
    pass
```

Add `"model_names": model_names` to the return dict.

- `mgr.claude.model_name` — already exists on `ClaudeClient` (property returns `self._model`)
- `mgr.kimi.model_name` — already exists on `KimiClient` (property returns `self._model`)
- If LLM manager is not initialized, returns `"unknown"` for both — graceful fallback
- No new imports needed beyond what already exists in the health endpoint

### No new files — modify only `system_health()` in `admin.py`

---

## Task 2 — Mobile: Fix AIUsageStatsScreen

**Agent:** Mobile
**Files:**
- `APP/src/api/admin.ts` — extend `SystemHealth` interface
- `APP/src/screens/AIUsageStatsScreen.tsx` — fix model names, dots, token display

### 2a — Update `SystemHealth` interface in `admin.ts`

Add `model_names` field:

```typescript
export interface SystemHealth {
  status: 'ok' | 'degraded';
  services: {
    database: string;
    redis: string;
    llm_manager: string;
  };
  connections: {
    websocket_active: number;
  };
  model_names?: {          // optional — graceful if backend not yet updated
    claude: string;
    kimi: string;
  };
}
```

### 2b — Fix model `detail` strings (use API values)

**Claude ModelRow** — replace hardcoded detail:
```tsx
// BEFORE
detail="claude-sonnet-4-6 · Anthropic"

// AFTER
detail={`${health?.model_names?.claude ?? 'claude-sonnet-4-6'} · Anthropic`}
```

**Kimi ModelRow** — replace hardcoded detail:
```tsx
// BEFORE
detail="Moonshot AI · APAC fallback"

// AFTER
detail={`${health?.model_names?.kimi ?? 'moonshot-v1-8k'} · Moonshot AI`}
```

### 2c — Fix status dots (green when last model-check was ok)

**Claude `online` prop** — currently `health !== undefined && llmOk`
Replace with: test result takes priority; fall back to system health if not yet tested.
```tsx
online={claudeCheck?.status === 'ok' ? true : (claudeCheck == null && health !== undefined && llmOk)}
```
- After successful test: green ✅
- After failed test: red ✅
- Never tested yet + LLM manager ok: green (existing behaviour)
- Never tested yet + LLM manager not ok: red

**Kimi `online` prop** — currently hardcoded `false`
Replace with:
```tsx
online={kimiCheck?.status === 'ok'}
```
- After successful test: green ✅
- Never tested / failed: red ✅

### 2d — Fix per-model token rows (friendly labels + always show Kimi row)

Currently the `stats.by_model.map()` renders raw API model IDs (`moonshot-v1-8k`,
`claude-sonnet-4-6`). The user gets `moonshot-v1-8k` as the label. Also, if Kimi
has zero usage rows, no Kimi row appears at all.

**Fix:** Add a `friendlyModelName()` helper and ensure a Kimi row always appears:

```typescript
// Helper — convert raw model ID to display name
function friendlyModelName(modelId: string): string {
  if (modelId.includes('claude')) return `Claude (${modelId})`;
  if (modelId.includes('moonshot') || modelId.includes('kimi')) return `Kimi (${modelId})`;
  return modelId;
}
```

In the per-model breakdown:
- Replace `{m.model}` label with `{friendlyModelName(m.model)}`
- After the `stats.by_model.map()` block, check if no Kimi row exists and add a
  zero-usage Kimi placeholder row:
  ```tsx
  {!stats.by_model.some(m => m.model.includes('moonshot') || m.model.includes('kimi')) && (
    <View style={[styles.modelUsageRow, ...]}>
      <View style={styles.modelUsageLeft}>
        <Text ...>Kimi ({health?.model_names?.kimi ?? 'moonshot-v1-8k'})</Text>
        <Text ...>No usage yet</Text>
      </View>
    </View>
  )}
  ```

---

## Acceptance Criteria

- [ ] `/admin/health` response includes `model_names.claude` and `model_names.kimi`
      matching actual values from config.yaml (e.g., `claude-sonnet-4-6`, `moonshot-v1-8k`)
- [ ] Claude `detail` string shows the actual model ID from health response
- [ ] Kimi `detail` string shows the actual model ID from health response
- [ ] Claude status dot turns green after a successful model-check test
- [ ] Kimi status dot turns green after a successful model-check test (was always red before)
- [ ] Per-model token rows show "Claude (model-id)" and "Kimi (model-id)" labels
- [ ] A Kimi row always appears in Usage Stats even when Kimi token usage is zero
- [ ] TypeScript: 0 new errors
- [ ] Graceful fallback: if `model_names` not present (old backend), hardcoded defaults used

---

## Quality Gate

Lead reviews both tasks after Mobile completes.
Single session each — both are small targeted changes.
