# Plan: Legal Agent Documentation Update
**Workflow:** change-request
**Date:** 2026-03-19
**Created by:** Lead Agent
**Source:** docs/LEGAL_AGENT_PROMPT.md — add Leo (Legal Agent) to existing 3 docs

---

## Context

Leo (Legal Agent) has been specified in `docs/LEGAL_AGENT_PROMPT.md`.
Backend implementation (Phases 1–6 of that prompt) is NOT in scope here.
This plan covers ONLY updating the 3 documentation files to reflect Leo.

---

## Task Breakdown

| # | Deliverable | File | Changes |
|---|------------|------|---------|
| 1 | Features List | `docs/Mezzofy_AI_Assistant_Features_List_v2.0.md` | Add Legal Department Features section + Leo skills table + Legal Agent in Special Agents section |
| 2 | Agent Architecture | `docs/AGENTS.md` | Add Leo agent entry (10th agent), update routing flowchart note, add 4 new skills to Skills Catalogue |
| 3 | User Guide | `docs/USER_GUIDE_AGENTIC.md` | Add Leo to Your AI Team table, add "Legal Agent (Leo)" section under Triggering Special Agents |

All 3 tasks can run in ONE Docs Agent session (no dependencies between them).

---

## Detailed Change Specs

### Task 1 — Mezzofy_AI_Assistant_Features_List_v2.0.md

**Add new section: Legal Department Features** (insert after Management Department Features, before Agent Enhancement v2.0):

```
## Legal Department Features ⭐ NEW

### Document Review & Analysis
✅ Review uploaded legal documents (PDF, DOCX)
✅ Contract review: NDAs, MOUs, shareholder agreements, term sheets, employment contracts, vendor agreements
✅ Identify document type, parties, key dates, and governing law automatically
✅ Structured review: Executive Summary, Key Terms, Risk Flags, Missing Clauses, Jurisdiction Notes, Recommended Actions
✅ Generate branded PDF review report

### Contract Drafting & Generation
✅ Generate business contracts from natural language descriptions
✅ Supported types: NDA, Service Agreement, Consultancy Agreement, Employment Contract, Vendor/Supplier Agreement, MOU, Letter of Intent, IP Assignment, Distribution Agreement, Shareholders Agreement (basic), Joint Venture Agreement (basic)
✅ Output in Word (DOCX) + PDF formats
✅ Customise jurisdiction-specific clauses

### Jurisdiction Coverage
✅ Singapore (PDPA, Companies Act, Employment Act, SIAC arbitration)
✅ Hong Kong (Companies Ordinance, HKIAC arbitration)
✅ Malaysia (Companies Act 2016, PDPA MY, AIAC arbitration)
✅ UAE / Dubai (onshore, DIFC, ADGM) — DIAC, DIFC-LCIA arbitration
✅ Saudi Arabia (with Shari'ah law considerations, SCCA)
✅ Qatar (onshore + QFC) — QICCA arbitration
✅ Cayman Islands (Exempted Companies, ELP, fund structures)

### Legal Research & Advisory
✅ Jurisdiction-specific legal Q&A
✅ Compare legal frameworks across jurisdictions side-by-side
✅ Regulatory compliance checks for business activities
✅ Recommend best jurisdiction for business structures or transactions
✅ Clause extraction: extract indemnity, liability caps, termination, IP clauses etc.

### Legal Risk Assessment
✅ Legal risk matrix (Critical / High / Medium / Low severity)
✅ Jurisdiction-specific risk flags
✅ Recommended mitigations

### Important Note
⚠️ All Leo outputs include mandatory AI disclaimer: analysis is for reference only and does not constitute professional legal advice.
```

**Update Agent Enhancement v2.0 table** — change "9 agents" to "10 agents" and add Leo row.

**Update Skills Catalogue section header** — change "11 new skills" to "15 new skills" (add 4 legal skills).

**Add to Legal Agent skills table:**
| Skill | Description |
|-------|-------------|
| document_review | Extract, parse, and analyse legal documents (PDF, DOCX) |
| contract_drafting | Generate business contracts from templates and parameters |
| legal_research | Research jurisdiction-specific laws and regulations |
| jurisdiction_advisory | Jurisdiction advisory for SG, HK, MY, UAE, KSA, QA, Cayman |

---

### Task 2 — AGENTS.md

**Add Leo entry after HR Agent** (before Research Agent section):

```markdown
### Legal Agent (Special)

| Field | Value |
|-------|-------|
| **ID** | `agent_legal` |
| **Persona** | Leo |
| **Department** | `legal` |
| **Skills** | `document_review`, `contract_drafting`, `legal_research`, `jurisdiction_advisory` |
| **LLM Model** | `claude-sonnet-4-6` |
| **RAG Namespace** | `legal` |

**Role:** International business law specialist. Reviews and drafts contracts, provides jurisdiction-specific legal advisory, and flags legal risk — across Singapore, Hong Kong, Malaysia, UAE/Saudi Arabia/Qatar, and Cayman Islands.

**Trigger:** Legal keywords in message from ANY department (contract, NDA, agreement, review contract, legal advice, governing law, etc.) → `task["agent"] = "legal"`. Also delegatable from ManagementAgent via `delegate_task()`.

**Cross-departmental:** ✅ Any department can invoke Leo — legal needs arise across Sales (vendor agreements), HR (employment contracts), Finance (loan/investment agreements), Management (shareholder agreements).

**5 workflows:**
- `document_review` — extract text → classify → LLM structured analysis → branded PDF report
- `contract_generation` — extract parameters → load template → LLM draft → DOCX + PDF
- `clause_extraction` — LLM identifies and extracts named clause types as structured JSON
- `risk_assessment` — LLM risk matrix (Critical/High/Medium/Low) → formatted PDF
- `legal_advisory` — load jurisdiction knowledge → structured advisory text (no document generated)

**Mandatory disclaimer:** Every Leo output appends: "This analysis is AI-generated for informational purposes only and does not constitute professional legal advice."

**Jurisdictions covered:**
| Jurisdiction | Arbitration Body | Key Legislation |
|---|---|---|
| Singapore | SIAC | Companies Act, Employment Act, PDPA, Contract Act |
| Hong Kong | HKIAC | Companies Ordinance, Employment Ordinance, PDPO |
| Malaysia | AIAC | Companies Act 2016, Employment Act 1955, PDPA MY |
| UAE (onshore/DIFC/ADGM) | DIAC / DIFC-LCIA | Federal Companies Law, Labour Law, DIFC/ADGM Laws |
| Saudi Arabia | SCCA | Companies Law, Labor Law, PDPL (Shari'ah applies) |
| Qatar (onshore/QFC) | QICCA | Commercial Companies Law, Labour Law, QFC Laws |
| Cayman Islands | Grand Court / London | Companies Act 2023, AML Regulations |
```

**Update routing flowchart** — add `LEO[LegalAgent\ntask agent=legal]` node to the Mermaid diagram under `_detect_agent_type` with label "legal keywords".

**Update Skills Catalogue** — add 4 new rows for document_review, contract_drafting, legal_research, jurisdiction_advisory.

**Update header** — "18 skills across 9 agents" → "22 skills across 10 agents".

---

### Task 3 — USER_GUIDE_AGENTIC.md

**Add Leo row to "Your AI Team" table:**
```
| Legal Agent | Leo | (All depts) | Contract review, contract drafting, legal Q&A, jurisdiction advice |
```

**Add "Legal Agent (Leo)" section under Triggering Special Agents:**

```markdown
### Legal Agent (Leo)

**When it activates:** Your message contains words like: *contract, agreement, NDA, MOU, legal review, review this document, draft a contract, legal advice, governing law, jurisdiction, indemnity, non-compete, terms and conditions*. Or attach a legal document (PDF/DOCX) and ask Leo to review it.

**What it does:**
Analyses and drafts legal documents for international business with coverage across Singapore, Hong Kong, Malaysia, UAE, Saudi Arabia, Qatar, and Cayman Islands.

**Sample prompts:**

| What you want | What to type |
|---|---|
| Review a contract | Attach PDF/DOCX → "Review this NDA and flag any risk areas" |
| Draft an NDA | "Draft an NDA between Mezzofy Pte Ltd and XYZ Corp under Singapore law" |
| Legal Q&A | "What are the notice period requirements for employment contracts in Malaysia?" |
| Compare jurisdictions | "Compare data protection obligations in Singapore and Hong Kong for a tech company" |
| Risk assessment | "Assess the legal risks in this vendor agreement" |
| Find clauses | "Extract all indemnity and liability clauses from this contract" |

**What Leo produces:**
- Document Review: structured PDF report (Executive Summary → Key Terms → Risk Flags → Missing Clauses → Jurisdiction Notes → Recommended Actions)
- Contract Drafting: Word document (DOCX) + PDF
- Legal Advisory: written response with applicable laws cited
- Risk Assessment: risk matrix PDF

**Important:** All Leo responses include a legal disclaimer — Leo's analysis is for reference only. Consult a qualified solicitor for binding decisions.
```

---

## Source Files for Docs Agent to Read

- `docs/LEGAL_AGENT_PROMPT.md` — full Leo specification (already read by Lead)
- `docs/AGENTS.md` — current version (modify in place)
- `docs/USER_GUIDE_AGENTIC.md` — current version (modify in place)
- `docs/Mezzofy_AI_Assistant_Features_List_v2.0.md` — current version (modify in place)

---

## Quality Gate

Lead reviews all 3 updated docs for:
- [ ] Leo appears consistently in all 3 docs (same persona name, same skills, same jurisdiction list)
- [ ] 4 new skills added to AGENTS.md Skills Catalogue
- [ ] Mermaid routing flowchart updated with Leo node (or noted as text if diagram update complex)
- [ ] Legal disclaimer requirement documented in all relevant sections
- [ ] Cross-departmental nature of Leo clearly explained
- [ ] User-facing language in USER_GUIDE (non-technical, plain English)
- [ ] No cross-reference breakage

---

## Output

All 3 existing files modified in-place. No new files created.
Commit when all 3 are done.
