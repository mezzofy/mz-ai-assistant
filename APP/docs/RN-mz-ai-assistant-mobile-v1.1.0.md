# Release Notes — Mezzofy AI Assistant Mobile
**Version:** 1.1.0 (versionCode 3)
**Date:** 2026-03-02
**Platform:** Android
**Build type:** Release (debug-signed, internal distribution)
**Min SDK:** 23 (Android 6.0+)

---

## Summary

v1.1.0 delivers 6 UX enhancements to the Mezzofy AI mobile app: proper Mezzofy brand theming with working dark/light mode, editable chat titles, a full-featured profile screen, speech language selection, and a clear notifications toggle.

---

## New Features

### 1. Editable Chat Titles
- Chat header auto-sets a title from the first 40 characters of the user's first message
- Tap the **pencil icon** in the chat header to edit the title inline
- Custom titles appear in Chat History, replacing the last-message fallback
- Titles persist across app restarts (AsyncStorage `@mz_chat_titles`)

### 2. Profile Screen
- **Settings → Edit Profile** now navigates to a dedicated Profile screen
- Displays: avatar (initials), full name, department badge, email, role, permissions list
- Accessible via stack navigation with slide-from-right animation

### 3. Dark / Light Theme (Working)
- **Settings → Appearance** now works with `Dark` | `Light` segmented control
- All 6 screens + shared components respond to theme change immediately
- Theme persists across restarts (AsyncStorage `@mz_settings_appearance`)

### 4. Mezzofy Orange Accent
- Brand accent color changed from teal `#00D4AA` → orange `#f97316` across all screens
- Applies to: buttons, tab bar active indicator, avatar backgrounds, send button, typing dots, active segment controls

### 5. Speech Language Selection
- **Settings → Speech Language** shows `English` | `Chinese` segmented control
- English → `en-US` locale; Chinese → `zh-CN` locale
- Voice recognition in Chat screen uses the selected language

### 6. Notifications Toggle
- **Settings → Notifications** shows `On` | `Off` segmented control
- Replaces the previous toggle row with a consistent segmented control style
- Setting persists across restarts

---

## Technical Changes

| Area | Change |
|------|--------|
| `src/utils/theme.ts` | Added `LIGHT_THEME`, `ThemeColors` type; accent `#00D4AA` → `#f97316` |
| `src/hooks/useTheme.ts` | New hook — returns `BRAND` or `LIGHT_THEME` based on appearance setting |
| `src/screens/ProfileScreen.tsx` | New screen |
| `src/stores/chatStore.ts` | Added `sessionTitles`, `loadTitles()`, `setSessionTitle()` |
| `src/screens/ChatScreen.tsx` | Editable title header, dynamic theme, speech locale |
| `src/screens/HistoryScreen.tsx` | Custom titles, dynamic theme |
| `src/screens/SettingsScreen.tsx` | Profile nav, segmented controls for 3 settings, dynamic theme |
| `src/screens/FilesScreen.tsx` | Dynamic theme |
| `src/screens/LoginScreen.tsx` | Dynamic theme |
| `src/screens/CameraScreen.tsx` | Dynamic theme |
| `src/components/shared/DeptBadge.tsx` | Dynamic theme |
| `App.tsx` | Profile screen in stack, dynamic NavigationContainer theme |
| `android/app/build.gradle` | versionCode 2→3, versionName 1.0.1→1.1.0 |

**No backend (server) changes required.**

---

## Known Limitations

- Signing: APK signed with debug keystore (suitable for internal distribution, not Play Store)
- API: Server URL uses HTTP (`http://3.1.255.48:8000`) — `android:usesCleartextTraffic="true"` in manifest
- WS audio streaming (PCM chunks) deferred to v2.0 — speech uses local Voice STT → REST path

---

## APK Location

```
APP/android/app/build/outputs/apk/release/app-release.apk
```
