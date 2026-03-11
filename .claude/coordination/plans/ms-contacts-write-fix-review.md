# Review: ms-contacts-write-fix-plan — Backend Tasks (1a, 1b, 1c, 2a, 2b)
**Date:** 2026-03-12
**Reviewer:** Lead Agent
**Commit reviewed:** `36bf87f`

---

## Checklist

### Task 1a — config.py
- [x] `Contacts.Read` added to `MS365_DELEGATED_SCOPES` ✅
- [x] `Contacts.ReadWrite` added ✅
- [x] Existing scopes unchanged ✅

### Task 1b — Contact tools (get_tools + handlers)
- [x] 4 tools registered in `get_tools()`: get/search/detail/create ✅
- [x] All 4 have correct `user_id` as required param ✅
- [x] All handlers follow existing pattern: `_get_headers()` → httpx → `_ok()`/`_err()` → `_audit()` ✅
- [x] `_get_contacts`: correct $select fields, $top clamped 1–50 ✅
- [x] `_search_contacts`: $search param formatted correctly ✅
- [x] `_get_contact_detail`: GET /me/contacts/{id} ✅
- [x] `_create_contact`: POST /me/contacts with optional fields, 201 success code ✅
- [x] `_create_contact` has write logging ✅

### Task 1c — System prompt
- [x] "Contacts" added to personal MS capabilities line ✅

### Task 2a — Diagnostic tool
- [x] `personal_check_token_scopes` registered in `get_tools()` ✅
- [x] `_check_token_scopes` handler decodes JWT payload (no sig verify) ✅
- [x] Returns `scp` as list ✅
- [x] Returns `ms_account` (UPN/preferred_username) ✅
- [x] Returns `missing_write_scopes` from defined set {Mail.Send, Calendars.ReadWrite, Notes.ReadWrite, Chat.ReadWrite} ✅
- [x] Returns actionable `diagnosis` string ✅
- [x] Exception handling: MSNotConnectedException + broad Exception ✅
- [x] `_get_raw_token` helper correctly calls `get_valid_token()` (which auto-refreshes) ✅

### Task 2b — Write logging
- [x] `personal_send_email` — logger.error on non-(200,202) ✅
- [x] `personal_create_event` — logger.error on non-(200,201) ✅
- [x] `personal_update_event` — logger.error on non-(200,204) ✅
- [x] `personal_delete_event` — logger.error on non-(204,200) ✅
- [x] `personal_create_note` — logger.error on non-(200,201) ✅
- [x] `personal_send_chat_message` — logger.error on non-(200,201) ✅
- [x] `personal_create_contact` — logger.error on non-(200,201) ✅
- [x] Log format includes: tool name, user_id, status code, body[:500] ✅

---

## Minor Note (non-blocking)
- Module docstring at line 1-12 still says "Provides 18 tools" — should say 24.
  Not a runtime issue; can be fixed opportunistically.

---

## Decision: ✅ PASS

All plan tasks implemented correctly. Pattern consistency maintained throughout.
Mobile Task 3 (ConnectedAccountsScreen.tsx + version bump) still pending.
