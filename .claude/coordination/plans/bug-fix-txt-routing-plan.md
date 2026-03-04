# Plan: Bug Fix — create_txt routing to wrong agent + no tool access in general response
**Workflow:** bug-fix
**Date:** 2026-03-04
**Created by:** Lead Agent

---

## Problem Statement

User (Management dept) sends: "Create a notes.txt with content Hello"
Expected: ManagementAgent handles it, LLM calls create_txt, file saved
Actual: MarketingAgent intercepts it, generates a "500-word landing page" about the message

---

## Root Cause Analysis

### Bug 1 — Wrong agent selected (PRIMARY)

**File:** `server/app/agents/marketing_agent.py` lines 18–22
**Cause:** `_TRIGGER_KEYWORDS` contains the generic word `"content"`.
The message "Create a notes.txt with **content** Hello" contains the word "content"
→ `MarketingAgent.can_handle()` returns True
→ MarketingAgent routes to `content_generation` skill with `content_type="website"` (default)
→ `ContentGenerationSkill._build_prompt()` generates prompt: "Write website landing page copy about..."
   with `_CONTENT_LENGTHS["medium"] = 500` → "500-word landing page"
→ LLM correctly detects the mismatch and explains it to the user

Other overly generic words in the same set: `"write"`, `"draft"`, `"post"`, `"copy"` —
these will cause similar misrouting for other non-marketing requests.

**Fix:** Remove generic English words. Keep only clearly marketing-domain terms.

Current:
```python
_TRIGGER_KEYWORDS = {
    "content", "website", "blog", "playbook", "campaign", "social media",
    "newsletter", "copy", "brand", "landing page", "post", "write", "draft",
    "marketing", "email blast", "announcement", "feature description",
}
```

Replace with:
```python
_TRIGGER_KEYWORDS = {
    "website copy", "blog post", "blog article", "playbook", "campaign",
    "social media", "newsletter", "brand guidelines", "landing page",
    "marketing", "email blast", "announcement", "feature description",
}
```

Key changes:
- "content" → REMOVED (too generic: appears in file content, product content, etc.)
- "copy" → REMOVED (means "file copy" as often as "marketing copy")
- "write" → REMOVED (generic verb used in all contexts)
- "draft" → REMOVED (generic — "draft PR", "draft email", etc.)
- "post" → REMOVED (means "POST request", "Teams post", not just social post)
- "blog" → changed to "blog post" / "blog article" (more specific)
- "brand" → changed to "brand guidelines" (more specific)
- "website" → changed to "website copy" (bare "website" is too generic)

---

### Bug 2 — No tools exposed in ManagementAgent general response (SECONDARY)

**File:** `server/app/agents/management_agent.py` lines 71–79
**Cause:** `_general_response()` calls `llm_mod.get().chat()` which has NO tools parameter.
Even if routing is correct, the LLM cannot call `create_txt` (or any other tool) from this path.

**Current code:**
```python
async def _general_response(self, task: dict) -> dict:
    content = task.get("extracted_text") or task.get("message", "")
    llm_result = await llm_mod.get().chat(
        messages=[{"role": "user", "content": content}],
        task_context=task,
    )
    content = llm_result.get("content", "I'm here to help. Could you clarify your request?")
    return self._ok(content=content)
```

**Fix:** Replace with `execute_with_tools()` and map `conversation_history` → `messages`
(chat.py stores history as `task["conversation_history"]` but execute_with_tools reads `task["messages"]`).

```python
async def _general_response(self, task: dict) -> dict:
    """General question — answer via LLM with full tool access (create_txt, create_csv, etc.)."""
    task_for_llm = {**task, "messages": task.get("conversation_history", [])}
    llm_result = await llm_mod.get().execute_with_tools(task_for_llm)
    content = llm_result.get("content", "I'm here to help. Could you clarify your request?")
    tools_called = llm_result.get("tools_called", [])
    return self._ok(content=content, tools_called=tools_called)
```

This enables:
1. LLM can call any registered tool (create_txt, create_csv, create_pdf, etc.)
2. Multi-turn tool use works (LLM asks "personal or shared?" → user replies → LLM calls tool)
3. Conversation history is passed so the LLM remembers the storage preference

---

## Changes Required

| # | File | Change | Lines |
|---|------|--------|-------|
| 1 | `server/app/agents/marketing_agent.py` | Replace `_TRIGGER_KEYWORDS` with specific marketing-only terms | 18–22 |
| 2 | `server/app/agents/management_agent.py` | Replace `_general_response()` to use `execute_with_tools` with history | 71–79 |

**No other files need to change.** The previously created `text_ops.py` and the `tool_executor.py` + `llm_manager.py` edits from the previous session are correct.

---

## Task Assignment

**Agent:** Backend Agent (these are Python server files)
**Sessions:** 1 (two small method-level changes)

---

## Verification After Deploy

On EC2:
```bash
sudo systemctl restart mezzofy-api.service

# Test 1: Management user asks to create notes.txt
# Expected: AI asks "personal or shared?" NOT "500-word landing page"

# Test 2: User replies "personal"
# Expected: AI calls create_txt, file appears in Files screen

# Verify on disk:
find /var/mezzofy/artifacts/management/admin@mezzofy.com/ -name "*.txt"
```

Also verify Marketing still works:
- "Write a landing page for our new coupon feature" → still routes to MarketingAgent ✅
- "Create a blog post about Mezzofy" → still routes to MarketingAgent ✅

---

## Acceptance Criteria

- [ ] "Create a notes.txt with content Hello" → ManagementAgent handles it
- [ ] LLM asks "personal or shared?" before calling create_txt
- [ ] File created at correct path after user answers
- [ ] File appears in Files screen
- [ ] Marketing agent still handles legitimate marketing requests
