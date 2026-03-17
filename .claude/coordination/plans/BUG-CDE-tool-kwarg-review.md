# Quality Gate Review: BUG-C/D/E — Tool Kwarg Fixes
**Date:** 2026-03-17
**Reviewer:** Lead Agent
**Commit:** e583d7d

## Checklist

### Documents
- [x] Plan exists at `BUG-CDE-tool-kwarg-plan.md`
- [x] Backend status updated in `.claude/coordination/status/backend.md`

### Code Review

#### `base_tool.py` — Global kwarg filter
- [x] `import inspect` added
- [x] `inspect.signature(handler)` used to determine accepted params
- [x] `has_var_keyword` guard: handlers with `**kwargs` skip filtering (correct — preserves existing behavior for all legacy handlers)
- [x] Unknown kwargs logged at WARNING level with tool name and dropped set
- [x] Filter applied before `await handler(**kwargs)`
- [x] No change to error handling path

#### `pdf_ops.py` — BUG-D: `content` alias
- [x] `_create_pdf` signature adds `content: Optional[str] = None`
- [x] `html_content = html_content or content or ""` — correct precedence (explicit `html_content` wins)
- [x] Tool schema adds `"content"` property with clear description "Alias for html_content"
- [x] `required` changed from `["title", "html_content"]` to `["title"]` — correct, since either content= or html_content= satisfies the requirement

#### `teams_ops.py` — BUG-E: `channel` alias
- [x] `_post_message` signature adds `channel: Optional[str] = None`
- [x] `channel_name = channel_name or channel` — correct resolution
- [x] Guard added: `if not channel_name: return self._err(...)` — prevents silent failure when neither is provided
- [x] Tool schema adds `"channel"` property with enum matching `channel_name`'s enum
- [x] `required` changed from `["channel_name", "content"]` to `["content"]` — correct, channel resolved from either alias

#### `test_tool_kwarg_fixes.py` — 10 tests
- [x] BUG-C: `test_drops_unknown_kwarg_no_type_error` — verifies start_date dropped without TypeError
- [x] BUG-C: `test_known_kwargs_pass_through` — verifies legit kwargs still reach handler
- [x] BUG-C: `test_drops_unknown_kwargs_logs_warning` — verifies WARNING emitted
- [x] BUG-C: `test_skips_filter_for_var_keyword_handler` — verifies **kwargs handlers unaffected
- [x] BUG-D: `test_content_alias_accepted_no_error` — no TypeError when content= passed
- [x] BUG-D: `test_html_content_alias_maps_to_html_content` — content= value reaches reportlab
- [x] BUG-D: `test_html_content_takes_precedence_over_content` — html_content wins when both supplied
- [x] BUG-E: `test_channel_alias_accepted_no_type_error` — no TypeError when channel= passed
- [x] BUG-E: `test_channel_alias_resolves_channel_name` — channel= resolves correctly
- [x] BUG-E: `test_missing_channel_returns_error_not_exception` — error dict returned (not raised)

### Test Results
- [x] 10/10 new tests passing
- [x] 420 total passing (was 410 before BUG-023 beat fix, 413 before this fix)
- [x] 42 pre-existing failures unchanged — no regressions
- [x] No TypeScript/Python errors in modified files

### Scope
- [x] Only `server/app/tools/` and `server/tests/` modified — within Backend scope
- [x] No DB migrations required
- [x] No API contract changes (tool schemas are internal to the LLM layer)

## Decision

**✅ PASS**

All 3 bugs fixed correctly. Global filter is the right defensive approach — it will
silently handle any future LLM kwarg hallucinations without crashing, while the
WARNING log makes them discoverable. Per-tool aliases for BUG-D/E are minimal and
correct — they don't change behavior for existing callers using the original param names.

## Deploy Instructions

```bash
# On EC2:
cd /home/ubuntu/mz-ai-assistant
git pull
sudo systemctl restart mezzofy-api.service
sudo systemctl restart mezzofy-celery.service
```

No migrate.py run needed. No Beat restart needed.
