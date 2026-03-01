# Review: Backend Agent — Phase 4 (LLM + Skills + Agents)
**Reviewer:** Lead Agent
**Date:** 2026-02-27
**Verdict:** ✅ PASS (after fixes)

---

## Findings

### 🔴 Blockers

**11 incorrect import paths** — all runtime `ModuleNotFoundError` or wrong class names.

The Backend Agent used `app.tools.comm.*` (non-existent directory) and wrong class names (`PdfOps`, `PptxOps`) in Phase 4 files. The actual directories are `app.tools.communication/` and `app.tools.document/`, and the actual class names are `PDFOps`, `PPTXOps` (uppercase acronyms).

| # | File | Line | Wrong Import | Correct Import |
|---|------|------|-------------|----------------|
| 1 | `server/app/agents/base_agent.py` | 134 | `from app.tools.comm.teams_ops import TeamsOps` | `from app.tools.communication.teams_ops import TeamsOps` |
| 2 | `server/app/agents/base_agent.py` | 155 | `from app.tools.comm.outlook_ops import OutlookOps` | `from app.tools.communication.outlook_ops import OutlookOps` |
| 3 | `server/app/agents/management_agent.py` | 110 | `from app.tools.comm.pdf_ops import PdfOps` | `from app.tools.document.pdf_ops import PDFOps` |
| 4 | `server/app/agents/management_agent.py` | 160 | `from app.tools.comm.pdf_ops import PdfOps` | `from app.tools.document.pdf_ops import PDFOps` |
| 5 | `server/app/agents/marketing_agent.py` | 77 | `from app.tools.comm.pdf_ops import PdfOps` | `from app.tools.document.pdf_ops import PDFOps` |
| 6 | `server/app/agents/marketing_agent.py` | 94 | `from app.tools.comm.docx_ops import DocxOps` | `from app.tools.document.docx_ops import DocxOps` |
| 7 | `server/app/agents/support_agent.py` | 97 | `from app.tools.comm.pdf_ops import PdfOps` | `from app.tools.document.pdf_ops import PDFOps` |
| 8 | `server/app/agents/support_agent.py` | 144 | `from app.tools.comm.pdf_ops import PdfOps` | `from app.tools.document.pdf_ops import PDFOps` |
| 9 | `server/app/skills/available/email_outreach.py` | 77 | `from app.tools.comm.outlook_ops import OutlookOps` | `from app.tools.communication.outlook_ops import OutlookOps` |
| 10 | `server/app/skills/available/financial_reporting.py` | 111 | `from app.tools.comm.pdf_ops import PdfOps` | `from app.tools.document.pdf_ops import PDFOps` |
| 11 | `server/app/skills/available/pitch_deck_generation.py` | 25 | `from app.tools.comm.pptx_ops import PptxOps` | `from app.tools.document.pptx_ops import PPTXOps` |

**Root cause:** `app.tools.comm` does not exist. Actual subdirectories are `communication/` and `document/`.
**Also:** Class names `PdfOps` and `PptxOps` are wrong — actual classes are `PDFOps` and `PPTXOps`.

---

### 🟡 Warnings

None beyond the blockers.

---

### 🟢 Suggestions

None.

---

## What Passed ✅

- LLM routing: Chinese text → Kimi (unicodedata + regex) ✅
- Default model: `claude-sonnet-4-6` ✅
- Auto-failover: `fallback = self.kimi if model is self.claude else self.claude` ✅
- Tool loop cap: `MAX_TOOL_ITERATIONS = 5` ✅
- `_append_tool_exchange()` handles both Anthropic (content blocks) and OpenAI (tool_calls array) ✅
- All 5 agents implement `can_handle()` and `execute()` ✅
- Skills load from registry via `_load_skill()` ✅
- Scheduler/webhook tasks skip permission checks ✅
- Email rate limiting 30/hour in `EmailOutreachSkill` ✅
- `llm_manager.get()` singleton added correctly ✅
- `agent_registry.py` added (proactive — unblocks Phase 5 router) ✅

---

## Summary

Architecture is correct. The LLM layer, skill infrastructure, and agent workflow logic are all sound. The only issue is 11 wrong import paths — a naming inconsistency introduced in Phase 4 against the actual Phase 2/3 directory structure (`comm` vs `communication`, `document`). All affected files are in the agents/ and skills/available/ directories. Fixes are mechanical search-and-replace.

---

## Fixes Required (Backend Agent)

Apply these 4 substitutions across the affected files:

| Find | Replace |
|------|---------|
| `from app.tools.comm.outlook_ops import OutlookOps` | `from app.tools.communication.outlook_ops import OutlookOps` |
| `from app.tools.comm.teams_ops import TeamsOps` | `from app.tools.communication.teams_ops import TeamsOps` |
| `from app.tools.comm.pdf_ops import PdfOps` | `from app.tools.document.pdf_ops import PDFOps` |
| `from app.tools.comm.pptx_ops import PptxOps` | `from app.tools.document.pptx_ops import PPTXOps` |
| `from app.tools.comm.docx_ops import DocxOps` | `from app.tools.document.docx_ops import DocxOps` |

Also update all call-site usages: `PdfOps(` → `PDFOps(`, `PptxOps(` → `PPTXOps(`.

Files to fix:
1. `server/app/agents/base_agent.py`
2. `server/app/agents/management_agent.py`
3. `server/app/agents/marketing_agent.py`
4. `server/app/agents/support_agent.py`
5. `server/app/skills/available/email_outreach.py`
6. `server/app/skills/available/financial_reporting.py`
7. `server/app/skills/available/pitch_deck_generation.py`

---

## Re-Review Result (2026-02-27)

All 11 fixes verified:
- `base_agent.py:134` → `app.tools.communication.teams_ops` ✅
- `base_agent.py:155` → `app.tools.communication.outlook_ops` ✅
- `management_agent.py:110,160` → `app.tools.document.pdf_ops import PDFOps` + `PDFOps(` ✅
- `marketing_agent.py:77,94` → `app.tools.document.pdf_ops + docx_ops`; `PDFOps(` ✅
- `support_agent.py:97,144` → `app.tools.document.pdf_ops import PDFOps`; `PDFOps(` ✅
- `email_outreach.py:77` → `app.tools.communication.outlook_ops` ✅
- `financial_reporting.py:111` → `app.tools.document.pdf_ops import PDFOps`; `PDFOps(` ✅
- `pitch_deck_generation.py:25` → `app.tools.document.pptx_ops import PPTXOps`; `PPTXOps(` ✅

`grep "app.tools.comm\."` → **0 matches**
`grep "PdfOps\(|PptxOps\("` → **0 matches**

**Phase 4 quality gate: PASSED → Phase 5 UNBLOCKED**
