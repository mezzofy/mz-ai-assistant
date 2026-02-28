# Release Notes — Mezzofy AI Assistant v1.0
**Release Date:** 2026-02-28
**Type:** Initial Release (General Availability)
**Prepared by:** Docs Agent

---

## Overview

Mezzofy AI Assistant v1.0 is the first production release of the AI-powered work assistant backend for the Mezzofy platform. This release delivers a complete FastAPI server that replaces all mock data in the React Native mobile app (`APP/`) with real AI-backed API calls.

The server provides department-aware AI agents (Sales, Marketing, Finance, Operations, Management) connected to Microsoft 365, real-time WebSocket streaming, file processing, task scheduling, and webhook integration — all secured with JWT authentication and Redis rate limiting.

---

## What's New

### AI Assistant Core
- **Multi-agent routing:** Incoming messages are automatically routed to the appropriate department agent (Sales, Marketing, Finance, Operations, Management) based on user department and message intent
- **Dual LLM strategy:** Chinese-language content routes to Kimi (Moonshot `moonshot-v1-128k`); English content routes to Claude (`claude-sonnet-4-6`); automatic failover between both
- **Multi-modal input:** Text, images (with OCR + Claude Vision), video (frame extraction + transcription), audio files (Whisper), live camera frames (WebSocket), PDF/DOCX/PPTX/CSV documents, and URL scraping (Playwright + BeautifulSoup)
- **Tool-use agents:** Each agent can invoke up to 5 tool iterations per request; tools cover email, Teams, calendar, LinkedIn, documents, databases, and web browsing
- **Persistent conversation history:** Sessions stored in PostgreSQL; conversation context injected into each LLM call

### Authentication & Security
- **JWT authentication:** Access tokens (60-minute expiry) + refresh tokens (7-day expiry) with Redis blacklist for revocation
- **Role-based access control:** 10 department roles with permission arrays loaded from `config/roles.yaml`
- **Rate limiting:** Redis sliding-window rate limiting (30 req/min for chat; 10 req/min for auth; 100 events/min for webhooks)
- **SSRF protection:** URL scraping blocks localhost, RFC 1918 ranges, and AWS metadata endpoint
- **CORS configuration:** Origin whitelist in `config/config.yaml`

### Real-Time Communication
- **WebSocket streaming:** `/chat/ws` supports live speech transcription, camera frame analysis, and streaming text responses
- **Speech-to-text:** Whisper-based streaming transcription for live speech input
- **Camera analysis:** Live camera frames analysed by Claude Vision in real-time

### File Management
- **Upload endpoint:** Accepts images, videos, audio, PDF, DOCX, PPTX, XLSX, CSV — saves to `/data/artifacts/` on EBS
- **Artifact registry:** All uploaded and AI-generated files tracked in PostgreSQL with ownership scoping
- **Download endpoint:** Streaming file download with ownership verification
- **S3 migration path:** Config supports `storage.type = "s3"` for future cloud storage

### Task Queue & Scheduling
- **Celery integration:** Background processing via Celery workers (Redis broker + backend)
- **Celery Beat scheduler:** 5 built-in scheduled tasks + user-defined jobs from PostgreSQL
- **Scheduler API:** Users can create up to 10 cron-based or interval-based scheduled jobs (minimum 15-minute interval)
- **Immediate trigger:** `POST /scheduler/jobs/{id}/run` executes any job outside its schedule

### Webhook Integration
- **Mezzofy platform events:** `customer_signed_up`, `customer_churned`, `order_completed`, `support_ticket_created`, `feature_released`
- **Microsoft Teams bot:** Adaptive card actions and @mentions routed to department agents
- **Generic webhooks:** Zapier, GitHub, Stripe — HMAC-SHA256 verified
- **200-first pattern:** All webhook endpoints acknowledge immediately; processing is fully asynchronous

### Microsoft 365 Integration
- **Outlook:** Send email, list inbox, create drafts, reply
- **Teams:** Post channel messages, create meetings, send direct messages
- **Calendar:** Schedule events, set reminders, query availability
- **Rate limiting:** Email capped at 30/hour (MS Graph throttles at ~50/hour; buffer is intentional)

### Admin Features
- **User management:** Create, update, deactivate users; admin-only
- **Audit log:** All auth events and sensitive actions logged to PostgreSQL `audit_log` table
- **Health endpoint:** Unauthenticated `/health` returns DB + Redis status

### Mobile API Contracts (Verified by E2E Tests)
All response shapes verified against the React Native mobile client (`APP/`):

| Contract | Endpoint | Verified |
|----------|----------|:--------:|
| `user_info.id` field (not `user_id`) | `POST /auth/login` | ✅ |
| `session_id` in chat response | `POST /chat/send` | ✅ |
| `artifacts` array in chat response | `POST /chat/send` | ✅ |
| `sessions` array in sessions list | `GET /chat/sessions` | ✅ |
| `messages` array in history | `GET /chat/history/{id}` | ✅ |
| `artifacts` + all 5 fields | `GET /files/` | ✅ |
| `artifact_id` in upload response | `POST /files/upload` | ✅ |
| `deleted: true` in delete response | `DELETE /files/{id}` | ✅ |

---

## Test Coverage

- **Total tests:** 247 passing, 0 failing
- **Unit tests:** 236 tests covering auth, chat, files, admin, webhooks, scheduler, agents, tools, middleware
- **E2E tests:** 11 tests in `TestMobileAuthFlow`, `TestMobileChatFlow`, `TestMobileFilesFlow` — multi-step chains using real JWT
- **Coverage (core modules):** API layer, gateway, webhooks, input router — 83–100%

---

## Infrastructure Requirements

| Component | Requirement |
|-----------|-------------|
| EC2 instance | t3.medium minimum (2 vCPU, 4 GB RAM) |
| OS | Ubuntu 22.04 LTS |
| Python | 3.11 |
| PostgreSQL | 15 |
| Redis | 7.x |
| Nginx | 1.18+ |
| Disk | 30 GB+ EBS (artifacts storage) |

---

## Configuration Changes from Prototype

The `APP/` React Native prototype used mock data exclusively. v1.0 requires real server endpoints. See `DEPLOYMENT.md` for the full setup guide.

**Required environment variables:** `JWT_SECRET`, `ANTHROPIC_API_KEY`, `KIMI_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `MS365_TENANT_ID`, `MS365_CLIENT_ID`, `MS365_CLIENT_SECRET`, `MS_TEAMS_TEAM_ID`, `MS_TEAMS_SENDER_USER_ID`, `LINKEDIN_COOKIE`, `WEBHOOK_SECRET`

---

## Known Limitations (v1.0)

| Limitation | Impact | Planned Fix |
|------------|--------|-------------|
| WebSocket in-process only | Multi-worker deployments can't push WS messages across workers | v1.1: Redis pub/sub for cross-worker WS push |
| DNS rebinding | URL scraping uses IP-based SSRF checks; DNS rebinding is not prevented | v1.1: Post-resolution IP validation |
| Teams bot auth | Uses simple bearer token; not full MS Bot Framework JWT validation | v1.1: Azure AD RSA key validation |
| Celery Beat restart required | New scheduler jobs created via API only activate on next Beat restart | v1.1: Hot-reload via Beat DB poll |
| Email audit log | Email sends are not yet written to `email_log` table | v1.1: Wire in processor.py |
| LinkedIn scraping | Session cookie-based; subject to LinkedIn rate limits and TOS changes | v2.0: Official LinkedIn API |

---

## Build History

| Phase | Description | Sessions |
|-------|-------------|:--------:|
| Phase 0 | Server scaffold + DB schema | 1 |
| Phase 1 | Auth + security layer | 1 |
| Phase 2 | Communication + document tools | 2 |
| Phase 3 | Media + web + database tools | 2 |
| Phase 4 | LLM layer + skills + agents | 3 |
| Phase 5 | API endpoints + core app logic | 1 |
| Phase 6 | Celery task queue + webhooks | 1 |
| Phase 7 | Server test suite | 2 |
| Phase 8 | Mobile API integration (React Native) | 3 |
| Phase 9 | End-to-end tests (247 passing) | 1 |
| Phase 10 | Documentation | 1 |

**Total:** 18 sessions

---

## Upgrade Notes

This is the initial release. No upgrade path from a previous version.

**For fresh deployment:** Follow `server/docs/DEPLOYMENT.md` end-to-end.

---

*Mezzofy AI Assistant v1.0 · Released 2026-02-28*
*Built by Mezzofy Engineering Team*
