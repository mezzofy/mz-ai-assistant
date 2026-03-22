# Quality Gate Review: Leo (Legal Agent) — Backend Implementation
**Date:** 2026-03-23
**Reviewer:** Lead Agent
**Verdict:** ⚠️ CONDITIONAL PASS — 1 gap to fix before full deployment

---

## Review Summary

The Leo backend implementation is **substantially complete** — 7 of 8 tasks fully done. One integration gap exists in `tasks.py` that blocks Celery delegation (Management → Leo). Direct user routing works fine.

---

## Task Checklist

### ✅ Task 1 — `server/app/agents/legal_agent.py`

| Check | Result |
|-------|--------|
| Subclasses BaseAgent | ✅ |
| `LEGAL_DISCLAIMER` constant defined | ✅ |
| `LEGAL_TRIGGERS` list present (37 triggers) | ✅ |
| `can_handle()` — both agent_override and keyword path | ✅ `task.get("agent_override") == "legal"` OR `task.get("agent") == "legal"` OR keyword match |
| `execute()` — log_task_start at entry | ✅ |
| `execute()` — LEGAL_DISCLAIMER appended on all 5 workflow returns | ✅ |
| `execute()` — log_task_complete / log_task_failed | ✅ |
| All 5 workflow methods present | ✅ `review_document`, `generate_contract`, `extract_clauses`, `assess_legal_risk`, `provide_legal_advice` |
| Helper methods | ✅ `_classify_legal_task`, `_classify_jurisdiction`, `_get_jurisdiction_knowledge_file`, `_load_jurisdiction_knowledge`, `_load_contract_template` |
| Lazy imports (Ops classes inside method bodies) | ✅ All `from app.llm import llm_manager as llm_mod` inside methods |
| `task["system_prompt"]` override pattern used | ✅ All workflow methods inject system_prompt into task dict before LLM call |
| `load_agent_record("agent_legal")` called in execute() | ✅ |

### ✅ Task 2 — 4 YAML Skill Files

All present in `server/app/skills/available/`:
- `document_review.yaml` ✅
- `contract_drafting.yaml` ✅
- `legal_research.yaml` ✅
- `jurisdiction_advisory.yaml` ✅

### ✅ Task 3 — 4 Python Skill Files

All present in `server/app/skills/available/`:
- `document_review.py` ✅
- `contract_drafting.py` ✅
- `legal_research.py` ✅
- `jurisdiction_advisory.py` ✅

### ✅ Task 4 — Knowledge Base (`server/knowledge/legal/`)

| Directory | Files |
|-----------|-------|
| `jurisdictions/` | singapore.md, hong_kong.md, malaysia.md, uae.md, saudi_arabia.md, qatar.md, cayman_islands.md ✅ (all 7) |
| `templates/singapore/` | nda.md, service_agreement.md, employment_contract.md, mou.md, vendor_agreement.md ✅ |
| `templates/hong_kong/` | nda.md, service_agreement.md, employment_contract.md ✅ |
| `templates/malaysia/` | nda.md, service_agreement.md ✅ |
| `templates/uae/` | nda.md, service_agreement.md ✅ |
| `templates/cayman_islands/` | shareholders_agreement.md, exempted_company_mou.md ✅ |
| `templates/general/` | nda.md, mou.md, loi.md ✅ |
| `clause_library/` | confidentiality, data_protection, dispute_resolution, entire_agreement, force_majeure, governing_law, indemnity, ip, liability, termination ✅ (all 10) |
| `advisory/` | data_protection_comparison, employment_law_overview, international_business_law, ip_protection_asia, regulatory_compliance_overview ✅ (all 5) |

### ✅ Task 5 — `migrate.py` DB Seed

`agent_legal` seeded with: id, name, display_name, department, description, skills (4), tools_allowed, llm_model, memory_namespace, is_orchestrator (FALSE), can_be_spawned (TRUE), is_active (TRUE). `ON CONFLICT (id) DO NOTHING` — safe to re-run. ✅

### ✅ Task 6 — Router Integration

**`server/app/api/chat.py`:**
- `LEGAL_TRIGGERS` imported from `legal_agent.py` ✅
- `_is_legal_request()` helper function present ✅
- `_detect_agent_type()` returns `"legal"` for `legal:` prefix OR keyword match ✅
- `"leo"` persona in `_PERSONA_ROUTING` dict → routes to `"legal"` ✅
- Routing order: persona → prefix → legal keywords (before long-running check) ✅

**`server/app/agents/agent_registry.py` (`AGENT_MAP`):**
- `"legal": LegalAgent` ✅
- `"agent_legal": LegalAgent` (explicit override support) ✅
- Router's `_execute_by_name("legal", ...)` works correctly ✅

### ✅ Task 7 — `server/config/roles.yaml`

- `legal_read` permission defined — covers review/analysis/jurisdiction tools ✅
- `legal_write` permission defined — covers draft_contract/generate_legal_document ✅
- `legal` department role has both permissions ✅
- Executive roles have `legal_read` ✅

### ❌ GAP — `tasks.py` `_AGENT_ID_MAP` Missing `agent_legal`

**File:** `server/app/tasks/tasks.py`, function `get_agent_by_id()`, lines ~807–817

**Problem:** `_AGENT_ID_MAP` contains only 9 agents. `agent_legal` is absent.

**Impact:** When Management Agent (Max) uses `delegate_task("agent_legal", ...)`, Celery's `process_delegated_agent_task` calls `get_agent_by_id("agent_legal")` → raises `ValueError: unknown agent_id 'agent_legal'`. Cross-department delegation from Max to Leo **fails silently** (Celery marks task as failed).

**Direct routing still works:** User typing "draft an NDA" → `chat.py` → `router.py` → `AGENT_MAP["legal"]` → Leo executes. Only the Celery delegation path is broken.

**Fix required (Backend Agent — ~5 min):**

In `server/app/tasks/tasks.py`, inside `get_agent_by_id()`:

```python
# Add import:
from app.agents.legal_agent import LegalAgent

# Add to _AGENT_ID_MAP:
"agent_legal": LegalAgent(_config),
```

Also update the docstring: `"AGENT_ID_MAP covers all 9 agents"` → `"covers all 10 agents (6 department + 4 special-purpose)"`

---

## What Works Right Now (Before Fix)

- ✅ Direct Leo invocation: "draft an NDA", "review this contract", "what's the governing law in Singapore"
- ✅ Persona routing: "leo: review this agreement"
- ✅ Prefix routing: "legal: draft an employment contract"
- ✅ Legal disclaimer on all outputs
- ✅ Jurisdiction knowledge loading (7 jurisdictions)
- ✅ Contract template loading
- ✅ Document review, contract generation, clause extraction, risk assessment, legal advisory workflows

## What Breaks Until Fix

- ❌ Management Agent delegating "Review this contract for the sales team" → Leo via Celery

---

## Deploy Instructions (After Fix)

```bash
# EC2:
git pull
python scripts/migrate.py          # seeds agent_legal row
sudo systemctl restart mezzofy-api.service
sudo systemctl restart mezzofy-celery.service
```

No portal rebuild needed. No nginx restart needed.

---

## Verdict

**CONDITIONAL PASS.** Leo is fully functional for direct invocation. Fix the single line in `tasks.py` to complete the Celery delegation path. The fix is trivial (~5 min Backend Agent work).
