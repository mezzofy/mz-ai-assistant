# Plan: Leo (Legal Agent) — Backend Implementation
**Workflow:** change-request
**Date:** 2026-03-19
**Created by:** Lead Agent
**Source:** docs/LEGAL_AGENT_PROMPT.md — Phases 1–6

---

## Context

Leo (Legal Agent) is fully documented in all 3 docs (commit a9cfa5a).
This plan covers the backend implementation only — all 6 phases from LEGAL_AGENT_PROMPT.md.
Documentation review gate: PASSED.

**Key facts for implementation:**
- Agent ID: `agent_legal` | Persona: Leo | Department: `legal`
- Skills: `document_review`, `contract_drafting`, `legal_research`, `jurisdiction_advisory`
- LLM: `claude-sonnet-4-6` | RAG Namespace: `legal` | Is Orchestrator: FALSE
- Cross-departmental: any dept can invoke; Management can delegate via `delegate_task()`
- Legal disclaimer appended to ALL outputs (non-negotiable)

---

## Task Breakdown

| # | Task | File(s) | Depends On | Status |
|---|------|---------|-----------|--------|
| 1 | Legal Agent class | `server/app/agents/legal_agent.py` | None | NOT STARTED |
| 2 | 4 skill YAML files | `server/app/skills/available/document_review.yaml` etc. | None | NOT STARTED |
| 3 | 4 skill Python files | `server/app/skills/available/document_review.py` etc. | Task 2 | NOT STARTED |
| 4 | Knowledge base files | `server/knowledge/legal/` (7 jurisdictions + templates + clauses) | None | NOT STARTED |
| 5 | DB seed in migrate.py | `server/scripts/migrate.py` — INSERT agent_legal | None | NOT STARTED |
| 6 | Router integration | `server/app/api/chat.py` + `server/app/router.py` | Task 1 | NOT STARTED |
| 7 | Permissions | `server/config/roles.yaml` | None | NOT STARTED |

Tasks 1, 2, 4, 5, 7 can run in parallel. Task 3 depends on Task 2. Task 6 depends on Task 1.

---

## Detailed Implementation Specs

### Task 1 — `server/app/agents/legal_agent.py`

Follow the exact spec in `docs/LEGAL_AGENT_PROMPT.md` Phase 1.
Key requirements:
- Subclass `BaseAgent` (same pattern as existing agents)
- `LEGAL_DISCLAIMER` constant — append to ALL `content` and `summary` fields in results
- `LEGAL_TRIGGERS` list — full list from prompt (contract, NDA, agreement, legal advice, etc.)
- `can_handle(task)` → check `task.get("agent_override") == "legal"` OR legal trigger in message
- `execute(task)` → `log_task_start()` → `_classify_legal_task()` → route to workflow → append disclaimer → `log_task_complete()`
- 5 async workflow methods: `review_document()`, `generate_contract()`, `extract_clauses()`, `assess_legal_risk()`, `provide_legal_advice()`
- 3 helper methods: `_classify_legal_task()`, `_classify_jurisdiction()`, `_get_jurisdiction_knowledge_file()`
- All Ops imports INSIDE method bodies (lazy import pattern — see memory.md)
- Uses `docx_ops.py` (create_docx, read_docx) and `pdf_ops.py` (create_pdf, read_pdf)

### Task 2 — Skill YAML files (4 files)

Create in `server/app/skills/available/`:

**`document_review.yaml`** — spec from LEGAL_AGENT_PROMPT.md Phase 2, Skill 1:
- capabilities: extract_text_from_pdf, extract_text_from_docx, identify_document_type, detect_parties, detect_governing_law, detect_key_dates
- tools: extract_legal_document, identify_document_type, detect_parties, detect_governing_law
- dependencies: python-docx>=1.1.0, reportlab>=4.0.7, PyPDF2>=3.0.0

**`contract_drafting.yaml`** — spec from Phase 2, Skill 2:
- capabilities: draft_nda, draft_service_agreement, draft_employment_contract, draft_mou, draft_vendor_agreement, draft_consultancy_agreement, draft_ip_assignment, draft_distribution_agreement, draft_loi, customise_jurisdiction_clauses
- tools: draft_contract, customise_clauses, get_contract_template
- dependencies: python-docx>=1.1.0, jinja2>=3.1.3

**`legal_research.yaml`** — spec from Phase 2, Skill 3:
- tools: research_jurisdiction_law, lookup_regulatory_requirements, check_compliance_requirements
- dependencies: playwright>=1.40.0, beautifulsoup4>=4.12.0

**`jurisdiction_advisory.yaml`** — spec from Phase 2, Skill 4:
- Contains full `jurisdictions_covered` block (SG, HK, MY, UAE, KSA, QA, Cayman)
- tools: get_jurisdiction_overview, compare_jurisdictions, recommend_jurisdiction

### Task 3 — Skill Python files (4 files)

Create paired `.py` files alongside each YAML:

**`document_review.py`** — `DocumentReviewSkill` class:
- `extract_legal_document(file_path, file_type="auto")` → uses existing pdf_ops/docx_ops for text extraction
- `identify_document_type(document_text)` → LLM classification
- `detect_parties(document_text)` → LLM extraction
- `detect_governing_law(document_text)` → LLM extraction
- Max 50MB / 200 pages; truncate with warning if exceeded

**`contract_drafting.py`** — `ContractDraftingSkill` class:
- `draft_contract(contract_type, party_a, party_b, commercial_terms, governing_law, special_clauses, output_format)` → full generation pipeline
- `customise_clauses(base_contract_text, modifications, governing_law)` → apply modifications
- `get_contract_template(contract_type, jurisdiction)` → load from `knowledge/legal/templates/{jurisdiction}/{contract_type}.md`
- Supported types: 11 (from prompt). Supported jurisdictions: 8 (from prompt).

**`legal_research.py`** — `LegalResearchSkill` class:
- `research_jurisdiction_law(topic, jurisdiction, depth="standard")` → KB lookup + optional web search
- `lookup_regulatory_requirements(activity, jurisdiction, entity_type)` → KB lookup
- `check_compliance_requirements(company_type, jurisdictions, industry, annual_revenue_usd)` → multi-jurisdiction check

**`jurisdiction_advisory.py`** — `JurisdictionAdvisorySkill` class:
- `get_jurisdiction_overview(jurisdiction, topic)` → load jurisdiction MD file + LLM summary
- `compare_jurisdictions(topic, jurisdictions)` → load multiple MD files + LLM comparison table
- `recommend_jurisdiction(business_activity, considerations, company_size)` → LLM recommendation

### Task 4 — Knowledge Base Files

Create directory structure under `server/knowledge/legal/`:

```
server/knowledge/legal/
├── README.md
├── jurisdictions/
│   ├── singapore.md          ← Full content provided in LEGAL_AGENT_PROMPT.md
│   ├── hong_kong.md
│   ├── malaysia.md
│   ├── uae.md
│   ├── saudi_arabia.md
│   ├── qatar.md
│   └── cayman_islands.md
├── templates/
│   ├── singapore/ (nda.md, service_agreement.md, employment_contract.md, vendor_agreement.md, mou.md)
│   ├── hong_kong/ (nda.md, service_agreement.md, employment_contract.md)
│   ├── malaysia/ (nda.md, service_agreement.md)
│   ├── uae/ (nda.md, service_agreement.md)
│   ├── cayman_islands/ (shareholders_agreement.md, exempted_company_mou.md)
│   └── general/ (nda.md, mou.md, loi.md)
├── clause_library/
│   └── (10 clause files: indemnity, liability, ip, data_protection, force_majeure, etc.)
└── advisory/
    └── (5 advisory files: international_business_law, data_protection_comparison, etc.)
```

Singapore seed content is fully provided in LEGAL_AGENT_PROMPT.md. Create equivalent files for all 6 other jurisdictions following the same structure:
**Legal System → Key Statutes for Business → Standard Contractual Practices → Common Risk Areas for Foreign Companies**

Each jurisdiction file must be comprehensive enough to serve as Leo's standalone knowledge context.

### Task 5 — DB Seed in `server/scripts/migrate.py`

Add Leo to the agents table seed. **Append-only — do NOT modify existing agent seeds.**

```sql
INSERT INTO agents (
  id, name, display_name, department, description,
  skills, tools_allowed, llm_model, memory_namespace,
  is_orchestrator, can_be_spawned, is_active
) VALUES (
  'agent_legal', 'Legal Agent', 'Leo (Legal)', 'legal',
  'I review and draft business contracts, provide jurisdiction-specific legal advisory
   for Singapore, Hong Kong, Malaysia, UAE, Saudi Arabia, Qatar, and Cayman Islands,
   and assess legal risk in documents.',
  '["document_review", "contract_drafting", "legal_research", "jurisdiction_advisory"]',
  '["read_pdf", "read_docx", "create_docx", "create_pdf", "outlook_send_email",
    "teams_post_message", "database_query", "web_research"]',
  'claude-sonnet-4-6', 'legal', FALSE, TRUE, TRUE
) ON CONFLICT (id) DO NOTHING;
```

Note: Check whether migrate.py uses `can_be_spawned` column — if not present in agents table schema, use the existing column set from prior agents (id, name, department, skills, tools_allowed, llm_model, memory_namespace, is_orchestrator, is_active).

### Task 6 — Router Integration

**`server/app/api/chat.py`** — Add Leo to `_detect_agent_type()`:
- Import `LEGAL_TRIGGERS` from `legal_agent.py`
- Add condition: if any legal trigger in message → set `task_payload["agent"] = "legal"`
- **CRITICAL ORDER:** Legal detection must run BEFORE `_is_long_running()` check (same pattern as scheduler — see memory.md SchedulerAgent routing note)

**`server/app/router.py`** — Add Leo to AGENT_MAP:
- `"agent_legal": LegalAgent` (import LegalAgent at top of file)
- `_route_mobile()` already handles `task["agent"]` short-circuit — no additional changes needed if AGENT_MAP entry is added correctly

### Task 7 — `server/config/roles.yaml`

**Append-only.** Add:
```yaml
legal_read:
  description: "Read and receive legal document analysis"
  departments: ["legal", "management", "sales", "finance", "hr", "support"]

legal_write:
  description: "Request contract drafting and generation"
  departments: ["legal", "management", "sales", "finance", "hr"]
```

Note: Legal is cross-departmental — `legal_read` is broad (all depts); `legal_write` excludes support (support doesn't draft contracts).

---

## Parallel Opportunities

- Tasks 1, 2, 4, 5, 7 → all independent, can be done in one session
- Task 3 → after Task 2 YAML files exist (skill classes reference YAML-defined capabilities)
- Task 6 → after Task 1 (needs LEGAL_TRIGGERS import from legal_agent.py)

**Recommended session order:**
1. Session A (one Backend session): Tasks 1 + 2 + 5 + 7 (agent class + YAMLs + DB seed + roles)
2. Session B (one Backend session): Tasks 3 + 4 + 6 (skill Python files + KB content + router)

Or, if context allows, Tasks 1–7 in a single session (KB files are text-heavy but manageable).

---

## Critical Patterns to Follow (from memory.md)

- **Lazy imports:** All Ops class imports INSIDE method bodies — `from app.tools.document.pdf_ops import PDFOps`
- **Tool class names:** `PDFOps`, `DOCXOps` (uppercase acronym — NOT PdfOps, DocxOps)
- **Import paths:** `app.tools.document.*` (NOT `app.tools.doc.*`)
- **can_handle() pattern:** Check explicit routing OR keyword match (both conditions documented in legal_agent.py spec)
- **AGENT_MAP routing:** Patch at `app.api.chat` import site for tests
- **log_task_start/complete/failed:** Call from execute() — already in BaseAgent
- **LEGAL_DISCLAIMER:** Must be appended in execute() after EVERY workflow returns — never omit

---

## Quality Gate (Lead Reviews After Completion)

- [ ] `legal_agent.py` imports, class structure, LEGAL_TRIGGERS list
- [ ] `can_handle()` — both agent_override and keyword trigger paths
- [ ] `execute()` — disclaimer appended to all 5 workflow results
- [ ] All 4 YAML files parseable (correct YAML syntax)
- [ ] migrate.py seed matches agents table schema
- [ ] Router: Leo reachable via legal keyword trigger AND via Management delegate_task()
- [ ] No existing agent routing broken (additive changes only)
- [ ] Knowledge base: all 7 jurisdiction files present and structured
- [ ] No imports at module top for Ops classes (lazy import rule enforced)

---

## Additive Rule

All changes MUST be additive. Do NOT:
- Modify existing agent files
- Change existing migrate.py seed rows
- Alter existing router routing logic
- Remove or modify existing roles.yaml entries
