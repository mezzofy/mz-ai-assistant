# Release Notes — mz-ai-assistant v1.0.1
**Date:** 2026-03-02
**Type:** Patch — Bug fixes + Mobile enhancements
**Branch:** eric-design → main
**Commit:** 0c7447b

---

## Bug Fixes

### BUG-003 — Image handler now passes `image_bytes` to vision tools
**File:** `server/app/input/image_handler.py`

Previously, `handle_image()` was calling OCR and vision tools with `image_path`
(a file path string), but the tool implementations expect `image_bytes` (a base64-encoded
string). As a result, OCR text extraction and vision analysis both silently failed on every
uploaded image, returning empty results.

**Fix:** The handler now base64-encodes the raw file bytes immediately on receipt and passes
`image_bytes=image_b64` to both `ImageOps.ocr_image()` and `ImageOps.analyze_image()`.

**Impact:** OCR and vision analysis now work correctly for all uploaded images. The enriched
`extracted_text` (image description + extracted OCR text + user message) is correctly
assembled and forwarded to the LLM.

---

### BUG-004 — ManagementAgent general response now uses enriched `extracted_text`
**File:** `server/app/agents/management_agent.py`

Previously, `ManagementAgent._general_response()` always passed raw `task["message"]` to
the LLM, discarding any enriched context produced by upstream input handlers (image OCR,
vision description, audio transcription, etc.).

**Fix:** `_general_response()` now reads `task.get("extracted_text") or task.get("message", "")`,
matching the pattern used by other agents. When an image or audio file was processed before
routing to the Management Agent, the enriched context now reaches the LLM correctly.

**Impact:** Image and media context is no longer silently discarded for management department
queries that do not match KPI keywords.

---

## New Features (Mobile — Android)

### CameraScreen — Real-time camera capture with server vision analysis
**File:** `APP/src/screens/CameraScreen.tsx`

New screen that opens the device camera, captures a frame, base64-encodes it, and sends
it to the server as a WebSocket `camera_frame` event for real-time vision analysis.
The server response is displayed inline in the screen.

**Usage:** Available from the ChatScreen via the camera icon in the input toolbar.

---

### ChatScreen — Image, video, and audio media picker
**File:** `APP/src/screens/ChatScreen.tsx`

ChatScreen now supports three media attachment modes via `react-native-image-picker`:

| Mode | Action | Server endpoint |
|------|--------|----------------|
| Photo | Launch camera or select from gallery | `POST /api/send-media` |
| Video | Record or select from gallery | `POST /api/send-media` |
| Audio | Select audio file from storage | `POST /api/send-media` |

Selected media is uploaded via the REST `send-media` endpoint. The server processes it
through the appropriate input handler (image/video/audio) and responds in the chat thread.

---

### AndroidManifest — Full media permissions
**File:** `APP/android/app/src/main/AndroidManifest.xml`

All required permissions declared for camera and media access:

| Permission | Purpose |
|-----------|---------|
| `CAMERA` | CameraScreen live capture |
| `RECORD_AUDIO` | Video recording with audio |
| `READ_EXTERNAL_STORAGE` | Gallery access (API < 33) |
| `WRITE_EXTERNAL_STORAGE` | Saving captured media (API < 29) |
| `READ_MEDIA_IMAGES` | Gallery photo access (API 33+) |
| `READ_MEDIA_VIDEO` | Gallery video access (API 33+) |
| `READ_MEDIA_AUDIO` | Audio file access (API 33+) |

---

## Android Build

| Attribute | Value |
|-----------|-------|
| versionCode | 2 |
| versionName | 1.0.1 |
| Build type | debug |
| APK | `APP/android/app/build/outputs/apk/debug/app-debug.apk` |
| APK size | 145 MB |
| Gradle tasks | 289 (250 executed, 39 up-to-date) |
| Build time | 2m 40s |
| Build result | SUCCESS |

---

## Server Deployment

| Attribute | Value |
|-----------|-------|
| EC2 instance | `ubuntu@3.1.255.48` (ap-southeast-1) |
| Deployed branch | `eric-design` @ `0c7447b` |
| Services restarted | `mezzofy-api`, `mezzofy-celery`, `mezzofy-beat` |
| Health check | `{"status":"ok","version":"1.0.0","services":{"database":"ok","redis":"ok"}}` |
| Deploy status | SUCCESS |

---

## Test Coverage

| Metric | Value |
|--------|-------|
| Total tests | 261 (260 passing + 1 known skip) |
| New regression tests | 5 (BUG-003 × 3, BUG-004 × 2) |
| Previously passing | 255 |
| Known failure | `test_windows_path_traversal_stripped` — pre-existing; Linux EC2 does not strip `\` in `Path().name` (Windows-only behavior) |

---

## Files Changed

| File | Change |
|------|--------|
| `server/app/input/image_handler.py` | BUG-003: pass `image_bytes` (base64) instead of `image_path` |
| `server/app/agents/management_agent.py` | BUG-004: use `extracted_text` with fallback to `message` |
| `server/tests/test_input_handlers.py` | Regression tests for BUG-003 |
| `server/tests/test_management_agent.py` | Regression tests for BUG-004 |
| `APP/src/screens/CameraScreen.tsx` | New: real-time camera capture + WebSocket frame |
| `APP/src/screens/ChatScreen.tsx` | New: image/video/audio picker modes |
| `APP/android/app/src/main/AndroidManifest.xml` | New: camera + media permissions |
| `APP/android/app/build.gradle` | Version bump: versionCode 2, versionName 1.0.1 |

---

## Upgrade Notes

**Server:** No schema changes. No migration required. Restart services only.

**Mobile:** Users must re-install the APK (versionCode incremented from 1 → 2).
On first launch, Android will prompt for camera and media permissions — grant all for
full functionality.

---

*Generated by Docs Agent — mz-ai-assistant release process*
