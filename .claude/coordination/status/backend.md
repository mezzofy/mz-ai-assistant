# Context Checkpoint: Backend Agent
**Date:** 2026-03-19
**Project:** mz-ai-assistant
**Session:** 23 (BUG-fix: get_crm_leads LEFT JOIN UUID type mismatch)

## Completed This Session (Session 23)
- ✅ BUG fix: `server/app/api/admin_portal.py` line 1489
  - Changed `LEFT JOIN users u ON u.id::text = sl.assigned_to` → `LEFT JOIN users u ON u.id = sl.assigned_to`
  - Root cause: unnecessary `::text` cast caused PostgreSQL "operator does not exist: text = uuid" error
  - Both `users.id` and `sales_leads.assigned_to` are UUID — direct UUID = UUID comparison is correct

## Previous Session (22): portal-v1.40.0 — Task 1: files download endpoint
- Task 1 DONE: Added `GET /files/{file_id}/download` endpoint to admin portal router
  - File: `server/app/api/admin_portal.py` (lines 899–956)
  - Inserted after `folder-tree` endpoint, before `# ── Users ──` section
  - Lazy inline imports throughout (sql_text, FileResponse, FsPath, os, HTTPException, get_artifacts_dir)
  - Path traversal guard using `get_artifacts_dir().resolve()`
  - Inline MIME map (13 types + octet-stream fallback)
  - Uses `AdminUser` dependency — consistent with all other admin portal endpoints

## Backend Work for v1.40.0: COMPLETE
- No further backend tasks. Frontend Agent handles Tasks 2–6. Deploy is Task 7.

## Resume Instructions
After /clear, load in order:
1. CLAUDE.md
2. .claude/agents/backend.md
3. .claude/coordination/status/backend.md
4. .claude/coordination/plans/portal-v1.40.0-plan.md
Backend Task 1 is DONE. No further backend action needed for v1.40.0.

---

# Previous Checkpoint: Session 21 (BUG-notification-history — stale comment removed)
**Date:** 2026-03-17
**Project:** mz-ai-assistant
**Session:** 21 (BUG-notification-history — stale comment removed)

## Completed This Session (Session 21)
- ✅ `server/app/tools/communication/push_ops.py` — removed stale comment (lines 263–264 ref to pre-Session-19 behavior)
- ✅ EC2 action required: run `python scripts/migrate.py` to create `notification_log` table (see plan)

---

# Previous Checkpoint: Session 20 (BUG-C/D/E — tool kwarg filter)
**Date:** 2026-03-17

## Completed This Session (Session 20)
- ✅ `server/app/tools/base_tool.py` — global kwarg filter via inspect.signature in execute()
- ✅ `server/app/tools/document/pdf_ops.py` — content= alias for html_content= (BUG-D)
- ✅ `server/app/tools/communication/teams_ops.py` — channel= alias for channel_name= (BUG-E)
- ✅ `server/tests/test_tool_kwarg_fixes.py` — 10 new tests; 420 total passing
- ✅ Commit: `e583d7d`
- ✅ EC2 deployed: git pull + restarted mezzofy-api.service + mezzofy-celery.service

---

# Previous Checkpoint: Session 19 (v1.31.0 — Webhook push logging fix)
**Date:** 2026-03-16

## Completed This Session (Session 19)

- ✅ `server/app/tasks/webhook_tasks.py` — Fixed `_deliver_results_async()` push block: replaced broken `PushOps.execute()` call (wrong args, no logging) with `get_user_push_targets()` + `send_push()` pattern. Adds `push_title` from `deliver_to` payload (backwards-compatible). Commit: `320d979`.

## Notes
- No DB schema changes — no migrate.py run needed
- No service restart needed for this fix to take effect after `git pull`
- No types changed — no handoff required

---

# Previous Checkpoint (Session 18)
**Context:** ~40% at checkpoint
**Reason:** Feature complete, Lead review PASS (after P1 fix)

---

## Completed This Session (Session 18)

- ✅ `server/app/llm/anthropic_client.py` — `_format_tools()` pass-through guard for native Anthropic built-in tools (e.g. `web_search_20250305`)
- ✅ `server/app/llm/kimi_client.py` — `_format_tools()` pass-through guard for pre-formatted OpenAI function tools (e.g. `$web_search`)
- ✅ `server/app/agents/research_agent.py` (NEW) — Agentic web-search loop, Claude + Kimi paths, max 8 iterations, step broadcasting
- ✅ `server/app/agents/developer_agent.py` (NEW) — Claude Code headless subprocess, stream-JSON parsing, 5 event types, configurable timeout
- ✅ `server/app/agents/agent_registry.py` — Added `"research": ResearchAgent`, `"developer": DeveloperAgent` to AGENT_MAP
- ✅ `server/app/api/chat.py` — Added `_detect_agent_type()`, `_RESEARCH_KEYWORDS`, `_DEVELOPER_KEYWORDS`, dynamic `queue_name` in DB INSERT, `task_payload["agent"]` routing
- ✅ `server/config/config.example.yaml` — Added `max_research_iterations`, `developer_work_dir`, `max_developer_timeout`
- ✅ P1 bug fix: `await process.wait()` added after `process.kill()` in timeout handler (developer_agent.py)

## Lead Review: PASS (after P1 fix)

- P1 fixed: zombie process leak in DeveloperAgent timeout path
- P2 confirm: `asyncio.timeout()` requires Python 3.11+ — human to confirm EC2 version
- P3 deferred: static progress=50 + success flag on nonzero exit → v1.24.0 backlog

## Notes
- No DB schema changes — no migrate.py run needed on EC2
- EC2 deploy requires: `npm install -g @anthropic-ai/claude-code` (if not present)
- EC2 .env: add `AGENT_WORK_DIR=/home/ubuntu/mezzofy-workspace`
- Restart both `mezzofy-api.service` AND `mezzofy-worker.service`
- Also in this commit: BUG-015 fixes in `session_manager.py` + `artifact_manager.py` (UUID str casting)

## Files Modified (commit together)
- `server/app/agents/research_agent.py` (new)
- `server/app/agents/developer_agent.py` (new)
- `server/app/llm/anthropic_client.py` (modified)
- `server/app/llm/kimi_client.py` (modified)
- `server/app/agents/agent_registry.py` (modified)
- `server/app/api/chat.py` (modified)
- `server/config/config.example.yaml` (modified)
- `server/app/context/session_manager.py` (BUG-015, pre-existing)
- `server/app/context/artifact_manager.py` (BUG-015, pre-existing)
