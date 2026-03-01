# Project Memory — Mezzofy Agent Team

> **Purpose:** Persistent decisions that ALL agents in ALL sessions must know.
> **Updated by:** Lead Agent (primary), any agent (discoveries).
> **Read by:** Every agent at boot (Step 7 of boot sequence).
> **Size limit:** Keep under 200 lines.

---

## Architectural Decisions (Never Re-Decide These)

<!-- Format: YYYY-MM-DD: [decision] — [reason] -->
- 2026-02-27: mz-ai-assistant server uses `app.tasks.celery_app` module path — plan takes precedence over INFRASTRUCTURE.md which said `scheduler.celery_app`
- 2026-02-27: migrate.py uses psycopg2 sync (not asyncpg) — simpler for one-time scripts; asyncpg reserved for FastAPI runtime
- 2026-02-27: nginx.conf placed in `server/config/` directory — setup.sh copies to /etc/nginx/
- 2026-02-27: mz-ai-assistant uses PostgreSQL 15 + asyncpg (not DynamoDB) — standalone EC2 deployment, not Lambda
- 2026-02-27: mz-ai-assistant Starlette middleware order — ChatGatewayMiddleware registered FIRST (innermost), CORSMiddleware registered SECOND (outermost). Last-added = outermost in Starlette.
- 2026-02-27: mz-ai-assistant rate limiting — Redis sliding window with unique ZADD keys: `f"{now_ms}:{uuid4().hex[:8]}"` prevents collision under concurrent load

---

## Patterns Established (Don't Re-Invent)

- **Auth flow:** OAuth2 + JWT → see `svc-iam/` for reference implementation
- **Coupon state machine:** See `coupon-domain-expert.md` for lifecycle
- **Error handling:** Backend returns RFC 7807 Problem Details format
- **i18n keys:** Namespaced by feature (e.g., `tickets.list.title`)
- **API pagination:** Cursor-based (not offset) — aligns Frontend + Backend + Mobile

---

## Known Issues & Workarounds

- **Vite HMR:** Needs WebSocket proxy through gateway — see gateway/config.py
- **Lambda cold start:** Must stay < 1s — use provisioned concurrency for P0 services
- **Mangum adapter:** Required for all Lambda-deployed FastAPI services
- **shadcn DatePicker:** Timezone bug — use custom wrapper in `shared/components/`

---

## Agent Notes

- Lead Session 1: mz-ai-assistant server build plan created — 10 phases, 23–26 sessions total. Phase 0 ready for Infra Agent.
- mz-ai-assistant: APP/ is React Native UI prototype (all mocks). Server must be built from scratch. Plan at `.claude/coordination/plans/mz-ai-assistant-server-v1.0.md`
- mz-ai-assistant LLM strategy: Chinese text → Kimi (Moonshot moonshot-v1-128k); English → Claude (claude-sonnet-4-6); auto-failover between both
- mz-ai-assistant DB: 9 PostgreSQL tables — users, conversations, sales_leads, artifacts, audit_log, llm_usage, email_log, scheduled_jobs, webhook_events

---

## Context Management Log

<!-- Format: YYYY-MM-DD: [Agent] [module] — estimated [N] sessions, actual [M] -->
- 2026-02-27: Infra mz-ai-assistant Phase 0 — estimated 2 sessions, actual 1 (very efficient)
- 2026-02-27: Backend mz-ai-assistant Phase 1 — estimated 2 sessions, actual 1 (both 1-A and 1-B in one session)
- 2026-02-27: Backend mz-ai-assistant Phase 2 — estimated 2 sessions, actual 2 (Session 1: all 9 files; Session 2: 2 review fixes)
- 2026-02-27: Backend mz-ai-assistant Phase 3 — estimated 2 sessions, actual 2 (Session 1: 9 existing + 2 new mezzofy files; Session 2: 4 review fixes)
- 2026-02-27: Backend mz-ai-assistant Phase 4 — estimated 3 sessions, actual 3 (4A: LLM clients; 4B: 7 skills; 4C: 6 agents + review fixes)
- 2026-02-27: Backend mz-ai-assistant Phase 5 — estimated 3 sessions, actual 1 (all 20 files in session 5A; no session 5B/5C needed)
- 2026-02-28: Backend mz-ai-assistant Phase 6 — estimated 2 sessions, actual 1 (all 6 files in session 6A)
- 2026-02-28: Docs mz-ai-assistant Phase 10 — estimated 1 session, actual 1 (4 doc files: API.md, DEPLOYMENT.md, openapi.yaml, RN v1.0)
- 2026-02-28: Tester mz-ai-assistant Phase 7 — estimated 2 sessions, actual 2 (7A: 9 test files; 7B: run + fix + 3 new files + coverage)
- 2026-02-28: Tester mz-ai-assistant Phase 9 — estimated 1 session, actual 1 (11 E2E tests, 247 total passing)

---

## Completed Patterns (Reference for New Modules)

<!-- Link to completed modules that serve as good examples -->
<!-- Format: [Pattern]: See [module]/[path] for reference -->
- **Tool pattern (BaseTool):** See `server/app/tools/base_tool.py` + `outlook_ops.py` for reference implementation
- **Async tool rule:** ALL Firebase/sync SDK calls in async handlers must use `run_in_executor(None, fn, *args)` — never call sync blocking I/O from async def
- **MS Graph Teams DM:** Requires `teams.sender_user_id` (Azure AD user object ID) in config — cannot use app `client_id` as a user reference
- **email_log writes deferred to Phase 5:** Tool handlers lack DB session context — email audit writes will be wired in Phase 5 (API layer provides get_db())
- **PostgreSQL INTERVAL parameterization:** Cannot use `INTERVAL :param` — PostgreSQL INTERVAL requires a literal. Use `MAKE_INTERVAL(days := :param)` with an integer parameter instead
- **anthropic async in tool handlers:** Always use `anthropic.AsyncAnthropic()` (not `Anthropic()`) when calling Claude API from async handlers — the sync client blocks the event loop
- **mezzofy KB tools:** data_ops.py + knowledge_ops.py resolve KB path from `server_root / config["tools"]["knowledge_base"]["directory"]`; `get_brand_guidelines` returns hardcoded orange/black/white defaults when KB file absent
- **Tool Ops import paths (CRITICAL):** `app.tools.communication.*` (not `comm`); `app.tools.document.*` (not `doc`); class names `PDFOps`, `PPTXOps` (uppercase acronym — NOT `PdfOps`, `PptxOps`)
- **Lazy inline tool imports:** All Ops class imports go INSIDE method bodies (not at module top) — avoids circular imports and speeds startup. Pattern: `from app.tools.document.pdf_ops import PDFOps` inside the function.
- **Agent permission bypass:** `_require_permission()` in BaseAgent skips checks when `task["source"]` is `"scheduler"` or `"webhook"` — system-initiated tasks don't need human approval
- **Email rate limiting:** EmailOutreachSkill enforces 30 emails/hour via `_check_rate_limit()` — MS Graph throttles at ~50/hr; buffer is intentional
- **Skill/LLM singletons:** Both `skill_registry` and `llm_manager` use module-level `init(config)` / `get()` singleton pattern — initialized once in `main.py` lifespan startup
- **Config singleton:** `app.core.config` — `load_config()` reads config.yaml + resolves ${ENV_VAR} at startup; `get_config()` returns cached dict. Injected as `task["_config"]` by chat endpoints.
- **REST chat auth:** ChatGatewayMiddleware decodes JWT → `request.state.user`. Chat endpoints use `_get_user_from_state(request)` (NOT `Depends(get_current_user)`) to avoid double decode.
- **WebSocket auth:** Gateway middleware bypasses `/chat/ws`. JWT passed as `?token=<JWT>` query param, validated directly inside the WS handler via `decode_access_token(token)`.
- **_db_session pattern:** Custom async context manager class in chat.py — used instead of `Depends(get_db)` when endpoint body also calls async context managers (session_manager, processor). Handles commit/rollback/close.
- **SSRF protection (url_handler):** Blocks localhost/loopback, AWS metadata (169.254.169.254), RFC 1918 ranges (10.x, 192.168.x, 172.16-31.x). Uses `urlparse().hostname` for normalization. DNS rebinding is a known v1.0 limitation.
- **WSConnectionManager:** In-process singleton. Multi-worker deployments need Redis pub/sub for cross-worker WS push — deferred to Phase 6 Celery integration.
- **Artifact ownership:** All DB artifact queries include `user_id` filter — users can only access their own files via `/files/{id}`.
- **Admin dynamic UPDATE:** `update_user` builds SET clause from hardcoded Pydantic model attribute names (never user-supplied). Values always parameterized — not SQL injection vulnerable.
- **File path traversal protection:** `Path(media_file.filename).name` strips directory components before saving uploads.
- **email_log wiring:** Phase 5 processor.py handles artifact DB writes; email audit log writes remain deferred — wire in Phase 7 tests or leave for Phase 6 task handlers.
- **Celery async pattern:** Celery workers don't have an event loop. All async agent code wrapped in `asyncio.run()` at sync task boundary. One `asyncio.run()` per task covers both agent execution and delivery.
- **DatabaseScheduler:** Custom `PersistentScheduler` subclass in `beat_schedule.py` — merges static 5 jobs + DB user jobs at Beat startup. No `redbeat` dependency needed. New user jobs activate on next Beat restart; use `POST /scheduler/jobs/{id}/run` for immediate execution.
- **Webhook 200-first:** All webhook endpoints return 200 *before* Celery processing completes. Pattern: record in DB → `.delay()` → return 200. Celery task updates DB record to processing/completed/failed.
- **Task names explicit:** All Celery tasks use explicit `name=` parameter (e.g., `"app.tasks.tasks.process_agent_task"`) matching the module path — ensures reliable `--include` discovery.
- **Scheduler constraints:** Max 10 active jobs per user (checked at create time); min 15-min interval (validated from cron minute field); owner-only for PUT/DELETE; admins can bypass ownership check.
- **Teams bot auth v1:** `TEAMS_BOT_SECRET` bearer token for Phase 6. Production TODO: full MS Bot Framework JWT validation with Azure AD RSA key.
- **BUG-001 (CRITICAL):** `app/core/auth.py: _build_payload()` reads `user["id"]` but decoded JWT payload from `decode_refresh_token` has `user_id`/`sub`. Fix: `user.get("id") or user.get("user_id")`. Token refresh crashes until fixed.
- **FastAPI test override type annotations:** Dependency override functions MUST have `request: Request` type annotation — untyped params are treated as required query params → 422 errors in tests.
- **Patch at import site, not source module:** When `module_a.py` does `from module_b import fn`, patching `module_b.fn` doesn't affect `module_a`'s local binding. Always patch `module_a.fn`.
- **AsyncSessionLocal direct calls:** Endpoints calling `AsyncSessionLocal()` directly (not `Depends(get_db)`) bypass FastAPI `dependency_overrides` — must `patch("module.AsyncSessionLocal", ...)` separately in tests.
- **E2E test mock depth:** When mocking multi-step flows, mock at the layer where the return type contract is satisfied. `process_input(task)` returns an enriched dict — mocking `handle_url` (which it calls) with a string return value causes `TypeError` upstream. Mock `app.api.chat.process_input` directly with a properly-typed return value.
- **mz-ai-assistant Phase 9 complete:** 247 tests passing (11 new E2E). All 8 mobile API contracts verified. Phase 10 Docs authorized.
- **mz-ai-assistant v1.0 COMPLETE:** All 10 phases passed quality gates. 18 sessions total (estimated 23–26). Deploy from `server/docs/DEPLOYMENT.md`.
- **mz-ai-assistant Android Build (2026-03-01):** `assembleDebug` succeeds — 277 tasks, 1m 4s. APK: 149 MB at `APP/android/app/build/outputs/apk/debug/app-debug.apk`. All 3 native packages autolinked cleanly: react-native-image-picker@7, react-native-document-picker@9, @react-native-voice/voice@3. No manual voice package fix required (Jetifier handled AndroidX migration as predicted). Only warnings: deprecated API notes (non-fatal) and `package=` attribute in AndroidManifest of the 3 packages (non-fatal).
- **mz-ai-assistant Phase 9+ items resolved (2026-03-01):** All prototype items now confirmed complete: (1) CameraScreen uses `launchCamera` from image-picker + `mzWs.sendCameraFrame(base64)`. (2) ChatScreen uses `react-native-document-picker` for file/audio uploads and `@react-native-voice/voice` for local STT → REST. (3) xfail markers confirmed absent from all test files. WS audio streaming (sendSpeechAudio PCM chunks) deferred to v2.0 — requires `react-native-audio-recorder-player` (not in package.json). v1.0 speech uses local Voice STT → REST path.
- **BUG-002 (2026-03-01):** ManagementAgent `can_handle()` blanket-matched any management user — Fix: require `is_management_user AND has_keyword` — department alone is insufficient.
- **Intent-check pattern:** In `execute()`, always check message intent before running heavyweight workflows. Non-KPI messages → `_general_response()`; KPI keywords → `_kpi_dashboard_workflow()`.
- **Date injection:** All LLM prompts that include report dates must inject `date.today().strftime(...)`. Never rely on LLM to generate dates — it produces `{Current Date}` placeholders.
