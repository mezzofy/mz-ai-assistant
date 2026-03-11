# Plan: MS Contacts Feature + Write Operations Fix (BUG-013)
**Workflow:** change-request
**Date:** 2026-03-11
**Created by:** Lead Agent

---

## Context

Two tasks following the MS OAuth integration (v1.17.x):

1. **FEAT-013 — Contacts:** Add MS Graph Contacts support to Chat tools + Connected Accounts UI
2. **BUG-013 — Write Operations:** Investigate and fix "write says success but nothing happens"

---

## Root Cause Analysis — BUG-013

`_base_task()` in `chat.py` already populates `task["user_id"]` from the JWT.
Today's system-prompt fix (commit `36c17ed`) correctly injects `{user_id}` into the
prompt so Claude uses the right value for `personal_*` tool calls.

**The write failure is NOT a code logic bug. It is a token scope / Azure AD issue.**

When the user connected their MS account, the OAuth consent screen only shows scopes
that are registered in the Azure Portal app registration. If the portal only has read
scopes (`Mail.Read`, `Calendars.Read`, etc.), the token will NOT include write scopes
(`Mail.Send`, `Calendars.ReadWrite`, `Chat.ReadWrite`, `Notes.ReadWrite`) — even
though our code requests them.

Graph API then returns 403 Forbidden for write calls. `_err()` returns
`{"success": False, "error": "Graph API error 403: ..."}`. Claude receives this
failed tool result and may still say "Done!" if the LLM interprets it as transient.

**Fix path:**
1. User verifies Azure Portal app has write permissions registered (see instructions below)
2. Add a diagnostic tool to decode the stored token's `scp` claim
3. Add server-side logging to write handlers so we can check EC2 logs
4. User must DISCONNECT + RECONNECT their MS account after any scope/permission change

---

## Task Breakdown

| # | Task | Agent | Scope | Depends On | Est. Sessions |
|---|------|-------|-------|------------|:-------------:|
| 1 | Add Contacts scope + tools to backend | Backend | `server/app/` | None | 1 |
| 2 | Add diagnostic tool + write logging | Backend | `server/app/` | None (same session as Task 1) | — |
| 3 | Add Contacts pill + update info text in mobile | Mobile | `APP/src/` | Task 1 (for context) | 1 |

Tasks 1+2 are a single Backend session. Task 3 is a separate Mobile session.
Tasks 1+2 and Task 3 can run in parallel.

---

## Task 1+2 — Backend Agent (1 session)

### 1a. `server/app/core/config.py` — Add Contacts scopes

Add to `MS365_DELEGATED_SCOPES`:
```python
"Contacts.Read",
"Contacts.ReadWrite",
```

After this change the list becomes:
```python
MS365_DELEGATED_SCOPES: List[str] = [
    "User.Read",
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.ReadWrite",
    "Notes.Read",
    "Notes.ReadWrite",
    "Chat.ReadWrite",
    "Contacts.Read",
    "Contacts.ReadWrite",
]
```

### 1b. `server/app/tools/communication/personal_ms_ops.py` — Add 4 contact tools

Add 4 tools to `get_tools()` (after Teams section):

```
personal_get_contacts      — GET /me/contacts (list)
personal_search_contacts   — GET /me/contacts?$search=... (by name/email)
personal_get_contact_detail — GET /me/contacts/{id} (full detail)
personal_create_contact    — POST /me/contacts (create new contact)
```

Handler details:
- `_get_contacts(user_id, limit=20)` → `GET /me/contacts` with `$top`, `$select` (id, displayName, emailAddresses, mobilePhone, jobTitle, companyName)
- `_search_contacts(user_id, query, limit=10)` → `GET /me/contacts?$search="<query>"`
- `_get_contact_detail(user_id, contact_id)` → `GET /me/contacts/{contact_id}`
- `_create_contact(user_id, display_name, email, phone=None, company=None, job_title=None)` → `POST /me/contacts`

All follow the existing pattern: `_get_headers()` → httpx → `_ok()` / `_err()` → `_audit()`

Success codes:
- GET: 200
- POST: 201

### 1c. `server/app/llm/llm_manager.py` — Update system prompt

In `_SYSTEM_PROMPT_TEMPLATE`, update the personal MS line (added in BUG-012 fix) to:
```
- Accessing YOUR personal Microsoft account (email, calendar, OneNote, Teams chats, Contacts)
  if you have connected it in Settings → Connected Accounts
```

### 2a. `server/app/tools/communication/personal_ms_ops.py` — Add diagnostic tool

Add `personal_check_token_scopes` tool:
- Handler: `_check_token_scopes(user_id)`
- Calls `get_valid_token(user_id)` to get the raw access token
- Decodes the JWT payload (base64, middle segment) WITHOUT verifying signature
- Returns the `scp` claim (space-separated string of granted scopes)
- Also returns `upn`/`unique_name` (the Microsoft account email)
- Returns `{"token_present": True, "granted_scopes": [...], "ms_account": "..."}` or `_not_connected()`

This lets the user ask Claude: "What MS permissions do you have?" and immediately
see whether write scopes are in the token.

### 2b. `server/app/tools/communication/personal_ms_ops.py` — Improve write logging

In ALL write handlers (`_send_email`, `_create_event`, `_update_event`, `_delete_event`,
`_create_note`, `_send_chat_message`, `_create_contact`):

On non-2xx response, log at ERROR level with:
```python
logger.error(
    f"personal_ms WRITE FAILED | tool={tool_name} user_id={user_id} "
    f"status={resp.status_code} body={resp.text[:500]}"
)
```

This makes EC2 log analysis definitive.

---

## Task 3 — Mobile Agent (1 session)

### 3a. `APP/src/screens/ConnectedAccountsScreen.tsx` — Add Contacts pill

Line 178 hardcodes `['Mail', 'Calendar', 'Notes', 'Teams']`.
Change to: `['Mail', 'Calendar', 'Notes', 'Teams', 'Contacts']`

### 3b. Same file — Update info text (line 215-218)

```
Connecting your Microsoft account lets the AI read and send your personal emails,
manage calendar events, access OneNote, manage your Contacts, and chat in Teams
on your behalf.
```

### 3c. Version bump

`APP/package.json` + `APP/android/app/build.gradle`:
- Version: 1.18.0 / versionCode 30

---

## Azure AD App Registration (USER ACTION REQUIRED)

**Before testing writes, the user must verify the Azure Portal app has these
delegated permissions registered:**

Go to: Azure Portal → App Registrations → [your app] → API Permissions → Add a Permission

Required delegated permissions under Microsoft Graph:
- `Mail.Read` ✅ (probably already there)
- `Mail.ReadWrite` — check
- `Mail.Send` — **add if missing**
- `Calendars.ReadWrite` — **add if missing**
- `Notes.Read`
- `Notes.ReadWrite` — **add if missing**
- `Chat.ReadWrite` — **add if missing**
- `Contacts.Read` — **add (new)**
- `Contacts.ReadWrite` — **add (new)**

After adding permissions: **DO NOT click "Grant admin consent"** unless the tenant
requires it. User consent is sufficient for delegated permissions on personal accounts.

**Then:** User must disconnect + reconnect their Microsoft account in Settings →
Connected Accounts to trigger a new consent dialog with all scopes.

---

## Deploy Steps

```bash
# After GitHub Desktop push:
ssh -i mz-ai-key.pem ubuntu@3.1.255.48
cd /home/ubuntu/mz-ai-assistant
git pull origin eric-design
sudo systemctl restart mezzofy-api.service
```

---

## Verification Steps

### After deploy + user reconnects MS account:

1. **Check scopes**: Ask Chat "What Microsoft permissions do you have?"
   - Claude calls `personal_check_token_scopes` → shows granted scopes
   - Must see: `Mail.Send Calendars.ReadWrite Notes.ReadWrite Chat.ReadWrite Contacts.Read Contacts.ReadWrite`

2. **Test Contacts read**: Ask Chat "Show me my Microsoft contacts"
   - Claude calls `personal_get_contacts(user_id="eric@mezzofy.com")`

3. **Test write — email**: Ask Chat "Send a test email to eric@mezzofy.com with subject 'Test'"
   - Check EC2 logs: `sudo journalctl -u mezzofy-api.service | grep "WRITE FAILED"` — should be empty
   - Check inbox for received email

4. **Test write — calendar**: Ask Chat "Create a calendar event for tomorrow at 10am called 'Test Meeting'"
   - Check Outlook calendar

5. **Test write — Teams**: Ask Chat "Show my Teams chats" then "Send 'hello test' to the first chat"

---

## Quality Gate

**PASS criteria:**
- [ ] `personal_check_token_scopes` returns all write scopes (confirms Azure AD fix)
- [ ] Contacts read tool returns contact list
- [ ] Email write: email arrives in inbox
- [ ] Calendar write: event visible in Outlook calendar
- [ ] No `WRITE FAILED` log entries during successful operations
- [ ] Connected Accounts screen shows 5 scope pills: Mail, Calendar, Notes, Teams, Contacts

---

## Agent Assignment

| Agent | Boot Command | Tasks |
|-------|-------------|-------|
| Backend | `/boot-backend` | 1a, 1b, 1c, 2a, 2b |
| Mobile | `/boot-mobile` | 3a, 3b, 3c |

Both agents can run in parallel (different files).
Lead reviews after both complete before deployment.
