# Release Notes — Mezzofy AI Assistant Mobile v1.1.1
**Date:** 2026-03-04
**Type:** Patch
**Platform:** Android
**Build:** versionCode 4

---

## Changes

### Icon Update
- Launcher icon background color changed from teal (`#00D4AA`) to Mezzofy Orange (`#f97316`)
- Adaptive icon support added (`mipmap-anydpi-v26/`) for Android 8.0+ (API 26+)
- `colors.xml` accent updated from `#00D4AA` to `#f97316` — now consistent with in-app theme

### No Functional Changes
- No API changes, no backend changes, no behavior changes
- Icon design unchanged (white "M" on solid background)

---

## Files Changed

| File | Change |
|------|--------|
| `android/app/src/main/res/values/colors.xml` | accent: `#00D4AA` → `#f97316` |
| `android/app/src/main/res/drawable/ic_launcher_background.xml` | New — solid orange background shape |
| `android/app/src/main/res/drawable/ic_launcher_foreground.xml` | New — white "M" vector (108dp canvas) |
| `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` | New — adaptive icon definition |
| `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml` | New — adaptive icon (round) definition |
| `android/app/build.gradle` | versionCode 3→4, versionName "1.1.0"→"1.1.1" |
| `package.json` | version "1.1.0"→"1.1.1" |
| `src/screens/SettingsScreen.tsx` | Version display: v1.1.0→v1.1.1 |

---

## Upgrade Notes
- Direct APK replacement — uninstall not required
- Icon update takes effect immediately after install
- Raster PNGs in `mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/` remain as-is (unused on Android 8.0+; serve as fallback for Android < 8.0)
