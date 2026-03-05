# Review: Backend + Mobile — GET /llm/usage-stats + AIUsageStatsScreen
**Reviewer:** Lead Agent
**Date:** 2026-03-05
**Plan:** `plans/llm-usage-stats-plan.md`
**Verdict:** ✅ PASS — Both tasks complete and correct

---

## Files Reviewed

| Agent | File | Type | Lines |
|-------|------|------|-------|
| Backend | `server/app/api/llm.py` | New | 103 |
| Backend | `server/app/main.py` | Modified | 173 |
| Mobile | `APP/src/api/llm.ts` | New | 19 |
| Mobile | `APP/src/screens/AIUsageStatsScreen.tsx` | Modified | 281 |

---

## Backend Review

### Checklist
- [x] CSR pattern — single endpoint, direct DB query acceptable (read-only aggregate, no business logic)
- [x] `Depends(get_current_user)` + `Depends(get_db)` — follows `files.py` pattern exactly
- [x] `user_id = current_user["user_id"]` — confirmed correct key (matches `files.py:97`)
- [x] Parameterized queries: `:user_id` bound parameter — no string interpolation, no SQL injection risk
- [x] User data isolation: `WHERE user_id = :user_id` on both queries — no cross-user visibility
- [x] `COALESCE(SUM(...), 0)` on all aggregate columns — zero-safe when user has no rows
- [x] `ORDER BY count DESC` — most-used model first
- [x] Pydantic response models: `ModelUsage` + `LlmUsageStats` — typed correctly
- [x] Router registered in `main.py`: `app.include_router(llm.router, prefix="/llm")`
- [x] `main.py` docstring updated: `/llm/*` route documented
- [x] No scope boundary violations — only `server/app/api/` modified

### Findings

#### 🔴 Blockers
None.

#### 🟡 Warnings
None.

#### 🟢 Suggestions
1. **`llm.py:89` — double-null guard** `totals.total_messages or 0` is redundant since `COUNT(*)` never returns NULL (unlike `SUM()`). COALESCE on the SUM columns is correct and necessary; the `or 0` on count is harmless redundancy. No change needed.

---

## Mobile Review

### Checklist (`llm.ts`)
- [x] TypeScript interfaces exactly match Pydantic models field-for-field
  - `ModelUsage`: model, input_tokens, output_tokens, count ✅
  - `LlmUsageStats`: total_messages, total_input_tokens, total_output_tokens, by_model, period ✅
- [x] `getLlmUsageStats()` returns `Promise<LlmUsageStats>` — typed correctly
- [x] Uses `apiFetch` — JWT auth token included automatically
- [x] No hardcoded base URL — consistent with rest of `api/` layer

### Checklist (`AIUsageStatsScreen.tsx`)
- [x] `Promise.all([getSystemHealth(), getLlmUsageStats().catch(() => null)])` — parallel fetch, stats error does not break health display
- [x] `stats` state typed as `LlmUsageStats | null | undefined` — undefined=loading, null=error, object=data
- [x] All 4 Usage Stats states handled: loading spinner, error + Retry, empty "No usage yet", data rows
- [x] Retry button on error calls `fetchHealth` — triggers full re-fetch including health
- [x] `toLocaleString()` on all numbers — locale-formatted display (e.g., "1,234,567")
- [x] `stats.by_model.map(m => ...)` uses `m.model` as key — correct (model name is unique per user)
- [x] All new styles defined in `StyleSheet.create` — no inline object styles introduced
- [x] TypeScript: 0 new errors reported by agent
- [x] No scope boundary violations — only `APP/src/` modified

### Findings

#### 🔴 Blockers
None.

#### 🟡 Warnings
None.

#### 🟢 Suggestions
1. **`AIUsageStatsScreen.tsx:155` — shared `loading` flag** — `stats === undefined || loading` ties stats loading display to the same `loading` flag as health. Since both resolve in `Promise.all`, this is correct — they always finish together. Nice side effect: a single `loading` state keeps the UI simple.

2. **`AIUsageStatsScreen.tsx:207-210` — In/Out token display** — `In ${m.input_tokens.toLocaleString()}` / `Out ${m.output_tokens.toLocaleString()}` are separate text nodes. Readable and consistent with the header row's sub-label approach. ✅

---

## Contract Verification

| Field | Backend (Pydantic) | Mobile (TypeScript) | Match |
|-------|-------------------|---------------------|-------|
| `total_messages` | `int` | `number` | ✅ |
| `total_input_tokens` | `int` | `number` | ✅ |
| `total_output_tokens` | `int` | `number` | ✅ |
| `by_model` | `List[ModelUsage]` | `ModelUsage[]` | ✅ |
| `period` | `str` | `string` | ✅ |
| `model` | `str` | `string` | ✅ |
| `input_tokens` | `int` | `number` | ✅ |
| `output_tokens` | `int` | `number` | ✅ |
| `count` | `int` | `number` | ✅ |

All 9 fields match. No type mismatches.

---

## Summary

Both agents delivered clean, minimal implementations that match the plan spec exactly.

**Backend:** Single endpoint, two queries (totals + per-model breakdown), user-scoped, null-safe.
Follows the established `files.py` pattern precisely — `get_current_user`, `get_db`, parameterized `text()` queries.

**Mobile:** Excellent `Promise.all` design — health and stats load in parallel, and a stats error
silently shows an error state rather than crashing the whole screen. The "Coming Soon" section
is fully replaced with a 4-state UI that correctly handles every observable data scenario.

**No blockers. No warnings. Ship when ready.**

## Next Step
- Deploy `server/` changes to EC2 (`mezzofy-api.service` restart)
- The mobile changes take effect on next hot-reload or app install (no native rebuild required)
- v1.3.0 is complete once the EC2 service is restarted with the new endpoint
