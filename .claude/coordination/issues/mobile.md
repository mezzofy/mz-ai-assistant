# Mobile Agent Issues

## OPEN: Need /llm/usage-stats endpoint for AI Usage Stats screen

**Filed by:** Mobile Agent
**Date:** 2026-03-05
**Priority:** Medium

### Request
The AI Usage Stats screen (`APP/src/screens/AIUsageStatsScreen.tsx`) currently shows a
"Coming Soon" placeholder for token usage data. To populate it, Backend needs to create a
GET endpoint that returns per-user token usage from the `llm_usage` table.

### Proposed endpoint
```
GET /llm/usage-stats
Auth: any authenticated user (not admin-only)
Returns:
{
  "total_messages": int,       // count of rows for this user_id
  "total_input_tokens": int,   // sum(input_tokens)
  "total_output_tokens": int,  // sum(output_tokens)
  "by_model": [                // grouped by model
    {"model": "claude-sonnet-4-6", "input_tokens": int, "output_tokens": int, "count": int},
    ...
  ],
  "period": "all_time"         // or "this_month" if filtered
}
```

### DB table available
`llm_usage` table already auto-populated by `llm_manager.py._track_usage()`:
- `user_id`, `model`, `department`, `input_tokens`, `output_tokens`, `created_at`

### Mobile usage
Once endpoint exists, `AIUsageStatsScreen.tsx` will call it via `apiFetch('/llm/usage-stats')`
and display breakdown under the "Usage Stats" section.
