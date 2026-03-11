# Review: ms-contacts-write-fix-plan — Mobile Task 3 (v1.18.0)
**Date:** 2026-03-12
**Reviewer:** Lead Agent
**Commits reviewed:** `ae49c9f` (Task 3a+3b), `6f2bc2c` (SettingsScreen label fix)

---

## Checklist

### Task 3a — Contacts pill (ConnectedAccountsScreen.tsx line 178)
- [x] Array changed from `['Mail', 'Calendar', 'Notes', 'Teams']` to `['Mail', 'Calendar', 'Notes', 'Teams', 'Contacts']` ✅
- [x] 5 pills render correctly — all use existing `scopePill`/`scopeText` styles ✅
- [x] No new style definitions needed (Contacts shares same pill style as others) ✅

### Task 3b — Info text update (line 215–218)
- [x] Updated to mention contacts: "manage your contacts on your behalf" ✅
- [x] Also updated disconnect confirmation dialog (line 119) to include "contacts" ✅ (bonus — non-required but correct)
- [x] Matches plan spec ✅

### Task 3c — Version bump
- [x] `APP/android/app/build.gradle`: versionCode 30, versionName "1.18.0" ✅
- [x] `APP/package.json`: version "1.18.0" ✅
- [x] `APP/src/screens/SettingsScreen.tsx`: label "Mezzofy AI Assistant v1.18.0" ✅ (fixed in 6f2bc2c)

### APK Build
- [x] `npm run build:android:release` → BUILD SUCCESSFUL (1m 2s) ✅
- [x] `output-metadata.json`: versionCode 30, versionName "1.18.0" ✅
- [x] APK size: ~60 MB (consistent with previous releases) ✅

---

## Decision: ✅ PASS

All Mobile Task 3 items complete. No regressions introduced.

---

## Plan Status: COMPLETE

| Task | Agent | Status |
|------|-------|--------|
| 1a — Contacts scopes (config.py) | Backend | ✅ DONE |
| 1b — 4 Contact tools (personal_ms_ops.py) | Backend | ✅ DONE |
| 1c — System prompt update (llm_manager.py) | Backend | ✅ DONE |
| 2a — Diagnostic tool (personal_check_token_scopes) | Backend | ✅ DONE |
| 2b — Write logging on all write handlers | Backend | ✅ DONE |
| 3a — Contacts pill (ConnectedAccountsScreen.tsx) | Mobile | ✅ DONE |
| 3b — Info text update | Mobile | ✅ DONE |
| 3c — Version bump to 1.18.0 / versionCode 30 | Mobile | ✅ DONE |

---

## Remaining Steps (User Actions)

1. **Push to GitHub** (via GitHub Desktop — eric-design branch)

2. **Deploy to EC2:**
   ```bash
   ssh -i mz-ai-key.pem ubuntu@3.1.255.48
   cd /home/ubuntu/mz-ai-assistant
   git pull origin eric-design
   sudo systemctl restart mezzofy-api.service
   ```

3. **Azure AD app registration** (REQUIRED for write ops to work):
   - Add delegated permissions: `Contacts.Read`, `Contacts.ReadWrite`, `Mail.Send`,
     `Calendars.ReadWrite`, `Notes.ReadWrite`, `Chat.ReadWrite`
   - After adding: user must Disconnect + Reconnect in Settings → Connected Accounts

4. **Install APK:** `APP/android/app/build/outputs/apk/release/app-release.apk`

5. **Verify:** Ask Chat "What Microsoft permissions do you have?" — should list all scopes including Contacts
