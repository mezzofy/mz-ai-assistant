# Mobile Agent Issues

## RESOLVED (2026-03-11): BUG-011 — AADSTS700025 on MS OAuth Callback (Backend Fix Required)
**Resolved:** Commit `5d16da1` — switched `ConfidentialClientApplication` → `PublicClientApplication` in `ms_oauth.py`

---

## ARCHIVED

**Filed by:** Mobile Agent
**Date:** 2026-03-11
**Priority:** P1 — MS OAuth connect flow completely broken at token exchange step

### Symptom
After successful Microsoft sign-in, the app receives the deep link callback
(`msalauth://callback?code=...`) and sends it to `POST /ms/auth/callback`.
The backend returns:
```
Token exchange failed: AADSTS700025: Client is public so neither
'client_assertion' nor 'client_secret' should be presented.
```

### Root Cause
`msalauth://` is a custom URI scheme. In Azure AD, redirect URIs with custom
schemes are automatically treated as **public client** (mobile/desktop) flows.
The backend's `_get_msal_app()` in `ms_oauth.py` uses
`msal.ConfidentialClientApplication(client_id, client_credential=client_secret)`.
When it calls `acquire_token_by_authorization_code()`, MSAL sends the
`client_secret` — Azure AD rejects it because the app is a public client.

### Fix Required (Backend Agent)
**File:** `server/app/api/ms_oauth.py` — `_get_msal_app()`

Change `msal.ConfidentialClientApplication` → `msal.PublicClientApplication`.
Public clients do NOT send `client_secret` during code exchange.

```python
# BEFORE:
return msal.ConfidentialClientApplication(
    client_id,
    authority=f"https://login.microsoftonline.com/{tenant_id}",
    client_credential=client_secret,
)

# AFTER:
return msal.PublicClientApplication(
    client_id,
    authority=f"https://login.microsoftonline.com/{tenant_id}",
)
```

Note: `client_secret` may still be needed elsewhere for app-level (non-delegated)
MS Graph calls. This change only affects the OAuth delegated flow in `ms_oauth.py`.

### No Mobile Code Change Needed
Deep link handling, state verification, and API calls are all correct.
`POST /ms/auth/callback` is called with the right `code` and `state`.

---

## RESOLVED (2026-03-05): Need /llm/usage-stats endpoint for AI Usage Stats screen
**Plan:** `.claude/coordination/plans/llm-usage-stats-plan.md`

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
