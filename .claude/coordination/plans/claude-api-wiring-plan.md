# Plan: Wire Claude API Native Capabilities into All Agents (v1.46.0)

**Date:** 2026-03-21
**Status:** In Progress
**Agent:** Backend Agent

---

## Context

v1.45.0 added the capability layer (new Python methods in anthropic_client.py, llm_manager.py, artifact_manager.py, anthropic_skills.py). But agents still call the OLD tool classes (PDFOps, PPTXOps, etc.) and the DB seed still lists old tool names. This plan wires everything together.

---

## Current State (Audit Findings)

### Agents still using OLD tools:
- `management_agent.py` — PDFOps (lines 150, 200)
- `hr_agent.py` — PDFOps (lines 181, 251, 311, 366)
- `marketing_agent.py` — PDFOps, PPTXOps (line 78)
- `support_agent.py` — PDFOps (lines 99, 146)
- `research_agent.py` — `web_search_20250305` (old type string, line 84)

### DB seed (admin_portal.py) still has old tool names:
- Finance: `["DatabaseOps", "PDFOps", "PPTXOps", "CSVOps"]`
- HR: `["DatabaseOps", "PDFOps", "PPTXOps", "CSVOps", "EmailOps", "TeamsOps"]`
- Sales: `["CRMOps", "LinkedInOps", "EmailOps", "PPTXOps", "PDFOps"]`
- Marketing: `["EmailOps", "WebScrapeOps", "PDFOps", "PPTXOps", "DOCXOps"]`
- Support: `["DatabaseOps", "EmailOps", "TeamsOps", "PDFOps"]`
- Legal: `["DOCXOps", "PDFOps", "EmailOps", "TeamsOps", "DatabaseOps", "WebResearch"]`
- Research: `["web_search_20250305 (native Anthropic tool)"]`

---

## Tasks

### TASK B1 — Research Agent: Upgrade to new web search tools

**File:** `server/app/agents/research_agent.py`

Change line 84:
```python
# OLD:
tools = [{"type": "web_search_20250305", "name": "web_search"}]

# NEW:
tools = [
    {"type": "web_search_20260209", "name": "web_search"},
    {"type": "web_fetch_20250124",  "name": "web_fetch"},
    {"type": "code_execution_20250825", "name": "code_execution"},
]
```

Update docstring/comments to reference new tool type strings.

---

### TASK B2 — Document Agents: Use Agent Skills instead of old Ops classes

**For each agent that calls PDFOps/PPTXOps/DOCXOps directly**, replace with `generate_document_with_skill()` from `LLMManager`.

**Pattern for replacement:**
```python
# OLD pattern:
from app.tools.document.pdf_ops import PDFOps
pdf = PDFOps(self.config)
result = pdf.generate(content, title)

# NEW pattern (additive — keep old as fallback):
try:
    from app.llm.llm_manager import get_llm_manager
    llm = get_llm_manager(db=task.get("db"), config=self.config)
    skill_result = await llm.generate_document_with_skill(
        skill_id="pdf",
        prompt=content,
        context_data=None,
        task_context=task,
    )
    if skill_result.get("success") and skill_result.get("file_ids"):
        # Download from Anthropic Files API and store locally
        from app.context.artifact_manager import download_from_anthropic
        artifact = await download_from_anthropic(
            db=task["db"],
            file_id=skill_result["file_ids"][0],
            user_id=task["user_id"],
            session_id=task["session_id"],
            skill_id="pdf",
            suggested_name=title,
        )
        return artifact
except Exception as e:
    logger.warning(f"Skill generation failed, falling back to PDFOps: {e}")
    # fallback to old path
    from app.tools.document.pdf_ops import PDFOps
    pdf = PDFOps(self.config)
    result = pdf.generate(content, title)
```

**Agents to update:**
- `management_agent.py` — PDF reports (lines 150, 200)
- `hr_agent.py` — PDF reports (lines 181, 251, 311, 366)
- `marketing_agent.py` — PDF + PPTX (line 78+)
- `support_agent.py` — PDF reports (lines 99, 146)
- `legal_agent.py` — DOCX agreements (find and update)
- `finance_agent.py` — PDF/XLSX reports (find and update)
- `sales_agent.py` — PPTX pitch decks (find and update)

---

### TASK B3 — Add Memory Tool to Management Agent

**File:** `server/app/agents/management_agent.py`

Add memory-scoped calls for KPI/preference persistence:
```python
# Use memory tool for user preferences / cached KPIs
memory_scope = f"user:{task.get('user_id')}"
result = await self.llm_manager.chat_with_memory(
    messages=messages,
    memory_scope=memory_scope,
    client_tools=existing_tools,
    system=system_prompt,
)
```

---

### TASK B4 — Update DB Seed (tools_allowed in admin_portal.py)

**File:** `server/app/api/admin_portal.py`

Update `tools_allowed` for each agent in the seed/upsert block:

| Agent | New tools_allowed |
|-------|------------------|
| Finance | `["DatabaseOps", "skill_pdf", "skill_xlsx", "CSVOps", "EmailOps", "code_execution_20250825"]` |
| HR | `["DatabaseOps", "skill_pdf", "skill_docx", "CSVOps", "EmailOps", "TeamsOps", "code_execution_20250825"]` |
| Sales | `["CRMOps", "LinkedInOps", "EmailOps", "skill_pptx", "skill_pdf", "web_fetch_20250124"]` |
| Marketing | `["EmailOps", "web_search_20260209", "web_fetch_20250124", "skill_pdf", "skill_pptx", "skill_docx"]` |
| Support | `["DatabaseOps", "EmailOps", "TeamsOps", "skill_pdf", "code_execution_20250825"]` |
| Legal | `["skill_docx", "skill_pdf", "EmailOps", "TeamsOps", "web_search_20260209", "web_fetch_20250124", "memory"]` |
| Research | `["web_search_20260209", "web_fetch_20250124", "code_execution_20250825"]` |
| Management | `["DatabaseOps", "skill_pdf", "skill_xlsx", "EmailOps", "TeamsOps", "memory", "code_execution_20250825"]` |

---

### TASK B5 — Commit

```
git add server/app/agents/ server/app/api/admin_portal.py
git commit -m "feat: Wire Claude API native tools into all agents — skill_pdf/pptx/docx/xlsx, web_search_20260209, web_fetch_20250124, code_execution_20250825, memory (v1.46.0)"
```

---

## Success Criteria

- [ ] Portal Agents page shows new tool names (after DB re-seed on EC2)
- [ ] Research Agent uses `web_search_20260209` + `web_fetch_20250124` + `code_execution_20250825`
- [ ] Document agents attempt Skill generation first, fall back to legacy Ops on failure
- [ ] Management Agent uses memory tool for user-level persistence
- [ ] Legal Agent uses Skill DOCX generation
- [ ] All agents committed at v1.46.0

---

## EC2 Deploy Steps (after commit)

```bash
cd /home/ubuntu/mz-ai-assistant && git pull
python server/scripts/migrate.py   # for new DB columns from v1.45.0
sudo systemctl restart mezzofy-api.service
```

The tools_allowed update in admin_portal.py auto-upserts on service restart (no manual SQL needed).
