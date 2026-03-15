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
- **Sales Lead Automation DEPLOYED (2026-03-13, commit 7937e4c):** 4 Celery tasks (email/ticket ingest, research, CRM digest), REST API `/sales/leads`, CRMOps, Beat jobs (12 total). EC2: config.yaml `sales:` block added, `-Q sales` added to worker, migrate.py run. Azure AD Mail.Read/Mail.Read.Shared granted. Pending: BUG-014 Anthropic key before chat is live.
- **mz-ai-assistant mobile v1.14.7 (2026-03-08) ✅ COMPLETE:** BUG-007: task progress % + step description in banner; race condition guard in pollActiveTask (session guard before set()); empty-bubble fallback `|| 'Task completed.'`; banner session-scoped (`activeTask.session_id === sessionId`). APK 61 MB, versionCode 25. Review: PASS. Commit: 2297ec0.
- **mz-ai-assistant mobile v1.14.0 (2026-03-07) ✅ COMPLETE:** Task lifecycle fix (queued→running→completed banner), WS task_complete notification, history badge filtered to background tasks only. APK 61 MB (release). versionCode 18. EC2 deployed manually. Commits: b320cf6 (code) + 1314ad2 (version bump).
- **mz-ai-assistant mobile v1.13.0 (2026-03-07) ✅ COMPLETE:** History header refresh button (top-right, disabled on double-tap, matches FilesScreen pattern) + Settings Storage & Data shows disk size (`X.X MB`) via new `GET /files/storage-stats` backend endpoint. Review: PASS. versionCode 17.
- **mz-ai-assistant mobile v1.12.0 (2026-03-07) ✅ COMPLETE:** History tab: pull-to-refresh (RefreshControl, orange spinner, parallel loadSessions+loadTasks) + task badge "Task ID: " prefix. APK 61 MB. Review: PASS. Minor: empty-state has no pull-to-refresh (non-blocker, v1.13.0 candidate).
- **mz-ai-assistant mobile v1.2.0 (2026-03-05):** APK built (145 MB, BUILD SUCCESSFUL). Contains: artifact DB registration fix (server), friendlier chat error messages (`normalizeApiError`), AI Usage Stats screen (Settings → tap → model status + system health). APK: `APP/android/app/build/outputs/apk/debug/app-debug.apk`.
- **mz-ai-assistant mobile v1.3.0 (2026-03-05) ✅ COMPLETE:** Files tab (pull-to-refresh, download with progress, in-app viewer: image/video/markdown/text) + AI Usage Stats real data. Build fix: compileSdkVersion 34→35 (media3:1.8.0). New: GET /llm/usage-stats (`server/app/api/llm.py`). Review: PASS both agents. Deploy: restart mezzofy-api.service on EC2 to activate new endpoint.
- **Per-user artifact routing (2026-03-04):** `contextvars.ContextVar` pattern — `app.core.user_context` module holds `_user_dept`/`_user_email`. Set in `router.py._execute_with_instance()` before agent dispatch. Read by `_resolve_output_dir()` in all 4 doc tools (PDF/PPTX/DOCX/CSV). Fallback to flat dir when email is empty (scheduler/webhook). Upload routing uses `get_user_artifacts_dir()` directly from `files.py` (no ContextVar needed — user is available in request scope).
- **mz-ai-assistant Android Build (2026-03-01):** `assembleDebug` succeeds — 277 tasks, 1m 4s. APK: 149 MB at `APP/android/app/build/outputs/apk/debug/app-debug.apk`. All 3 native packages autolinked cleanly: react-native-image-picker@7, react-native-document-picker@9, @react-native-voice/voice@3. No manual voice package fix required (Jetifier handled AndroidX migration as predicted). Only warnings: deprecated API notes (non-fatal) and `package=` attribute in AndroidManifest of the 3 packages (non-fatal).
- **mz-ai-assistant Phase 9+ items resolved (2026-03-01):** All prototype items now confirmed complete: (1) CameraScreen uses `launchCamera` from image-picker + `mzWs.sendCameraFrame(base64)`. (2) ChatScreen uses `react-native-document-picker` for file/audio uploads and `@react-native-voice/voice` for local STT → REST. (3) xfail markers confirmed absent from all test files. WS audio streaming (sendSpeechAudio PCM chunks) deferred to v2.0 — requires `react-native-audio-recorder-player` (not in package.json). v1.0 speech uses local Voice STT → REST path.
- **BUG-002 (2026-03-01 — superseded 2026-03-04):** ManagementAgent `can_handle()` originally required `AND has_keyword`. Superseded by routing redesign — `can_handle()` is now dept-only; intent check lives in `execute()`.
- **Routing redesign (2026-03-04, commit c3799b6):** All agents: `can_handle()` = dept-only (no keywords). Keywords live in `execute()` to guard expensive workflows. `BaseAgent._general_response()` shared fallback using `execute_with_tools`. Cross-dept routing in `agent_registry.get_agent_for_task()` requires `cross_department_access` permission or admin/executive/management role.
- **`create_txt` tool (2026-03-04, commit ed5a23f):** `server/app/tools/document/text_ops.py` — `TextOps` with `create_txt` + `read_txt`. Registered in `tool_executor.py`. Added to storage rule in `_SYSTEM_PROMPT_TEMPLATE`. Follows same `_resolve_output_dir(storage_scope)` pattern as `csv_ops.py`.
- **Intent-check pattern:** In `execute()`, always check message intent before running heavyweight workflows. Non-domain messages → `_general_response()`; domain keywords → specialist workflow.
- **Date injection:** All LLM prompts that include report dates must inject `date.today().strftime(...)`. Never rely on LLM to generate dates — it produces `{Current Date}` placeholders.
- **BUG-003 (FIXED 2026-03-05):** `session_manager.py` stores messages with `{"role", "content", "timestamp"}`. The Anthropic API rejects `timestamp` with 400 `"Extra inputs are not permitted"`. Fix: `AnthropicClient._sanitize_messages()` strips all non-`role`/`content` fields before every API call. Never add extra fields to messages passed to `_client.messages.create()`.
- **HRAgent COMPLETE 2026-03-07 (commits b320cf6 + 7cc5187):** 6th dept agent fully activated. `hr_viewer`/`hr_manager` roles in roles.yaml + VALID_ROLES/VALID_DEPARTMENTS in rbac.py. Beat jobs: `weekly-hr-summary` (Fri 09:00 UTC) + `monthly-headcount` (1st 01:00 UTC) in beat_schedule.py. Config: `teams.channels.hr`, `notifications.hr_manager_email`, `hr` in agents.available. Webhooks: `employee_onboarded`, `employee_offboarded`. Deploy requires `HR_MANAGER_EMAIL` in `.env`.
- **BUG-008 (FIXED 2026-03-09) — Celery tasks stuck in `running` forever:** `_run_chat_task()` used `async with AsyncSessionLocal() as db:` (autocommit=False) but had NO `await db.commit()`. All DB writes (conversation history, artifacts, `UPDATE agent_tasks SET status='completed'`) were silently rolled back when the session closed. Fix: added `await db.commit()` after `process_result()` inside the `async with` block. Commit: `2d199fa`.
- **BUG-009 (FIXED 2026-03-09) — agent_tasks.result always NULL:** `process_result()` UPDATE only set `status/progress/completed_at` — not the `result` JSONB column. `GET /tasks/{id}` always returned `"result": null`. Fix: UPDATE now includes `result = CAST(:result AS jsonb), current_step = NULL` with artifact payload. Commit: `8400fba`.
- **Celery asyncio event loop (CRITICAL pattern):** `asyncio.run()` creates and destroys an event loop each call. SQLAlchemy async pool connections bound to loop #1 cannot be reused in loop #2 → "Future attached to a different loop". Fix: call `engine.sync_engine.dispose()` before EVERY `asyncio.run()` call that isn't the main task. Applied in `on_worker_ready`, SoftTimeLimitExceeded path, MaxRetriesExceededError path. `worker_process_init` already disposes at fork.
- **AnthropicClient 429 retry delays (CRITICAL):** Default `[1, 2, 4]` second delays are useless for Anthropic free tier (10K input tokens/min). After 3 failed attempts the LLM falls to Kimi. Fix: 429 rate-limit errors now use `[30, 60, 60]` second delays; 500/529 server errors keep `[1, 2, 4]`. File: `server/app/llm/anthropic_client.py`. Commit: `8400fba`.
- **LLM system prompt file-save (UX bug):** `_SYSTEM_PROMPT_TEMPLATE` said "MUST ask where to save — Do not skip this question" unconditionally. Background Celery tasks can't receive an interactive reply → LLM asks the question, loop ends, no file created. Fix: now conditional — "If user has NOT specified location, ask; if already specified (e.g., 'personal folder'), use directly." File: `server/app/llm/llm_manager.py`. Commit: `8400fba`.
- **Integration test PASSED 2026-03-09:** `test_research_top3_competitors_completes_with_text_file` — 1 passed in 255.81s (4m 15s) on EC2. Test dispatches research task, polls to `completed`, validates ≥1 `.txt` artifact, downloads and verifies non-empty. TIMEOUT_S=600 (was 180).
- **MS OAuth delegated integration COMPLETE 2026-03-11 (review: PASS):** 10 files — `ms_oauth_tokens` table, Fernet-encrypted token storage, 4 OAuth endpoints (`/ms/auth/*`), 18 personal Graph tools in `personal_ms_ops.py`. KNOWN V1.0 LIMITATION: concurrent refresh race — if two requests for same expired user token arrive simultaneously, second refresh fails (`invalid_grant`). Fix in v1.1: Redis distributed lock around refresh. Deployment prereqs: run `migrate.py`, generate `MS_TOKEN_FERNET_KEY`, update Azure AD app registration (add delegated perms + `msalauth://callback` redirect).
- **BUG-011 (FIXED 2026-03-11):** `ms_oauth.py _get_msal_app()` used `ConfidentialClientApplication` with `client_secret`. Azure AD rejects this for `msalauth://` redirect URIs (public client → AADSTS700025). Fix: switched to `PublicClientApplication` (no `client_secret`), guard now checks `client_id` only. Commit: `5d16da1`.
- **MSAL public client pattern:** For delegated OAuth with custom URI scheme redirects (`msalauth://`), always use `PublicClientApplication`. `ConfidentialClientApplication` is only for server-to-server flows with `https://` redirects.
- **BUG-010 (FIXED 2026-03-11):** `MS365_DELEGATED_SCOPES` in `config.py` included `"offline_access"` — MSAL's `get_authorization_request_url()` rejects it as a user-provided scope (it's an OIDC reserved scope MSAL manages internally). Caused `ValueError` → HTTP 500 → mobile "Error" popup on Connect. Fix: removed `"offline_access"` from the list. Commit: `7b1cb3f`.
- **MSAL blocking pattern (WARNING):** `msal.PublicClientApplication` methods are synchronous. Called from `async def` handlers in `ms_oauth.py` — blocks event loop per call. Acceptable for low-traffic EC2; fix in v1.1 with `run_in_executor`.
- **mz-ai-assistant mobile v1.17.0 (2026-03-11) ✅ COMPLETE:** Connected Accounts screen (Settings → MS OAuth connect/disconnect). 8 files: msOAuth.ts API layer, msStore.ts Zustand store, ConnectedAccountsScreen.tsx, SettingsScreen row, App.tsx nav, AndroidManifest deep link, version bumps. KNOWN W1: oauthLoading spinner has no cancel path if user abandons OAuth in browser — fix in v1.18.0 with AppState listener. APK build pending. Review: PASS. Commit: 7f3f430.
- **mz-ai-assistant mobile v1.17.1 (2026-03-11) ✅ COMPLETE:** Patch — 503 UX fix. ConnectedAccountsScreen shows friendly message "Microsoft account integration is not available on this server" instead of raw server error when GET /ms/auth/url returns 503. Server fix: EC2 .env updated with MS365_CLIENT_ID + MS365_CLIENT_SECRET. versionCode 29. Commits: b54c487 (ConnectedAccountsScreen ApiError fix) + fa0b851 (version bump).
- **mz-ai-assistant mobile v1.18.0 (2026-03-12) ✅ COMPLETE (Lead review: PASS):** MS Contacts feature (FEAT-013/BUG-013) fully shipped. Backend: 4 Contact tools + `personal_check_token_scopes` diagnostic + write logging (commit 36bf87f). Mobile: Contacts pill + info text + versionCode 30 (commit ae49c9f + 6f2bc2c). APK: BUILD SUCCESSFUL. Pending: GitHub push + EC2 deploy + Azure AD write permission registration + user MS reconnect.
- **BUG-014 (2026-03-12) — Anthropic API key monthly spending limit exhausted:** EC2 key `sk-ant-api03-KIC5...` hit its usage cap. Error: `"You have reached your specified API usage limits. You will regain access on 2026-04-01 at 00:00 UTC."` This started 2026-03-11 and is NOT a v1.18.0 code issue — coincidental timing. Fix: replace `ANTHROPIC_API_KEY` in `server/config/.env` on EC2 with a new key, then `sudo systemctl restart mezzofy-api.service`. .env path on EC2: `/home/ubuntu/mz-ai-assistant/server/config/.env`.
- **BUG-015 (FIXED 2026-03-14) — UUID type mismatch in session_manager + artifact_manager:** `_fetch_session()` returned raw `row.id` (UUID object); `list_user_sessions()` returned raw `row.id` as `session_id`; `artifact_manager.py` passed raw `session_id` to INSERT. asyncpg expects `str`. Fix: `str(row.id)` in both session_manager returns; `str(session_id) if session_id is not None else None` in artifact_manager. Root: new sessions used `str(uuid4())` but fetched sessions returned UUID objects.
- **mz-ai-assistant mobile v1.20.0 (2026-03-13) ✅ COMPLETE (Lead review: PASS):** AI Model Check button. `POST /admin/model-check` (admin-only, 15s timeout, latency_ms). Mobile: ⚡ pulse icon per model row → spinner → inline result (green ✓ / red ✗). Refresh clears results. 5 tests. APK 61 MB, versionCode 32. Commit: 12f917c. KNOWN W1: null result (network failure) gives no UI feedback — deferred to v1.21.0.
- **RAG semantic search (2026-03-14) ✅ COMPLETE:** pgvector + sentence-transformers (all-MiniLM-L6-v2, 384-dim) deployed to EC2. `knowledge_vectors` table + IVFFlat cosine index. `semantic_search` tool added to KnowledgeOps — lazy-loads model, threshold filtering, category filter. `scripts/index_knowledge.py` for KB indexing. Pin: `sentence-transformers==3.3.1` + `transformers==4.47.1` (torch 2.3.1 compat). 14 tests passing (424 total). Deploy: `sudo -u postgres psql -d mezzofy_ai -c "CREATE EXTENSION vector;"` → `python scripts/migrate.py` → `python scripts/index_knowledge.py`.
- **Multi-Agent Orchestration v1.23.0 (2026-03-14) ✅ COMPLETE (Lead review: PASS):** ResearchAgent (web_search_20250305 agentic loop, max 8 iter) + DeveloperAgent (Claude Code headless subprocess, stream-JSON). Wired into existing `/chat/send` → Celery path via `_detect_agent_type()` in chat.py. No new REST endpoints, no new Celery tasks. `_format_tools()` in both LLM clients updated with pass-through guards for native/pre-formatted tools. EC2 prereq: `npm install -g @anthropic-ai/claude-code` + `asyncio.timeout()` requires Python 3.11+.
- **ResearchAgent pattern:** `can_handle()` checks `task.get("agent") == "research"` (NOT department). Only triggered from Celery path where chat.py sets `task_payload["agent"] = "research"`. Safe in cross-dept fallback — returns False when `agent` key absent. Same pattern for DeveloperAgent.
- **Native LLM tool pass-through:** Anthropic built-in tools (`web_search_20250305`) have `{"type": "web_search_20250305", "name": "web_search"}` — no `description`/`parameters`. Guard in `_format_tools()`: `if "type" in t and t.get("type") != "function"`. Kimi pre-formatted tools guard: `if "function" in t and isinstance(t.get("function"), dict)`.
- **SchedulerAgent v1.25.0 (2026-03-15) ✅ COMPLETE (Lead review: PASS):** Chat-based scheduled job management. 6 files: `app/tools/scheduler/scheduler_ops.py` (4 tools: create/list/delete/run_now), `app/agents/scheduler_agent.py`, chat.py keyword detection, agent_registry + router + tool_executor wiring. Key pattern: scheduler detection runs BEFORE `_is_long_running()` in chat.py — phrases like "schedule a weekly report" match long-running keywords and would have been routed to Celery incorrectly. KNOWN GAP: cron 15-min minimum not enforced in chat path (deferred to v1.26.0). Commits: initial impl + `6d9f634` (3 bug fixes).
- **`task["system_prompt"]` override pattern:** `LLMManager._build_system_prompt()` now early-returns `task["system_prompt"]` when set. Allows specialist agents to inject a fully custom prompt and restrict the LLM to a subset of tools via system instructions. Any agent can use this pattern — set `task["system_prompt"]` before calling `llm_mod.get().execute_with_tools(task)`.
- **SchedulerAgent routing:** `can_handle()` checks `task.get("agent") == "scheduler"`. Set by `_is_scheduler_request()` in chat.py sync path. `_route_mobile()` in router.py short-circuits to `_execute_by_name(explicit_agent, ...)` before dept routing when `task["agent"]` is in AGENT_MAP — covers scheduler, research, developer all consistently.
- **BUG-017 (FIXED 2026-03-15) — next_run always NULL:** Celery Beat's `PersistentScheduler` never writes `next_run` back to PostgreSQL. Fix: `compute_next_run(cron_expr)` helper (croniter-based, tz-aware) called at create time and after `run_job_now` in both REST (`scheduler.py`) and chat (`scheduler_ops.py`) paths. `croniter>=1.3.8` added to requirements.txt. Commits: `3f9a44e` (backend) + `051aef4` (mobile card enhancements). v1.26.0 Lead review: PASS.
- **compute_next_run pattern:** `compute_next_run(cron_expr: str) -> datetime` in `app/webhooks/scheduler.py`. Returns tz-aware UTC datetime. Import lazily inside method bodies to keep consistent with project's lazy-import rule. Both REST and chat code paths must call it — they operate independently.
- **BUG-019 (FIXED 2026-03-15) — Artifact routing goes to `general/shared` instead of correct dept:** ContextVars (`_user_dept`, `_user_email`) set by `router.py` via `set_user_context()` are NOT propagated to Celery worker processes — they reset to defaults (`"general"`, `""`). Fix: `_fetch_user_context(user_id)` helper (DB lookup of email+role) + `set_user_context()` call added to both `_run_agent_task()` and `_run_chat_task()` in `tasks.py`. Pattern: any async Celery entry point that dispatches to document-writing tools MUST call `set_user_context()` before agent execution. v1.27.0.
