# Plan: Fix BUG-C/D/E — Tool Handler Kwarg Mismatches
**Workflow:** bug-fix
**Date:** 2026-03-17
**Created by:** Lead Agent

## Problem Summary

Three tools crash when the LLM passes parameter names that differ from the
exact handler signature. Root cause is in `base_tool.py:71`:

```python
result = await tool["handler"](**kwargs)   # passes ALL LLM kwargs, unfiltered
```

| Bug | Tool | LLM passes | Handler expects | Error |
|-----|------|-----------|----------------|-------|
| BUG-C | `query_analytics` | `start_date` | `metric`, `period` | `unexpected kwarg 'start_date'` |
| BUG-D | `create_pdf` | `content` | `html_content` (required) | `unexpected kwarg 'content'` |
| BUG-E | `teams_post_message` | `channel` | `channel_name` (required) | `unexpected kwarg 'channel'` |

---

## Fix Strategy

**Two-layer fix:**

1. **Global defensive filter in `base_tool.py`** — use `inspect.signature` to
   strip unknown kwargs before calling the handler. Fixes BUG-C (drops `start_date`
   safely — `period` has a default). Protects all future tools.

2. **Per-handler aliases for BUG-D and BUG-E** — `html_content`/`channel_name`
   are *required* params. A silent drop breaks the call. Must accept both names.

---

## Task Breakdown

| # | Task | Agent | File(s) | Depends On | Status |
|---|------|-------|---------|-----------|--------|
| 1 | Global kwarg filter in `base_tool.py` | Backend | `server/app/tools/base_tool.py` | None | NOT STARTED |
| 2 | `create_pdf` alias: accept `content` → `html_content` | Backend | `server/app/tools/document/pdf_ops.py` | None | NOT STARTED |
| 3 | `teams_post_message` alias: accept `channel` → `channel_name` | Backend | `server/app/tools/communication/teams_ops.py` | None | NOT STARTED |
| 4 | Tests for all 3 fixes | Backend | `server/tests/test_tool_kwarg_fixes.py` (new) | 1,2,3 | NOT STARTED |
| 5 | Commit, push, deploy | Backend | — | 4 | NOT STARTED |

Tasks 1, 2, 3 are **independent — implement in parallel** in one session.

---

## Detailed Fix Specifications

### Task 1 — `base_tool.py` global filter

In `execute()`, before calling the handler, filter kwargs to only those the
handler signature accepts:

```python
import inspect

async def execute(self, tool_name: str, **kwargs) -> dict:
    tools_by_name = {t["name"]: t for t in self.get_tools()}
    tool = tools_by_name.get(tool_name)
    if not tool:
        return {"success": False, "error": f"Tool '{tool_name}' not found in {self.__class__.__name__}"}

    try:
        handler = tool["handler"]
        # Filter kwargs to only params the handler accepts
        sig = inspect.signature(handler)
        accepted = set(sig.parameters.keys()) - {"self"}
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        if not has_var_keyword:
            filtered = {k: v for k, v in kwargs.items() if k in accepted}
            if len(filtered) < len(kwargs):
                dropped = set(kwargs) - set(filtered)
                logger.warning(f"Tool '{tool_name}' dropped unknown kwargs: {dropped}")
            kwargs = filtered

        result = await handler(**kwargs)
        ...
```

> **Note:** If the handler uses `**kwargs`, skip filtering (has_var_keyword=True).

### Task 2 — `pdf_ops.py` `content` alias

Update `_create_pdf` signature:

```python
async def _create_pdf(
    self,
    title: str,
    html_content: str = None,
    content: str = None,      # ← alias accepted from LLM
    document_type: str = "Report",
    filename: str = None,
    extra_css: str = None,
    storage_scope: str = "user",
) -> dict:
    html_content = html_content or content or ""
    ...
```

Also update the tool schema `parameters.properties` to document `content` as an
accepted alias (add it alongside `html_content`), so the LLM sees both:

```python
"content": {
    "type": "string",
    "description": "Alias for html_content. HTML body content to render as PDF.",
},
```

And update `required` to `["title"]` (remove `html_content` from required
since `content` is an alias — both optional when the other is provided).

### Task 3 — `teams_ops.py` `channel` alias

Update `_post_message` signature:

```python
async def _post_message(
    self,
    channel_name: str = None,
    content: str = "",
    channel: str = None,      # ← alias accepted from LLM
    subject: str = None,
) -> dict:
    channel_name = channel_name or channel
    if not channel_name:
        return self._err("channel_name (or channel) is required.")
    ...
```

Also update the tool schema to add `channel` as an alias property in
`parameters.properties` with description: `"Alias for channel_name."`.

### Task 4 — Tests (`server/tests/test_tool_kwarg_fixes.py`)

New test file, 5 tests:

1. **`test_base_tool_drops_unknown_kwarg`** — subclass BaseTool with a handler
   that accepts only `(metric, period)`. Call `execute("tool", metric="x", start_date="2026")`.
   Assert handler is called without `start_date` (no TypeError).

2. **`test_base_tool_passes_known_kwargs`** — same setup, assert known params
   ARE passed through correctly.

3. **`test_create_pdf_accepts_content_alias`** — patch `PDFOps._create_pdf_reportlab`.
   Call `executor.execute("create_pdf", title="T", content="<p>body</p>")`.
   Assert no error, assert `html_content` received `"<p>body</p>"`.

4. **`test_teams_post_message_accepts_channel_alias`** — patch MS Graph client.
   Call `executor.execute("teams_post_message", channel="sales", content="Hello")`.
   Assert `channel_name` resolves to `"sales"` (no unexpected kwarg error).

5. **`test_base_tool_skips_filter_for_var_keyword_handler`** — handler with `**kwargs`.
   Assert all kwargs pass through unfiltered.

---

## Files to Modify

| File | Change |
|------|--------|
| `server/app/tools/base_tool.py` | Add `import inspect`; filter kwargs in `execute()` |
| `server/app/tools/document/pdf_ops.py` | Add `content=None` alias to `_create_pdf`; update schema |
| `server/app/tools/communication/teams_ops.py` | Add `channel=None` alias to `_post_message`; update schema |
| `server/tests/test_tool_kwarg_fixes.py` | New — 5 tests |

**No DB migrations, no API changes, no service restarts needed.**
After git push → EC2 git pull → restart `mezzofy-api.service` and `mezzofy-celery.service`.

---

## Quality Gate

Backend Agent must:
- [ ] All 5 new tests passing
- [ ] Existing test suite still at 410 passed (no regressions)
- [ ] `create_pdf` called with `content=` produces a PDF (not a blank/error)
- [ ] `teams_post_message` called with `channel=` resolves to correct channel
- [ ] `query_analytics` called with `start_date=` logs a warning and proceeds with defaults

**Estimated sessions:** Backend — 1 session (small, 4 targeted files)
