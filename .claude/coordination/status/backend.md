# Context Checkpoint: Backend Agent
**Date:** 2026-03-19
**Project:** mz-ai-assistant
**Session:** 26 (FEAT: Leo Legal Agent — v1.34.0)
**Context:** ~65% at checkpoint
**Reason:** All 7 tasks complete, committing and checkpointing

## Completed This Session (Session 26)

- ✅ Task 1: `server/app/agents/legal_agent.py` (NEW)
  - LegalAgent class with LEGAL_TRIGGERS, LEGAL_DISCLAIMER
  - can_handle(): checks agent_override, agent key, or keyword in message
  - execute(): classify → route → ALWAYS append LEGAL_DISCLAIMER → log
  - 5 workflow methods: contract_review, contract_drafting, legal_research, jurisdiction_advisory, compliance_review
  - All PDFOps/DOCXOps imports INSIDE method bodies (lazy pattern)

- ✅ Task 2: 4 skill YAML files in `server/app/skills/available/`
  - `document_review.yaml`
  - `contract_drafting.yaml`
  - `legal_research.yaml`
  - `jurisdiction_advisory.yaml`

- ✅ Task 3: 4 skill Python files in `server/app/skills/available/`
  - `document_review.py` — DocumentReviewSkill, lazy imports inside _extract_pdf()/_extract_docx()
  - `contract_drafting.py` — ContractDraftingSkill
  - `legal_research.py` — LegalResearchSkill
  - `jurisdiction_advisory.py` — JurisdictionAdvisorySkill

- ✅ Task 4: Knowledge base under `server/knowledge/legal/`
  - README.md
  - jurisdictions/: singapore.md, hong_kong.md, malaysia.md, uae.md, saudi_arabia.md, qatar.md, cayman_islands.md
  - templates/singapore/: nda.md, service_agreement.md, employment_contract.md, vendor_agreement.md, mou.md
  - templates/hong_kong/: nda.md, service_agreement.md, employment_contract.md
  - templates/malaysia/: nda.md, service_agreement.md
  - templates/uae/: nda.md, service_agreement.md
  - templates/cayman_islands/: shareholders_agreement.md, exempted_company_mou.md
  - templates/general/: nda.md, mou.md, loi.md
  - clause_library/: indemnity.md, liability.md, ip.md, data_protection.md, force_majeure.md, confidentiality.md, dispute_resolution.md, termination.md, governing_law.md, entire_agreement.md
  - advisory/: international_business_law.md, data_protection_comparison.md, employment_law_overview.md, ip_protection_asia.md, regulatory_compliance_overview.md

- ✅ Task 5: `server/scripts/migrate.py` — Leo DB seed appended (additive only)
  - INSERT agent_legal / Leo / legal department
  - ON CONFLICT (id) DO NOTHING — safe to re-run

- ✅ Task 6: Router integration (additive only)
  - `server/app/api/chat.py`:
    - Import LEGAL_TRIGGERS from legal_agent
    - Added _is_legal_request() function
    - Updated _detect_agent_type() to return "legal"
    - Legal detection block BEFORE _is_long_running() check
  - `server/app/agents/agent_registry.py`:
    - Import LegalAgent
    - Added "legal" and "agent_legal" keys to AGENT_MAP

- ✅ Task 7: `server/config/roles.yaml` (additive only)
  - Added legal_officer role (legal department)
  - Added legal_read to executive permissions
  - Added legal_read and legal_write to permission_tool_map

## Key Decisions
- Legal routing is synchronous (same as SchedulerAgent) — runs BEFORE _is_long_running() check
- AGENT_MAP has both "legal" (chat.py detection) and "agent_legal" (ManagementAgent delegation) keys
- LEGAL_DISCLAIMER appended to ALL content/summary fields in ALL results — no exceptions
- All PDFOps/DOCXOps imports are inside method bodies (critical lazy import pattern)

## Files Created (New)
- `server/app/agents/legal_agent.py`
- `server/app/skills/available/document_review.yaml`
- `server/app/skills/available/contract_drafting.yaml`
- `server/app/skills/available/legal_research.yaml`
- `server/app/skills/available/jurisdiction_advisory.yaml`
- `server/app/skills/available/document_review.py`
- `server/app/skills/available/contract_drafting.py`
- `server/app/skills/available/legal_research.py`
- `server/app/skills/available/jurisdiction_advisory.py`
- `server/knowledge/legal/README.md`
- `server/knowledge/legal/jurisdictions/singapore.md`
- `server/knowledge/legal/jurisdictions/hong_kong.md`
- `server/knowledge/legal/jurisdictions/malaysia.md`
- `server/knowledge/legal/jurisdictions/uae.md`
- `server/knowledge/legal/jurisdictions/saudi_arabia.md`
- `server/knowledge/legal/jurisdictions/qatar.md`
- `server/knowledge/legal/jurisdictions/cayman_islands.md`
- `server/knowledge/legal/templates/singapore/nda.md`
- `server/knowledge/legal/templates/singapore/service_agreement.md`
- `server/knowledge/legal/templates/singapore/employment_contract.md`
- `server/knowledge/legal/templates/singapore/vendor_agreement.md`
- `server/knowledge/legal/templates/singapore/mou.md`
- `server/knowledge/legal/templates/hong_kong/nda.md`
- `server/knowledge/legal/templates/hong_kong/service_agreement.md`
- `server/knowledge/legal/templates/hong_kong/employment_contract.md`
- `server/knowledge/legal/templates/malaysia/nda.md`
- `server/knowledge/legal/templates/malaysia/service_agreement.md`
- `server/knowledge/legal/templates/uae/nda.md`
- `server/knowledge/legal/templates/uae/service_agreement.md`
- `server/knowledge/legal/templates/cayman_islands/shareholders_agreement.md`
- `server/knowledge/legal/templates/cayman_islands/exempted_company_mou.md`
- `server/knowledge/legal/templates/general/nda.md`
- `server/knowledge/legal/templates/general/mou.md`
- `server/knowledge/legal/templates/general/loi.md`
- `server/knowledge/legal/clause_library/indemnity.md`
- `server/knowledge/legal/clause_library/liability.md`
- `server/knowledge/legal/clause_library/ip.md`
- `server/knowledge/legal/clause_library/data_protection.md`
- `server/knowledge/legal/clause_library/force_majeure.md`
- `server/knowledge/legal/clause_library/confidentiality.md`
- `server/knowledge/legal/clause_library/dispute_resolution.md`
- `server/knowledge/legal/clause_library/termination.md`
- `server/knowledge/legal/clause_library/governing_law.md`
- `server/knowledge/legal/clause_library/entire_agreement.md`
- `server/knowledge/legal/advisory/international_business_law.md`
- `server/knowledge/legal/advisory/data_protection_comparison.md`
- `server/knowledge/legal/advisory/employment_law_overview.md`
- `server/knowledge/legal/advisory/ip_protection_asia.md`
- `server/knowledge/legal/advisory/regulatory_compliance_overview.md`

## Files Modified (Additive)
- `server/scripts/migrate.py` — Leo DB seed appended
- `server/app/api/chat.py` — LEGAL_TRIGGERS import, _is_legal_request(), _detect_agent_type() update, legal detection block
- `server/app/agents/agent_registry.py` — LegalAgent import + AGENT_MAP entries
- `server/config/roles.yaml` — legal_officer role, legal_read on executive, permission_tool_map entries

## EC2 Action Required (after deploy)
- Run: `python scripts/migrate.py` to seed agent_legal record into agents table

## Resume Instructions
After /clear, load in order:
1. CLAUDE.md
2. .claude/agents/backend.md
3. .claude/coordination/status/backend.md
Session 26 work is COMPLETE and committed. No further backend action needed for v1.34.0.

---

# Previous Session (25): FEAT: add GET /crm/countries, POST /crm/leads, PATCH /crm/leads/{lead_id}

## Completed This Session (Session 25)
- ✅ Added `GET /crm/countries` endpoint before `GET /crm/leads` (line ~1453)
  - File: `server/app/api/admin_portal.py`
  - Returns `{"countries": [...]}` — distinct non-null locations from `sales_leads` ordered alphabetically
- ✅ Added `POST /crm/leads` endpoint after `GET /crm/leads` (line ~1557)
  - Validates `company_name` required (400 if missing)
  - Generates UUID id + utcnow() created_at
  - Defaults: `source = "manual"`, `status = "new"`
  - Returns `{"id": lead_id, "created": True}`
- ✅ Added `PATCH /crm/leads/{lead_id}` endpoint after `POST /crm/leads` (line ~1600)
  - Allowlist of 10 editable fields; 400 if no valid fields supplied
  - Dynamic SET clause; 404 if rowcount == 0
  - Returns `{"updated": True}`
- ✅ Final CRM endpoint order verified: GET /crm/countries → GET /crm/leads → POST /crm/leads → PATCH /crm/leads/{lead_id} → GET /crm/pipeline

## Previous Session (24): FEAT: add `country` filter to GET /crm/leads

## Completed This Session (Session 24)
- ✅ Added `country: Optional[str] = Query(None)` parameter to `get_crm_leads` (line 1460)
  - File: `server/app/api/admin_portal.py`
  - Added after `assigned_to` param, before `current_user`
- ✅ Added `country` filter block in filter logic (lines 1478–1480)
  - `sl.location ILIKE :country` with `%{country}%` for case-insensitive partial match
  - Matches location/country text such as "Singapore", "Malaysia", etc.

## Previous Session (23): BUG-fix: get_crm_leads LEFT JOIN UUID type mismatch
- ✅ BUG fix: `server/app/api/admin_portal.py` line 1489
  - Changed `LEFT JOIN users u ON u.id::text = sl.assigned_to` → `LEFT JOIN users u ON u.id = sl.assigned_to`
  - Root cause: unnecessary `::text` cast caused PostgreSQL "operator does not exist: text = uuid" error
  - Both `users.id` and `sales_leads.assigned_to` are UUID — direct UUID = UUID comparison is correct
