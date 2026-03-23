# Plan: CR-skills-api-silent-failure-fix
**Lead:** Lead Agent
**Date:** 2026-03-23
**Agent:** Backend only (1 session)
**Risk:** Low — prompt addition + try/except restructure, no schema/API changes

---

## Problem Summary

Two compounding failures prevent document generation from working end-to-end:

### Failure 1 — Anthropic Skills sandbox rejects bash
The `pptx` / `docx` / `pdf` / `xlsx` Anthropic Skills run Python code inside a
code-execution sandbox (`code-execution-2025-08-25`). That sandbox disallows
`subprocess` / `os.system` / shell calls. When the skill's generated code tries
to call bash (e.g. to run soffice for QA or post-processing), the sandbox returns
`"cannot execute the Shell Command bash directly"` in the `code_execution_result`
block. Claude echoes this in its text response. No `file_ids` are produced →
`generate_document_with_skill()` returns `{"success": False, "file_ids": []}`.

### Failure 2 — Silent-failure gap: fallback never triggers on success=False
Every document-generating agent uses this pattern:

```python
try:
    skill_result = await generate_document_with_skill(skill_id="pptx", ...)
    if skill_result.get("success") and skill_result.get("file_ids"):
        ...download artifact...          # ← only runs on success
    # ← GAP: success=False → falls through silently, no fallback triggered
except Exception as e:
    ...legacy fallback (pptx_ops/pdf_ops/docx_ops)...   # ← only on exception
```

When Failure 1 occurs (`success=False`, no exception), the `if` skips AND the
`except` is never entered. Result: empty artifacts returned to user, no fallback,
no error message.

Affected agents: management_agent, sales_agent, marketing_agent, hr_agent,
support_agent, legal_agent, finance_agent (7 files).

---

## Tasks (Backend Agent — 1 session)

### Task 1 — Suppress bash in Skills sandbox via system prompt
**File:** `server/app/llm/llm_manager.py`
**Method:** `generate_document_with_skill()`

Inside the method, when building `user_content`, also set (or append to) the
`system` prompt with a document-generation constraint:

```
system_addon = (
    "IMPORTANT: When generating documents, use ONLY Python library functions "
    "(python-pptx, openpyxl, fpdf2, python-docx). "
    "Do NOT use subprocess, os.system, os.popen, or any shell/bash commands. "
    "The execution sandbox does not allow shell access."
)
```

If `system` is already set (from `_build_system_prompt(task_context)`), append
`system_addon` to it. If `system` is None, set it to `system_addon`.

This instruction is passed on every `chat_with_server_tools` call inside the
`pause_turn` loop, so Claude never attempts bash inside the sandbox.

---

### Task 2 — Close the silent-failure gap in all 7 agents

For each agent listed below, find the document-generation `try/except` block and
restructure it so that `success=False` ALSO triggers the legacy fallback.

**Pattern to apply (conceptually):**
```python
skill_ok = False
try:
    skill_result = await generate_document_with_skill(...)
    if skill_result.get("success") and skill_result.get("file_ids"):
        ...primary path (download artifact)...
        skill_ok = True
except Exception as e:
    logger.warning(f"Skill generation failed (exception): {e}")

if not skill_ok:
    ...legacy fallback (PDFOps / DocxOps / PPTXOps)...
```

**Files to modify and their fallback tools:**

| File | skill_id | Fallback |
|------|----------|---------|
| `server/app/agents/management_agent.py` | pdf (×2 methods) | PDFOps |
| `server/app/agents/sales_agent.py` | pptx (×1 method) | deck_skill.create_pitch_deck |
| `server/app/agents/marketing_agent.py` | pdf (×1), docx (×1) | PDFOps, DocxOps |
| `server/app/agents/hr_agent.py` | pdf (×4 methods) | PDFOps |
| `server/app/agents/support_agent.py` | pdf (×2 methods) | PDFOps |
| `server/app/agents/legal_agent.py` | docx (×1 method) | DocxOps |
| `server/app/agents/finance_agent.py` | pdf (×1 method) | PDFOps |

Total occurrences to fix: ~12 try/except blocks across 7 files.

**Important constraint:** Do NOT change the fallback logic itself — only restructure
so it triggers on `success=False` in addition to exceptions.

---

## Out of Scope

- Do NOT change `_qa_pptx()` or `_qa_docx()` (already fixed with LibreOffice profile isolation)
- Do NOT change the Skills API beta headers or model
- Do NOT add Computer Use beta (`computer-use-2025-11-5`)
- Do NOT touch portal, frontend, or any non-agent/llm files

---

## Quality Gate (Lead Agent reviews before deploy)

- [ ] `generate_document_with_skill()` system prompt includes bash-suppression instruction
- [ ] Instruction is appended (not replacing) existing system prompt — not breaking agent personas
- [ ] All 7 agent files restructured — `success=False` triggers fallback
- [ ] Legacy fallback path untouched — same logic as before
- [ ] No new imports added unnecessarily
- [ ] `logger.warning()` at the top of each fallback path logs why fallback ran (exception vs success=False)

---

## Deploy Checklist

```bash
git pull
sudo systemctl restart mezzofy-api.service
sudo systemctl restart mezzofy-celery.service

# Test: trigger a pitch deck request via mobile app
# Expected: Anthropic Skills generates the file (no bash error in logs)
# If Skills fails: fallback should run and produce a file (not silent empty)
sudo journalctl -u mezzofy-celery.service -f | grep -E "Skill|skill_id|fallback|pptx|docx|pdf"
```

---

## Resume Instructions (Backend Agent)
After /clear, read:
1. CLAUDE.md
2. .claude/agents/backend.md
3. .claude/skills/backend-developer.md
4. .claude/coordination/memory.md
5. This plan file
Then complete Tasks 1 and 2 in order.
