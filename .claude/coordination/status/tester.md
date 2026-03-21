# Context Checkpoint: Tester Agent
**Date:** 2026-03-22
**Project:** mz-ai-assistant
**Session:** Agent roster + persona routing tests

## Completed This Session (2026-03-22)

### Tests created
- `server/tests/test_agent_roster_routing.py` — **53 new tests** covering:
  - `TestAgentPersonaMap` (12 tests): all 10 dept→persona map entries, unknown-dept fallback, entry count
  - `TestSystemPromptRoster` (13 tests): `LLMManager._build_system_prompt()` self-identity per dept, roster header, all 10 persona names present, roster before template content, custom system_prompt bypass
  - `TestPersonaRouting` (20 tests): `_detect_persona_routing()` — all 10 name-prefix variants (`leo:`, `rex:`, etc.), 5 directed-phrase variants, 5 false-positive safety tests (must return None)
  - `TestDetectAgentTypeWithPersona` (8 tests): `_detect_agent_type()` persona routing priority, existing prefix routing, existing keyword routing, no-match case

### Test Results
- New test file: **53/53 passed**
- Full suite (excluding known infra-dependent files): **501 passed, 17 failed**
- All 17 failures confirmed **pre-existing** (Redis connection errors in test_auth.py + test_e2e_mobile.py, Outlook import errors in test_outlook_ops.py, live API call in test_integration_research_task.py) — verified via `git stash` before/after comparison
- **Zero regressions** from the two backend changes (`llm_manager.py` + `chat.py`)

### What was tested
1. `server/app/llm/llm_manager.py` — `_AGENT_PERSONA_MAP`, `_AGENT_TEAM_ROSTER`, `_build_system_prompt()` persona injection
2. `server/app/api/chat.py` — `_PERSONA_ROUTING`, `_PERSONA_ROUTE_VERBS`, `_detect_persona_routing()`, `_detect_agent_type()` priority order

## Session Status: COMPLETE

---

## Previous Session (2026-03-21)

## Completed This Session

### Tests updated
- `server/tests/test_input_handlers.py`
  - Added `MagicMock` to imports
  - `TestManagementAgentBug004.test_general_response_uses_extracted_text_when_present`: was patching `execute_with_tools`; updated to mock `chat_with_memory` (success path) and assert `tools_called=["memory"]`
  - `TestManagementAgentBug004.test_general_response_falls_back_to_message_when_no_extracted_text`: updated to mock `chat_with_memory` raising → `execute_with_tools` called (fallback path verified)

### Tests created
- `server/tests/test_base_agent.py` — 15 new tests covering:
  - `TestGeneralResponseSuccessPath` (5 tests): `chat_with_memory` called on success, `tools_called=["memory"]`, `text` field extraction, `content` fallback key, memory scope `user:{user_id}`, empty response default
  - `TestGeneralResponseFallbackPath` (3 tests): `execute_with_tools` called when `chat_with_memory` raises, fallback propagates `tools_called`, `"memory"` absent from fallback result
  - `TestSalesAgentGeneralWorkflow` (3 tests): `_general_sales_workflow` delegates to `_general_response`, full chain reaches `chat_with_memory`, `execute()` unknown message routes correctly
  - `TestManagementAgentInheritsGeneralResponse` (2 tests): `_general_response` not in `ManagementAgent.__dict__`, resolves to `BaseAgent._general_response`

## Test Count
- **Before:** 547
- **After:** 562 (+15 in test_base_agent.py)

## Test Results
- All 133 tests across `test_base_agent.py`, `test_input_handlers.py`, `test_sales_agent.py`, `test_hr_agent.py`, `test_agent_separation.py` pass ✅
- Pre-existing failure (unrelated): `test_admin_portal.py::TestDeleteUser::test_delete_user_soft_deletes` — Redis connection refused; confirmed failing before this session

## Patch Target Pattern
`patch("app.llm.llm_manager.get", return_value=mock_llm)` + `mock_llm.chat_with_memory = AsyncMock(...)` — same pattern as existing `execute_with_tools` tests in codebase.

## Key Patching Decisions
- `chat_with_memory` patched via `app.llm.llm_manager.get()` return value (consistent with all other LLM mocking in the test suite)
- `_build_system_prompt` mocked as `MagicMock(return_value="sys")` since it is a sync method called inside `_general_response`
- `ManagementAgent.__dict__` introspection used to assert no `_general_response` override exists

## Session Status: COMPLETE
