# Review: Mobile Agent — Files Tab (Refresh + Download + In-App Viewer)
**Reviewer:** Lead Agent
**Date:** 2026-03-05
**Verdict:** ✅ PASS

---

## Files Reviewed

| File | Type | Lines |
|------|------|-------|
| `APP/src/utils/fileViewer.ts` | New | 25 |
| `APP/src/screens/FileViewerScreen.tsx` | New | 238 |
| `APP/src/screens/FilesScreen.tsx` | Modified | 290 |
| `APP/App.tsx` | Modified | 140 |
| `APP/android/app/src/main/AndroidManifest.xml` | Modified | 36 |
| `APP/package.json` | Modified | 38 |

---

## Checklist

### Mobile Review Checklist
- [x] Clean Architecture + MVVM pattern — utility is pure TS, screens follow component+hook pattern
- [x] State management correct — Zustand not applicable here (screen-local state only, correct choice)
- [x] NativeUI not applicable — file viewer uses RN core + native packages (correct for this feature)
- [x] Platform-specific optimizations — Android `PermissionsAndroid` runtime request, iOS `DocumentDirectoryPath`
- [x] Error states handled — loading, error, done states all covered for all three features
- [x] TypeScript used throughout — no raw JS files introduced
- [ ] i18n — not applicable, app has no i18n wired (strings hardcoded per established pattern)
- [ ] WatermelonDB — not applicable, offline not relevant here
- [ ] NFC — not applicable

### Cross-Agent Review Points
- [x] No scope boundary violations — only `APP/` modified
- [x] `getFileDownloadUrl` API contract unchanged — token-signed URL preserved
- [x] `ArtifactItem` type imported correctly from `../api/files`
- [x] No new server changes required for download or refresh

---

## Findings

### 🔴 Blockers
None.

### 🟡 Warnings

1. **`FilesScreen:123` — `handleDownload` in `useCallback` deps includes `downloadState`**
   - `downloadState` is a Record that changes on every progress tick (every 5% step)
   - This causes `handleDownload` to get a new reference on each progress update, which
     triggers a re-render of all download buttons in the list simultaneously
   - Functionally correct (buttons are `disabled` during download), but could cause visible
     flicker for the non-downloading buttons in a long list
   - Low risk at current scale (file lists are short); acceptable for v1.3.0

2. **`FileViewerScreen:45` — `navigation: any`, `route: any` prop types**
   - Matches existing `AIUsageStatsScreen` pattern (`navigation: any`)
   - Warning: untyped navigation params means no compile-time safety for `route.params`
   - Acceptable: codebase has no typed navigation stack (not introduced here)

3. **`FileViewerScreen:234` — `fullImage` uses `aspectRatio: 1` (hardcoded square)**
   - Portrait or landscape images will appear with letterboxing in one axis
   - Correct for a v1 viewer; dynamic sizing via `Image.getSize` would be ideal
   - Acceptable at v1.3.0 scope

### 🟢 Suggestions

1. **`fileViewer.ts:10` — extensionless filename edge case**
   - If `filename` has no dot (e.g., `"README"`), `split('.').pop()` returns `"README"`
   - This falls through all extension checks and hits the MIME fallback, which is correct
   - No change needed; behaviour is correct

2. **`FileViewerScreen:22` — `markdownStyles()` called inline in JSX without `useMemo`**
   - `colors` from `useTheme()` is stable between renders (only changes on theme switch)
   - No perceptible performance impact at this scale; `useMemo` would be nice-to-have

3. **`FilesScreen:185` — double navigation path (card `onPress` + eye button `onPress`)**
   - Both call `navigation.navigate('FileViewer', {file: f})` — consistent, not a bug
   - Card tap is a convenience affordance; eye button is the explicit intent indicator

---

## Summary

The implementation is complete, correct, and consistent with established patterns. All three
features (pull-to-refresh, download with progress, in-app viewer) are fully implemented.

- **fileViewer.ts** is clean, pure TypeScript, zero dependencies — ideal for unit testing
- **FileViewerScreen** handles all 4 viewer types (image, video, markdown, text) with proper
  loading/error states and a functional header download button
- **FilesScreen** correctly extracts `loadFiles` as a `useCallback`, wires `RefreshControl`
  with brand colors, and implements independent per-file download progress tracking
- **AndroidManifest** correctly scopes WRITE_EXTERNAL_STORAGE to API ≤ 28
- **package.json** adds the 3 required native packages

No blockers. Two warnings are minor performance/type-safety notes, both acceptable at v1.3.0.

## Next Steps
- [ ] Run `cd APP && npm install` to install react-native-fs, react-native-video, react-native-markdown-display
- [ ] Run `cd APP/android && .\gradlew.bat clean && cd .. && npx react-native run-android` for native rebuild
- [ ] Verify checklist items from the plan against the running app
- [ ] Backend Agent to implement `/llm/usage-stats` endpoint (separate plan below)
