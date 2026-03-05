# Plan: GET /llm/usage-stats Endpoint
**Workflow:** change-request
**Date:** 2026-03-05
**Created by:** Lead Agent
**Resolves:** `.claude/coordination/issues/mobile.md` (Mobile Agent filed 2026-03-05)

---

## Context

The AI Usage Stats screen (`APP/src/screens/AIUsageStatsScreen.tsx`) shows a
"Coming Soon" placeholder in its "Usage Stats" section. The `llm_usage` table is
already populated by `llm_manager.py._track_usage()` every time the LLM is called.

This plan adds the API endpoint to expose that data and wires the mobile screen to consume it.

---

## Task Breakdown

| # | Task | Agent | Skills | Scope | Depends On | Est. Sessions | Status |
|---|------|-------|--------|-------|-----------|:-------------:|--------|
| 1 | Add GET /llm/usage-stats endpoint | Backend | backend-developer | `server/app/` | — | 1 | NOT STARTED |
| 2 | Wire AIUsageStatsScreen to endpoint | Mobile | mobile-developer | `APP/src/` | Task 1 | 1 | NOT STARTED |

Tasks 1 and 2 are sequential — Mobile needs the endpoint to exist first.

---

## Task 1 — Backend: GET /llm/usage-stats

**Agent:** Backend
**Session estimate:** 1 session
**Files to create/modify:**

| Action | File | What |
|--------|------|------|
| CREATE | `server/app/api/llm.py` | New router — GET /llm/usage-stats |
| MODIFY | `server/app/main.py` | Register `router_llm` with `app.include_router()` |

### Endpoint Spec

```
GET /llm/usage-stats
Authorization: Bearer <access_token>
Auth: any authenticated user (not admin-only)
```

**Response shape:**
```json
{
  "total_messages": 42,
  "total_input_tokens": 85000,
  "total_output_tokens": 12000,
  "by_model": [
    {
      "model": "claude-sonnet-4-6",
      "input_tokens": 80000,
      "output_tokens": 11000,
      "count": 38
    },
    {
      "model": "moonshot-v1-128k",
      "input_tokens": 5000,
      "output_tokens": 1000,
      "count": 4
    }
  ],
  "period": "all_time"
}
```

### DB Query

`llm_usage` table columns already in use:
- `user_id` — filter to requesting user only
- `model` — group by for breakdown
- `input_tokens`, `output_tokens` — sum per group
- `created_at` — available for period filtering (use all_time for v1)

SQL (aggregate):
```sql
SELECT
    COUNT(*) AS total_messages,
    SUM(input_tokens)  AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens
FROM llm_usage
WHERE user_id = :user_id;

SELECT
    model,
    SUM(input_tokens)  AS input_tokens,
    SUM(output_tokens) AS output_tokens,
    COUNT(*)           AS count
FROM llm_usage
WHERE user_id = :user_id
GROUP BY model
ORDER BY count DESC;
```

### Pattern to Follow

Follow the existing `server/app/api/files.py` pattern:
- Use `get_current_user` dependency (not ChatGatewayMiddleware — this is a standard REST endpoint)
- Use `Depends(get_db)` for the AsyncSession
- Return a Pydantic response model
- No admin check — any authenticated user can see their own stats

### Architecture (CSR pattern)

For a single read-only query, a dedicated service/repository layer is overkill. Acceptable
to query DB directly in the endpoint for v1 (same pattern as simple GET endpoints in files.py).

---

## Task 2 — Mobile: Wire AIUsageStatsScreen

**Agent:** Mobile
**Session estimate:** 1 session
**Files to create/modify:**

| Action | File | What |
|--------|------|------|
| CREATE | `APP/src/api/llm.ts` | `getLlmUsageStats()` — calls GET /llm/usage-stats |
| MODIFY | `APP/src/screens/AIUsageStatsScreen.tsx` | Replace "Coming Soon" with real data |

### API Shape (TypeScript)

```typescript
// APP/src/api/llm.ts
export interface ModelUsage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  count: number;
}

export interface LlmUsageStats {
  total_messages: number;
  total_input_tokens: number;
  total_output_tokens: number;
  by_model: ModelUsage[];
  period: string;
}

export const getLlmUsageStats = (): Promise<LlmUsageStats> =>
  apiFetch<LlmUsageStats>('/llm/usage-stats');
```

### UI (AIUsageStatsScreen — Usage Stats section)

Replace the "Coming Soon" card with:
- Total messages (e.g., "42 messages")
- Total tokens used (input + output, formatted with commas)
- Per-model breakdown rows (model name, token count, message count)
- Loading state: spinner
- Error state: "Unable to load stats" with retry
- Empty state: "No usage yet" when total_messages === 0

Fetch in the same `fetchHealth` call (or in parallel — both are fast reads).
Display alongside existing model status and system status sections.

---

## Quality Gate

Lead reviews after Task 1 only if Backend adds something unusual.
For this size of change (single endpoint + one screen update), a post-implementation
spot-check is sufficient — no formal gate required between Tasks 1 and 2.

**Acceptance criteria:**
- [ ] GET /llm/usage-stats returns correct aggregate for the requesting user
- [ ] Other users' data is not visible (user_id filter enforced)
- [ ] Empty response (no rows) returns zeros, not null/error
- [ ] Mobile screen shows real numbers after Backend task complete
- [ ] Loading and error states work correctly in the mobile screen
- [ ] TypeScript: 0 new errors

---

## Parallel Opportunity

None — Task 2 (Mobile) must wait for Task 1 (Backend) to be deployed/running on EC2.
Mobile can stub the response shape locally to develop the UI in parallel if desired,
but the full integration test requires Task 1 live.
