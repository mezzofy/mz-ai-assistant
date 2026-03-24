# Bug Fix Plan: Anthropic Client Timeout Too Short for Research Tasks

**Plan ID:** BUG-022-anthropic-timeout
**Date:** 2026-03-24
**Priority:** High
**Version:** v1.35.1
**Assigned To:** Backend Agent
**Workflow:** workflow-bug-fix

---

## Bug Summary

**BUG-022:** `AnthropicClient` is initialized with `timeout=60.0` (60 seconds). Research-type agent plan steps involve multiple LLM calls with tool use (web_search, scraping, reasoning) that require 2–5 minutes per call. The 60s timeout causes:

1. Every LLM call in the agentic loop times out
2. `AnthropicClient.chat` retries internally (up to 3 attempts × 60s = ~3 min per LLM call)
3. The agent never produces output — the whole agent task "succeeds" with an error or retries
4. The orchestrator marks the step `RETRYING` and re-dispatches it
5. **Result:** Plan step loops in RETRYING indefinitely — never COMPLETED or FAILED

**Confirmed by E2E test:** `test_e2e_agent_plan_cycle.py` — step_1 stayed `RETRYING` for 15+ minutes.

---

## Root Cause

**File:** `server/app/llm/anthropic_client.py`, line 44:
```python
self._client = anthropic.AsyncAnthropic(api_key=self._api_key, timeout=60.0)
```

`timeout=60.0` applies to the **total request duration** per individual API call. Anthropic research tasks with tool use (web_search, multi-step reasoning) routinely take 2–10 minutes per API call.

Anthropic's own docs recommend: "For long-running requests, use a higher timeout (300–600s)."

---

## Fix Scope

**Files to modify:**
1. `server/app/llm/anthropic_client.py` — increase timeout using `httpx.Timeout`
2. `server/app/tasks/tasks.py` — add Celery soft time limit for agent tasks (defensive cap)

**Files to read first:**
- `server/app/llm/anthropic_client.py` — full file
- `server/app/tasks/tasks.py` — the `process_agent_task` and `process_delegated_agent_task` Celery task decorators

---

## Implementation Spec

### Fix 1: `anthropic_client.py` — Granular httpx.Timeout

**Replace:**
```python
self._client = anthropic.AsyncAnthropic(api_key=self._api_key, timeout=60.0)
```

**With:**
```python
import httpx as _httpx
self._client = anthropic.AsyncAnthropic(
    api_key=self._api_key,
    timeout=_httpx.Timeout(
        connect=10.0,    # TCP handshake: 10s is generous
        read=600.0,      # Stream read: 10 minutes for long tool-use chains
        write=30.0,      # Request body upload: 30s
        pool=10.0,       # Wait for connection from pool: 10s
    ),
)
```

**Why 600s read timeout:**
- Research tasks with web_search tool use can run 5–10 minutes
- Claude's own streaming API docs suggest 600s for agentic loops
- The connect/write/pool timeouts remain short (network-layer, not LLM latency)

### Fix 2: `tasks.py` — Celery Task Soft Time Limit (defensive cap)

Add `soft_time_limit` and `time_limit` to `process_delegated_agent_task` to prevent runaway tasks:

Find the `@celery_app.task` decorator for `process_delegated_agent_task` and add:
```python
@celery_app.task(
    bind=True,
    max_retries=1,
    name="app.tasks.tasks.process_delegated_agent_task",
    soft_time_limit=900,   # 15 min: raises SoftTimeLimitExceeded (catchable)
    time_limit=960,        # 16 min: hard kill
)
```

In the task body, catch `SoftTimeLimitExceeded` and return a proper failed result:
```python
from celery.exceptions import SoftTimeLimitExceeded
...
except SoftTimeLimitExceeded:
    logger.warning(f"process_delegated_agent_task: soft time limit exceeded for task {self.request.id}")
    return {"success": False, "content": "Task exceeded maximum execution time (15 minutes).", "error": "soft_time_limit_exceeded"}
```

This ensures the orchestrator receives a proper FAILED result instead of the task hanging forever.

**IMPORTANT:** Do NOT add time limits to `process_agent_task` (the main user-facing task) — that one is already protected by Celery task timeout from the original Celery config. Only add to `process_delegated_agent_task` (the orchestrator step task).

---

## Tests Required

Update `server/tests/test_cleanup_stuck_plans.py` — no changes needed (unit tests mock the LLM).

Add one test to a new or existing test file verifying the Anthropic client timeout is set correctly:

**File:** `server/tests/test_anthropic_client_config.py`

```python
def test_anthropic_client_uses_granular_timeout():
    """AnthropicClient must use httpx.Timeout with read=600 not a flat 60s timeout."""
    import httpx
    from app.llm.anthropic_client import AnthropicClient
    # Patch api_key to avoid real credentials
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        client = AnthropicClient.__new__(AnthropicClient)
        # Check the timeout config on the underlying httpx client
        # anthropic.AsyncAnthropic exposes ._client._base_url_for_env or timeout
        ...
```

Actually keep this simple — just assert the constant value:

```python
# In test_anthropic_client_config.py
def test_anthropic_read_timeout_is_sufficient_for_research():
    """Ensure read timeout >= 300s to support long research tool-use chains."""
    import inspect
    source = inspect.getsource(AnthropicClient.__init__)
    # Verify 60.0 is no longer the flat timeout
    assert "timeout=60.0" not in source, (
        "AnthropicClient still uses flat 60s timeout — must be httpx.Timeout with read>=300s"
    )
    assert "read=600" in source or "read=300" in source, (
        "AnthropicClient must set httpx.Timeout read timeout >= 300s for research tasks"
    )
```

---

## Acceptance Criteria

- [ ] `AnthropicClient` uses `httpx.Timeout(connect=10, read=600, write=30, pool=10)`
- [ ] `process_delegated_agent_task` has `soft_time_limit=900, time_limit=960`
- [ ] `SoftTimeLimitExceeded` is caught and returns proper failed result
- [ ] 1 test verifying timeout config
- [ ] E2E test `test_e2e_agent_plan_cycle.py` completes within 15 minutes after fix

---

## Deploy Steps

1. Git push → EC2 git pull
2. `sudo systemctl restart mezzofy-api.service`
3. `sudo systemctl restart mezzofy-celery.service`
4. Re-run E2E test: `MZ_TEST_ADMIN_PASSWORD="P@ss8888" MZ_TEST_BASE_URL="http://localhost:8000" MZ_PLAN_POLL_TIMEOUT_S=900 venv/bin/pytest tests/test_e2e_agent_plan_cycle.py -v -m integration`

---

## Version Tag

`v1.35.1` — BUG-022: Fix Anthropic client timeout for long-running research tasks
