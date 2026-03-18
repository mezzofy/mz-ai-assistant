# STATUS — mz-ai-assistant
**Date:** 2026-02-28
**Lead Agent:** 🎯 Lead
**Overall Progress:** 100% ✅ ALL PHASES COMPLETE (Phase 0–10)

---

## Current Phase

**Phase 10: Docs** ← ✅ COMPLETE (2026-02-28)
- **Agent:** Docs Agent
- **Deliverables:** API.md, DEPLOYMENT.md, openapi.yaml, RN-mz-ai-assistant-v1.0.md
- **Status:** ✅ All documentation written

**Phase 9: E2E Tests** ← ✅ COMPLETE (2026-02-28)
- xfail cleanup: done (already removed in previous session)
- Base suite: 236 passed
- E2E tests: 11 tests (TestMobileAuthFlow + TestMobileChatFlow + TestMobileFilesFlow)
- Final suite: 247 passed, 0 failed
- Quality gate: ✅ PASSED — all 8 API contracts verified

**Phase 8: Mobile Integration** ← ✅ COMPLETE (2026-02-28)
- **Session 8A:** ✅ API layer + auth (10 files)
- **Session 8B:** ✅ Chat API + chatStore + ChatScreen (5 files + hooks fix)
- **Session 8C:** ✅ FilesScreen + HistoryScreen + CameraScreen (4 files)
- **Quality gate:** ✅ PASSED — all mocks removed, 0 TypeScript errors

---

## What Exists Today

| Layer | Status | Notes |
|-------|--------|-------|
| Mobile app (`APP/`) | ✅ Phase 8 complete | 6 screens, real API calls throughout — all DEMO_* mocks removed. Native packages installed: image-picker, document-picker, voice. APK builds clean (2026-03-01). |
| Server (`/server/`) | 🔄 In progress | Phase 0+1+2+3 complete — scaffold + auth + 40 tools built |
| Documentation | ✅ Complete | APP.md, LLM.md, AGENTS.md, TOOLS.md, CONFIG.md, SECURITY.md, MEMORY.md, SKILLS.md, INFRASTRUCTURE.md, TESTING.md |
| DB schema | ✅ Created | 9 PostgreSQL tables via `server/scripts/migrate.py` |
| Auth layer | ✅ Complete | JWT, RBAC, rate limiting, audit log, gateway middleware |
| Tools layer | ✅ Complete | 40 tools registered (+ 2 WebSocket-only) across 11 tool files |

---

## 10-Phase Build Plan

| Phase | Agent | Sessions | Depends On | Status |
|-------|-------|:--------:|------------|--------|
| 0: Scaffold + DB | Infra | 1 | — | ✅ Complete |
| 1: Auth + Security | Backend | 1 | Phase 0 | ✅ Complete (PASSED) |
| 2: Comm + Doc Tools | Backend | 2 | Phase 1 | ✅ Complete (PASSED) |
| 3: Media + Web + DB Tools | Backend | 2 | Phase 1 | ✅ Complete (PASSED) |
| 4: LLM + Skills + Agents | Backend | 3 | Phase 2+3 | ✅ Complete (PASSED) |
| 5: API + Core App | Backend | 3 | Phase 4 | ✅ Complete (PASSED) |
| 6: Scheduler + Webhooks | Backend | 2 | Phase 5 | ✅ Complete (PASSED) |
| 7: Server Tests | Tester | 2 | Phase 6 | ✅ Complete (BUG-001 ✅ fixed — xfail cleanup pending) |
| 8: Mobile Integration | Mobile | 3 | Phase 7 | ✅ Complete (PASSED) |
| 9: E2E Tests | Tester | 1 | Phase 8 | ✅ Complete (PASSED) |
| 10: Docs | Docs | 1 | Phase 9 | ✅ Complete |

**Total estimated sessions: 23–26**

---

## Recently Completed (2026-03-18)

- ✅ **Mission Control Portal v1.33.0 — DEPLOYED to EC2** (commit ae04c18)
  - Created: `server/app/api/admin_portal.py` — 20 endpoints under `/api/admin-portal/*`
    - Auth: `GET /api/admin-portal/auth/me`
    - Dashboard: sessions (30s poll), LLM usage w/ budget gauges, system vitals (psutil), agent status
    - Scheduler: list jobs, run history, manual trigger → Celery, toggle active
    - Agents: registry + RAG memory file listing per department
    - Files: paginated list + delete (physical + DB)
    - Users: list, create w/ invite email, get, update, soft-delete + token blacklist
  - Updated: `server/app/main.py` — router registered at `/api/admin-portal`
  - Updated: `server/scripts/migrate.py` — `users.invite_token VARCHAR(64)` + `users.deleted_at TIMESTAMPTZ`
  - Updated: `server/config/config.example.yaml` — `admin_portal:` block with LLM budgets
  - Updated: `server/requirements.txt` — psutil==5.9.8
  - Updated: `server/config/nginx.conf` — `/mission-control` static + `/api/admin-portal/` proxy
  - Created: `server/tests/test_admin_portal.py` — 8 unit tests
  - Created: `portal/` — full React+TS+Vite portal app (20 source files, 289KB build)
    - Pages: Login, OTP, Dashboard (pixel art agent office canvas), Scheduler, Agents, Files, Users
    - Dark theme: bg #0A0E1A · accent #6C63FF · teal #00D4AA
    - Auth: reuses `/auth/*`; Zustand in-memory only; `AdminRoute` guard

## Recently Completed (2026-03-06)

- ✅ **HRAgent added (v1.1)** — Backend + Docs: 6th department agent (`hr`)
  - Created: `server/app/agents/hr_agent.py` — HR agent with 8 workflows (payroll, leave, recruitment, weekly summary, headcount, onboarding, offboarding, general)
  - Updated: `server/app/agents/agent_registry.py` — `"hr": HRAgent` added to AGENT_MAP
  - Updated: `server/app/router.py` — HR webhook event routing (`employee_onboarded`, `employee_offboarded`, `leave_request_submitted`)
  - Created: `server/tests/test_hr_agent.py` — 28 new tests (all passing)
  - Updated: `AGENTS.md`, `APP/README.md`, `docs/STATUS`, `memory.md` — documentation reflects 6 agents
  - Created: `docs/RN-mz-ai-assistant-v1.1.md` — release notes for v1.1.0
  - **Test suite total:** 288 tests passing (was 260)
  - **Pending (Backend Agent):** `config/roles.yaml` (hr_viewer/hr_manager), `app/core/rbac.py` (VALID_ROLES), `tasks/beat_schedule.py` (2 new jobs), `config/config.example.yaml` (#hr channel)

## Recently Completed (2026-02-28)

- ✅ **Phase 10 COMPLETE** — Docs Agent: Full documentation suite written
  - Created: `server/docs/API.md` — all endpoints with request/response examples
  - Created: `server/docs/DEPLOYMENT.md` — EC2 setup guide, service management, env var checklist
  - Created: `server/docs/openapi.yaml` — OpenAPI 3.1 header + pointer to `/docs` live spec
  - Created: `docs/RN-mz-ai-assistant-v1.0.md` — v1.0 release notes

- ✅ **Phase 9 COMPLETE** — Tester Agent: E2E mobile flow tests (11 tests, 247 total passing)
  - Created: `server/tests/test_e2e_mobile.py` (TestMobileAuthFlow×4, TestMobileChatFlow×3, TestMobileFilesFlow×4)
  - All 8 API contracts verified (user_info.id, session_id, artifacts, sessions, messages, deleted: true)
  - Quality gate: ✅ PASSED

- ✅ **Phase 8 COMPLETE (8C)** — Mobile Agent: FilesScreen + HistoryScreen + CameraScreen (4 files created/replaced)
  - Created: `APP/src/api/files.ts` (listFilesApi, uploadFileApi, deleteFileApi, getFileDownloadUrl)
  - Replaced: `FilesScreen.tsx` (real GET /files/), `HistoryScreen.tsx` (loadSessions + navigate), `CameraScreen.tsx` (mzWs lifecycle)
  - Quality gate: ✅ PASSED — all Phase 8 criteria met, 0 new TypeScript errors

- ✅ **Phase 8 Session 8B COMPLETE** — Mobile Agent: Chat API layer + chatStore + ChatScreen real wiring (5 files + hooks fix)
  - Created: `APP/src/api/chat.ts` (sendText/Url/Media/getSessions/getHistory), `APP/src/api/websocket.ts` (MzWebSocket + mzWs singleton)
  - Replaced: `APP/src/stores/chatStore.ts` (real API, atomic set, sessionId), `APP/src/screens/ChatScreen.tsx` (DEMO_RESPONSES removed, hooks fixed)
  - Fixed: authStore.ts ISSUE-1 (freshAccess re-read after getMeApi), ChatScreen hooks violation (2x useEffect moved before null guard)

- ✅ **Phase 8 Session 8A COMPLETE** — Mobile Agent: API layer + auth integration (10 files)
  - Created: `APP/src/config.ts`, `APP/src/storage/tokenStorage.ts`, `APP/src/api/api.ts`, `APP/src/api/auth.ts`
  - Replaced: `APP/src/stores/authStore.ts` (real JWT state machine), `APP/src/screens/LoginScreen.tsx` (real login + error banner)
  - Updated: `APP/App.tsx` (session restore useEffect), `APP/src/screens/SettingsScreen.tsx` (null guard + async logout), `APP/src/screens/ChatScreen.tsx` (null guard)

- ✅ **BUG-001 FIXED** — Backend Agent: `app/core/auth.py _build_payload()` now uses `user.get("id") or user.get("user_id")` — token refresh returns 200
- ✅ **Phase 7 COMPLETE** — Tester Agent: 236 tests (235 pass + 1 xfail), 9 test files, core coverage 83–100%, BUG-001 documented
- ✅ **Phase 7 quality gate PASSED** — All 5 dept workflows ✅; security tests ✅; core API/gateway/webhooks/input >80% coverage ✅
- ✅ **Phase 6 quality gate PASSED** — 6 files: celery_app, tasks, webhook_tasks, beat_schedule, webhooks.py full, scheduler.py full
- ✅ **Phase 6 COMPLETE** — Backend Agent: Celery task queue + 3 webhook endpoints + scheduler CRUD API (1 session: 6A)
- ✅ **Phase 5 quality gate PASSED** — 20 files: router, 8 input handlers, context layer, output layer, chat.py + files.py + admin.py full APIs, main.py updated
- ✅ **Phase 5 COMPLETE** — Backend Agent: full REST + WebSocket pipeline operational (1 session: 5A)
- ✅ **Phase 4 quality gate PASSED** — 11 import path blockers fixed (app.tools.comm.* → communication/document; PdfOps→PDFOps; PptxOps→PPTXOps)
- ✅ **Phase 4 COMPLETE** — Backend Agent: LLM layer + 7 skill pairs + 6 agent files (20 new files)
- ✅ **Phase 3 COMPLETE** — Backend Agent: 42 tools implemented (40 in executor + 2 WebSocket-only)
- ✅ Phase 3 quality gate PASSED (after fixes: pytesseract/Whisper run_in_executor + AsyncAnthropic + MAKE_INTERVAL SQL fix)

### Phase 3 Deliverables
- `server/app/tools/media/image_ops.py` — ImageOps, 4 tools (ocr_image, analyze_image, resize_image, extract_exif)
- `server/app/tools/media/video_ops.py` — VideoOps, 4 tools
- `server/app/tools/media/audio_ops.py` — AudioOps, 4 tools (transcribe_audio, detect_language, convert_audio, get_audio_info)
- `server/app/tools/media/speech_ops.py` — SpeechOps, 2 tools (WebSocket-only)
- `server/app/tools/web/browser_ops.py` — BrowserOps, 3 tools
- `server/app/tools/web/scraping_ops.py` — ScrapingOps, 4 tools
- `server/app/tools/web/linkedin_ops.py` — LinkedInOps, 2 tools
- `server/app/tools/database/db_ops.py` — DatabaseOps, 4 tools
- `server/app/tools/database/crm_ops.py` — CRMOps, 7 tools
- `server/app/tools/mezzofy/data_ops.py` — MezzofyDataOps, 4 tools
- `server/app/tools/mezzofy/knowledge_ops.py` — KnowledgeOps, 4 tools
- `server/app/tools/tool_executor.py` — All Phase 3 registrations uncommented

### Phase 4 Deliverables
- `server/app/llm/anthropic_client.py` — AnthropicClient (claude-sonnet-4-6, tool loop ≤5 iter)
- `server/app/llm/kimi_client.py` — KimiClient (moonshot-v1-128k, Chinese language routing)
- `server/app/llm/llm_manager.py` — LLMManager + module-level init()/get() singleton
- `server/app/skills/skill_loader.py` — SkillLoader (YAML scan + Python class instantiation)
- `server/app/skills/skill_registry.py` — module-level singleton init()/get()
- `server/app/skills/available/` — 7 × YAML+Python pairs: linkedin_prospecting, financial_reporting, pitch_deck_generation, email_outreach, content_generation, web_research, data_analysis
- `server/app/agents/base_agent.py` — BaseAgent abstract (can_handle, execute, _load_skill, permission check)
- `server/app/agents/finance_agent.py` — FinanceAgent
- `server/app/agents/sales_agent.py` — SalesAgent (4 workflows)
- `server/app/agents/marketing_agent.py` — MarketingAgent
- `server/app/agents/support_agent.py` — SupportAgent (3 workflows)
- `server/app/agents/management_agent.py` — ManagementAgent (KPI aggregation)
- `server/app/agents/agent_registry.py` — AGENT_MAP + get_agent_for_task() (proactive — unblocks Phase 5 router)

### Previously Completed (Phase 2)
- `server/app/tools/communication/outlook_ops.py` — 8 tools
- `server/app/tools/communication/teams_ops.py` — 4 tools
- `server/app/tools/communication/push_ops.py` — 1 tool
- `server/app/tools/document/pdf_ops.py` — 3 tools
- `server/app/tools/document/pptx_ops.py` — 2 tools
- `server/app/tools/document/docx_ops.py` — 2 tools
- `server/app/tools/document/csv_ops.py` — 2 tools

---

## In Progress

None — all 10 phases complete.

---

## Next Phase

**Project Complete.** mz-ai-assistant v1.0 is ready for production deployment.

See `server/docs/DEPLOYMENT.md` for EC2 setup instructions.
See `docs/RN-mz-ai-assistant-v1.0.md` for release notes.

### Phase 7 Deliverables
- `server/tests/conftest.py` — shared fixtures (client, tokens, mocks, DB overrides)
- `server/tests/test_auth.py` — 26 auth tests (login, JWT, RBAC, refresh, logout, /me)
- `server/tests/test_chat_workflow.py` — 20 tests (5 dept workflows, routing, SSRF)
- `server/tests/test_scheduler.py` — 24 tests (CRUD, limits, cron validation)
- `server/tests/test_webhooks.py` — 22 tests (HMAC, Teams, custom, events)
- `server/tests/test_security.py` — 25 tests (SQL inj, path traversal, JWT, SSRF, RBAC)
- `server/tests/test_llm_routing.py` — 20 tests (provider, failover, tool loop, tokens)
- `server/tests/test_admin.py` — 23 tests (users CRUD, audit log, health dashboard)
- `server/tests/test_files.py` — 15 tests (upload/list/get/delete, MIME validation)
- `server/tests/test_input_handlers.py` — 41 tests (URL validation, input routing, handlers)
- `server/tests/results/phase7-report.md` — full test + coverage report

### Phase 6 Deliverables
- `server/app/tasks/celery_app.py` — Celery app, Redis broker, 10-min limits, task_acks_late
- `server/app/tasks/tasks.py` — process_agent_task (asyncio.run), health_check
- `server/app/tasks/webhook_tasks.py` — handle_mezzofy_event, handle_teams_mention, handle_custom_event
- `server/app/tasks/beat_schedule.py` — 5 static schedules + DatabaseScheduler + DB job loader
- `server/app/webhooks/webhooks.py` — HMAC-verified Mezzofy/Teams/custom + events audit
- `server/app/webhooks/scheduler.py` — CRUD + manual trigger (max 10 jobs, min 15-min interval)

### Phase 5 Deliverables
- `server/app/router.py` — source-aware agent dispatch (mobile/webhook/scheduler)
- `server/app/core/config.py` — YAML config loader, ${ENV_VAR} resolver, singleton
- `server/app/input/input_router.py` + 7 handlers — text, image, video, audio, file, url, camera, speech
- `server/app/context/session_manager.py` — conversation history in `conversations` table
- `server/app/context/artifact_manager.py` — file registry in `artifacts` table, ownership-scoped
- `server/app/context/processor.py` — post-agent result assembly + DB writes
- `server/app/output/output_formatter.py` — REST + WS response envelopes
- `server/app/output/stream_handler.py` — WSConnectionManager singleton
- `server/app/api/chat.py` — POST /chat/send, send-media, send-url, GET sessions/history, DELETE session, WS /chat/ws
- `server/app/api/files.py` — upload, list, get (FileResponse), delete (DB only)
- `server/app/api/admin.py` — users CRUD, audit log, health dashboard
- `server/app/main.py` — startup inits llm_manager + skill_registry

---

## Quality Gates (Lead Agent Reviews)

| After Phase | Gate Status | Criteria |
|-------------|-------------|---------|
| Phase 0 | ✅ PASSED | 9 tables + 13 indexes ✅; 10 roles ✅; 47 packages ✅; setup.sh 10 steps ✅; 20 stubs ✅ |
| Phase 1 | ✅ PASSED | All fixes verified: rate_limit_auth on login ✅; CORS middleware order ✅; dead code cleaned ✅; ZADD collision fixed ✅ |
| Phase 2 | ✅ PASSED | All 22 tools implemented; push run_in_executor fix ✅; teams sender_user_id fix ✅ |
| Phase 3 | ✅ PASSED | pytesseract/Whisper run_in_executor ✅; AsyncAnthropic ✅; MAKE_INTERVAL SQL fix ✅ |
| Phase 4 | ✅ PASSED | LLM routing ✅; tool loop ≤5 iter ✅; all 5 agents + skills ✅; agent_registry ✅; 11 import fixes verified ✅ |
| Phase 5 | ✅ PASSED | REST + WS pipeline ✅; SSRF protection ✅; ownership-scoped artifacts ✅; JWT coverage ✅; SQL injection safe ✅ |
| Phase 6 | ✅ PASSED | Beat weekly_kpi_report ✅; webhooks 200-first + Celery enqueue ✅; scheduler CRUD ✅; HMAC auth ✅; task_acks_late ✅ |
| Phase 7 | ✅ PASSED | 235 passed + 1 xfailed; all 5 dept workflows ✅; security ✅; core coverage 83–100% ✅; BUG-001 documented |
| Phase 9 | ✅ PASSED | 247 passed, 0 failed; 11 E2E tests; all 8 API contracts verified ✅ |
| Phase 10 | ✅ PASSED | API.md ✅; DEPLOYMENT.md ✅; openapi.yaml ✅; RN-mz-ai-assistant-v1.0.md ✅ |

---

## Post-Deployment (2026-03-10)

- **BUG-005 FIXED:** ManagementAgent ran KPI dashboard workflow for file uploads (PDF) even when the message contained a KPI keyword like "summary"
  - **File:** `server/app/agents/management_agent.py`
  - **Root cause:** `execute()` checked KPI keywords before checking whether a file was attached; a "summarise this PDF" message matched `_KPI_KEYWORDS` ("summary") → KPI workflow ran, ignoring the uploaded document entirely
  - **Fix:** Added early-exit check — if `anthropic_file_id` is set OR `input_type == "file"`, route directly to `_general_response()` before any keyword check
  - **Tests:** `TestManagementAgentBug004` (4 tests including BUG-005 regression) in `server/tests/test_input_handlers.py`

- **BUG-005 (LLM side) FIXED:** When a PDF was uploaded via Anthropic Files API, Claude still called `search_user_files` + `read_pdf` unnecessarily
  - **File:** `server/app/llm/llm_manager.py`
  - **Root cause:** System prompt's FILE SEARCH RULE ("MUST call search_user_files FIRST") applied unconditionally — even when the file was already in the conversation as a native document block
  - **Fix:** `_build_system_prompt()` now appends `_ATTACHED_FILE_DIRECTIVE` when `task["anthropic_file_id"]` is set — explicitly telling Claude the document is already in context and tool calls are not needed for it. PDFs are also passed as native `{"type": "document", ...}` content blocks (not extracted text).
  - **Tests:** `TestSystemPromptFileAttachment` (3 tests) in `server/tests/test_llm_routing.py`

- **BUG-004 FIXED:** `image_handler.py` was passing `image_path` (a temp file path) to `ImageOps.execute()` instead of `image_bytes` (base64). Temp file was written then cleaned up, but the path was already invalid by the time the tool used it.
  - **Fix:** `handle_image()` now encodes bytes as base64 and passes `image_bytes=` directly to `ocr_image` and `analyze_image`
  - **Tests:** `TestImageHandlerBug003` (4 tests) in `server/tests/test_input_handlers.py`

- **Architecture review:** Full end-to-end chat flow documented — `docs/TD-chat-flow-v1.0.md` updated to v1.1
  - Added: PDF → Files API native doc block path (Layer 3), `_ATTACHED_FILE_DIRECTIVE` system prompt addition (Layer 7), ManagementAgent file routing (Layer 6)

- **Test suite:** ~299 tests passing (was 288 after v1.1 HRAgent; +11 new regression tests)

---

## Post-Deployment (2026-03-09)

- ✅ **Chat Flow Map documented** — `docs/TD-chat-flow-v1.0.md` created
  - Full 10-layer flow map from user input → response, verified against live code
  - Documents all entry points, sync/async fork, agent selection, tool-calling loop, WebSocket path, background delivery
  - Source of truth for onboarding and architecture reviews

- **BUG-003 FIXED:** `apac_signals` over-broad Kimi routing — English city names caused Claude → Kimi misroute
  - **File:** `server/app/llm/llm_manager.py`
  - **Root cause:** `"singapore"`, `"malaysia"`, `"taiwan"`, `"hong kong"`, `"asia pacific"` in `apac_signals` set matched general English business queries
  - **Fix:** Removed those 5 English terms; kept only exclusive Chinese-market signals (`"china"`, `"chinese market"`, `"mainland"`, `"apac"`, `"mandarin"`, `"中国"`, `"亚太"`, `"新加坡"`)
  - **Commit:** `63db1b7` — deployed to EC2 and git-synced

## Post-Deployment (2026-03-01)

- **BUG-002 FIXED:** ManagementAgent routing bug — AI always returned KPI dashboard
  - **File:** `server/app/agents/management_agent.py`
  - **Root causes (3):** (1) `can_handle()` returned `True` for ANY management-dept user with no keyword check; (2) `execute()` always called `_kpi_dashboard_workflow()` for all non-scheduler tasks; (3) KPI prompt had no real date → LLM output contained `{Current Date}` placeholder
  - **Fix:** `can_handle()` now requires `is_management_user AND has_keyword`; `execute()` adds intent check routing non-KPI messages to `_general_response()`; `date.today().strftime(...)` injected into KPI prompt
  - **Status:** Deployed and running on EC2 (`ubuntu@ip-172-31-27-67:8000`)
  - **Regression tests:** `TestManagementAgentUnit` (9 tests) added to `server/tests/test_chat_workflow.py`

---

## Blockers

None — project complete.

---

## Key Reference Files

| File | Contains |
|------|---------|
| `INFRASTRUCTURE.md` | AWS architecture, full server folder structure, PostgreSQL schema, systemd services |
| `CONFIG.md` | All config keys, environment variables, `requirements.txt` packages |
| `MEMORY.md` | 9 DB tables, Session Manager, Artifact Manager, CRM lead lifecycle |
| `SECURITY.md` | JWT spec, RBAC roles (10 roles), rate limits, audit log format |
| `APP.md` | Gateway, Router, Input pipeline, Output layer, Context layer, all REST+WS endpoints |
| `LLM.md` | Claude + Kimi clients, LLM Manager, failover logic, token budgets |
| `AGENTS.md` | 6 department agents (Sales, Marketing, Finance, Support, Management, HR) + base agent |
| `SKILLS.md` | 7 skills (presentation, email, LinkedIn, etc.) with YAML + Python spec |
| `TOOLS.md` | 31 tools across 9 categories — full function signatures |
| `TESTING.md` | pytest suite spec — auth tests, workflow tests, scheduler, webhook, security, LLM |

---

## Build Plan Location

Full phased plan with session breakdowns, file lists, and quality gates:
`.claude/coordination/plans/mz-ai-assistant-server-v1.0.md`

---

## Notes

- **Mobile app:** `APP/` is a complete UI prototype. Phase 8 will replace all `DEMO_RESPONSES` and `setTimeout()` with real API calls.
- **Architecture:** FastAPI on EC2 (t3.xlarge, Singapore), PostgreSQL 15, Redis 7, Celery workers × 4, Nginx SSL termination.
- **LLM strategy:** Anthropic Claude (default) + Kimi (Chinese language detection) with automatic failover.
