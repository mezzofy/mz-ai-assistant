# Context Checkpoint: Backend Agent
**Date:** 2026-03-21
**Session:** 33 — Agent persona names + team roster + persona routing
**Context:** ~20% at checkpoint
**Reason:** Change request complete

## Completed This Session

- ✅ Added `_AGENT_PERSONA_MAP` constant to `llm_manager.py` (after `_ATTACHED_IMAGE_DIRECTIVE`)
- ✅ Added `_AGENT_TEAM_ROSTER` constant to `llm_manager.py` (after `_AGENT_PERSONA_MAP`)
- ✅ Updated `_build_system_prompt()` in `llm_manager.py` to inject `self_identity` + `_AGENT_TEAM_ROSTER` prefix before the formatted system prompt
- ✅ Added `_PERSONA_ROUTING` dict to `chat.py` (after `_SCHEDULER_KEYWORDS`)
- ✅ Added `_PERSONA_ROUTE_VERBS` list to `chat.py` (after `_PERSONA_ROUTING`)
- ✅ Added `_detect_persona_routing()` helper function to `chat.py` (before `_detect_agent_type()`)
- ✅ Replaced `_detect_agent_type()` body in `chat.py` to call `_detect_persona_routing()` first (highest priority), then fall through to existing keyword/prefix routing

## Files Modified
- `server/app/llm/llm_manager.py` (added 2 module-level constants + 2 lines in `_build_system_prompt()`)
- `server/app/api/chat.py` (added 2 constants + new `_detect_persona_routing()` + replaced `_detect_agent_type()`)

## Decisions Made
- `_detect_persona_routing()` scans both name-prefix ("leo: ...") and directed-verb ("ask leo ...", "route to leo") patterns
- False-positive guard: "the max items" → None because "max" has no verb prefix and doesn't start with "max:"
- No agent `*.py` files in `server/app/agents/` were modified
- No test files were modified

## Previous Session Summary (session 32 — chat_with_memory() wired to all agents)
- `server/app/agents/base_agent.py`, `management_agent.py`, `sales_agent.py`

## Resume Instructions
No resume needed — change request complete.
Deploy: git push → EC2 git pull → sudo systemctl restart mezzofy-api mezzofy-celery
