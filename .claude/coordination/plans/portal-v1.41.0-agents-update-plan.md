# Plan: Mission Control Portal v1.41.0 — Agentic Agents + Leo (Legal) Update
**Workflow:** change-request
**Date:** 2026-03-19
**Created by:** Lead Agent
**Branch:** eric-design

---

## Context

The portal's Agent Registry and Office canvas were built in v1.33.0 with a simplified hardcoded `AGENT_REGISTRY` (9 agents, basic skills only). Since then:
- **Agent Enhancement v2.0 (v1.33–v1.34):** 9 agents now have personas, full skills, tools_allowed, llm_model, is_orchestrator — documented in `docs/AGENTS.md`
- **Leo (Legal Agent) added (2026-03-19):** 10th agent documented in `docs/AGENTS.md`; backend NOT yet implemented

This change-request updates the portal to reflect the full AGENTS.md spec:
1. **Backend:** Update `AGENT_REGISTRY` in `admin_portal.py` — add Leo + all agentic metadata fields
2. **Frontend:** AgentOffice canvas (add Leo sprite), AgentsPage cards (persona, tools, LLM, type), types (extend Agent interface)

**Source of truth:** `docs/AGENTS.md` v2.0

---

## Agent Data (from docs/AGENTS.md)

| Agent | Persona | Dept | Skills | Tools | Orchestrator | Type |
|-------|---------|------|--------|-------|:------------:|------|
| Management | Max | management | data_analysis, web_research | DatabaseOps, PDFOps, PPTXOps, CSVOps, EmailOps, TeamsOps | ✅ | Dept |
| Finance | Fiona | finance | financial_reporting, data_analysis | DatabaseOps, PDFOps, PPTXOps, CSVOps | ❌ | Dept |
| Sales | Sam | sales | linkedin_prospecting, email_outreach, pitch_deck_generation, web_research | CRMOps, LinkedInOps, EmailOps, PPTXOps, PDFOps | ❌ | Dept |
| Marketing | Maya | marketing | content_generation, web_research | EmailOps, WebScrapeOps, PDFOps, PPTXOps, DOCXOps | ❌ | Dept |
| Support | Suki | support | data_analysis, email_outreach | DatabaseOps, EmailOps, TeamsOps, PDFOps | ❌ | Dept |
| HR | Hana | hr | data_analysis, email_outreach | DatabaseOps, EmailOps, CSVOps | ❌ | Dept |
| Legal | Leo | legal | document_review, contract_drafting, legal_research, jurisdiction_advisory | DOCXOps, PDFOps, EmailOps, TeamsOps, DatabaseOps, WebResearch | ❌ | Special |
| Research | Rex | research | web_research, data_analysis, deep_research, source_verification | web_search (native Anthropic tool) | ❌ | Special |
| Developer | Dev | developer | code_generation, code_review, code_execution, api_integration, test_generation | Claude Code CLI subprocess | ❌ | Special |
| Scheduler | Sched | scheduler | schedule_management, cron_validation, job_monitoring, beat_sync | SchedulerOps (create/list/delete/run_now) | ❌ | Special |

---

## Task Breakdown

| # | Task | Agent | File(s) | Depends On | Est. Context | Status |
|---|------|-------|---------|-----------|:------------:|--------|
| 1 | Update AGENT_REGISTRY (all 10 agents) | Backend | `server/app/api/admin_portal.py` | — | ~10% | NOT STARTED |
| 2 | Extend Agent TypeScript type | Frontend | `portal/src/types/index.ts` | — | ~2% | NOT STARTED |
| 3 | Add Leo to AgentOffice canvas | Frontend | `portal/src/components/AgentOffice.tsx` | — | ~10% | NOT STARTED |
| 4 | Enhanced agent cards (persona, tools, LLM) | Frontend | `portal/src/pages/AgentsPage.tsx` | Task 2 | ~15% | NOT STARTED |
| 5 | Commit + deploy to EC2 | Deploy | — | 1–4 | — | NOT STARTED |

**Tasks 1, 2, 3 can run in parallel. Task 4 depends on Task 2. Backend (Task 1) and Frontend (Tasks 2–4) are independent.**

---

## Backend Implementation (Task 1)

**File:** `server/app/api/admin_portal.py`

Replace the hardcoded `AGENT_REGISTRY` list (lines ~459–469) with the full 10-agent registry including persona, llm_model, is_orchestrator, tools_allowed, and accurate skills from AGENTS.md:

```python
AGENT_REGISTRY = [
    {
        "name": "Management Agent", "persona": "Max", "department": "management",
        "description": "Cross-department KPI aggregator and orchestrator. Decomposes multi-department tasks and delegates to specialist agents.",
        "skills": ["data_analysis", "web_research"],
        "tools_allowed": ["DatabaseOps", "PDFOps", "PPTXOps", "CSVOps", "EmailOps", "TeamsOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": True,
    },
    {
        "name": "Finance Agent", "persona": "Fiona", "department": "finance",
        "description": "Financial analysis, KPI reports, revenue metrics, and department-scoped data access.",
        "skills": ["financial_reporting", "data_analysis"],
        "tools_allowed": ["DatabaseOps", "PDFOps", "PPTXOps", "CSVOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Sales Agent", "persona": "Sam", "department": "sales",
        "description": "CRM lead management, LinkedIn prospecting, sales email outreach, and pitch deck generation.",
        "skills": ["linkedin_prospecting", "email_outreach", "pitch_deck_generation", "web_research"],
        "tools_allowed": ["CRMOps", "LinkedInOps", "EmailOps", "PPTXOps", "PDFOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Marketing Agent", "persona": "Maya", "department": "marketing",
        "description": "Marketing content creation, campaign email delivery, and competitive web research.",
        "skills": ["content_generation", "web_research"],
        "tools_allowed": ["EmailOps", "WebScrapeOps", "PDFOps", "PPTXOps", "DOCXOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Support Agent", "persona": "Suki", "department": "support",
        "description": "Support ticket management, SLA reporting, and customer communications.",
        "skills": ["data_analysis", "email_outreach"],
        "tools_allowed": ["DatabaseOps", "EmailOps", "TeamsOps", "PDFOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "HR Agent", "persona": "Hana", "department": "hr",
        "description": "HR data analytics, leave management, and employee communications.",
        "skills": ["data_analysis", "email_outreach"],
        "tools_allowed": ["DatabaseOps", "EmailOps", "CSVOps"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Legal Agent", "persona": "Leo", "department": "legal",
        "description": "International business law specialist — contract review and drafting for SG, HK, MY, UAE, KSA, QA, and Cayman Islands.",
        "skills": ["document_review", "contract_drafting", "legal_research", "jurisdiction_advisory"],
        "tools_allowed": ["DOCXOps", "PDFOps", "EmailOps", "TeamsOps", "DatabaseOps", "WebResearch"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Research Agent", "persona": "Rex", "department": "research",
        "description": "Agentic web-research specialist. Multi-iteration search loop using Claude native web_search tool.",
        "skills": ["web_research", "data_analysis", "deep_research", "source_verification"],
        "tools_allowed": ["web_search_20250305 (native Anthropic tool)"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Developer Agent", "persona": "Dev", "department": "developer",
        "description": "Runs Claude Code CLI as a headless subprocess for code generation, review, and execution tasks.",
        "skills": ["code_generation", "code_review", "code_execution", "api_integration", "test_generation"],
        "tools_allowed": ["Claude Code CLI (stream-JSON subprocess)"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
    {
        "name": "Scheduler Agent", "persona": "Sched", "department": "scheduler",
        "description": "Chat-based scheduled job manager. Accepts natural language and translates to UTC cron expressions.",
        "skills": ["schedule_management", "cron_validation", "job_monitoring", "beat_sync"],
        "tools_allowed": ["SchedulerOps (create_job, list_jobs, delete_job, run_now)"],
        "llm_model": "claude-sonnet-4-6", "is_orchestrator": False,
    },
]
```

**Note:** This is a REPLACE of the AGENT_REGISTRY constant only. The `list_agents()` function below it uses `**agent` spread — all new fields are automatically included in the response. No changes to the endpoint function signature or logic.

---

## Frontend Implementation (Tasks 2–4)

### Task 2 — `portal/src/types/index.ts`

Extend the `Agent` interface:

```typescript
export interface Agent {
  name: string
  department: string
  persona?: string
  description?: string
  skills: string[]
  tools_allowed?: string[]
  llm_model?: string
  is_orchestrator?: boolean
  is_busy: boolean
  tasks_today: number
  rag_memory_count: number
}
```

---

### Task 3 — `portal/src/components/AgentOffice.tsx`

**Add Leo to AGENT_POSITIONS:**
```typescript
const AGENT_POSITIONS: Record<string, { x: number; y: number }> = {
  management: { x: 400, y: 60 },
  finance:    { x: 90,  y: 190 },
  sales:      { x: 210, y: 270 },
  hr:         { x: 330, y: 330 },
  marketing:  { x: 470, y: 330 },
  support:    { x: 590, y: 270 },
  legal:      { x: 550, y: 190 },   // ← NEW: middle row, between management and research
  research:   { x: 710, y: 190 },
  developer:  { x: 670, y: 330 },
  scheduler:  { x: 130, y: 320 },
}
```

**Add Leo to DEPT_COLORS:**
```typescript
const DEPT_COLORS: Record<string, string> = {
  finance:    '#FFB84D',
  sales:      '#00D4AA',
  marketing:  '#C77DFF',
  support:    '#4DA6FF',
  management: '#FF6B8A',
  hr:         '#DB2777',
  legal:      '#F59E0B',   // ← NEW: amber/gold (scales of justice)
  research:   '#4DA6FF',
  developer:  '#00D4AA',
  scheduler:  '#FFB84D',
}
```

**Add Leo to bodyColors inside drawSprite():**
```typescript
const bodyColors: Record<string, string> = {
  management: '#2D1B69',
  finance:    '#064E3B',
  sales:      '#1E3A5F',
  marketing:  '#78350F',
  support:    '#164E63',
  hr:         '#4C1D95',
  legal:      '#3B1A00',   // ← NEW: dark mahogany (law firm paneling)
  research:   '#1E3A5F',
  developer:  '#064E3B',
  scheduler:  '#78350F',
}
```

**Add legal branch in drawSprite() — scales of justice accessory:**

Add after the `scheduler` branch in the existing `if/else if` chain:

```typescript
} else if (dept === 'legal') {
  // Scales of justice: horizontal beam + two hanging pans
  ctx.fillStyle = '#F59E0B'
  // Beam (horizontal bar)
  ctx.fillRect(x - 7 * scale, cy - 8 * scale, 14 * scale, 2 * scale)
  // Center post (vertical)
  ctx.fillRect(x - 1 * scale, cy - 8 * scale, 2 * scale, 4 * scale)
  // Left pan
  ctx.fillRect(x - 9 * scale, cy - 5 * scale, 5 * scale, 2 * scale)
  // Right pan
  ctx.fillRect(x + 4 * scale, cy - 5 * scale, 5 * scale, 2 * scale)
  // Left chain
  ctx.fillRect(x - 7 * scale, cy - 8 * scale, 1 * scale, 3 * scale)
  // Right chain
  ctx.fillRect(x + 6 * scale, cy - 8 * scale, 1 * scale, 3 * scale)
}
```

The `ALL_DEPTS = Object.keys(AGENT_POSITIONS)` line is already dynamic — Leo is automatically included once added to AGENT_POSITIONS.

---

### Task 4 — `portal/src/pages/AgentsPage.tsx`

Replace the current simple card layout with an enhanced version that shows persona, description, type badge, LLM model, and tools_allowed:

**Key UI additions per agent card:**

1. **Header row:** Show persona name as subtitle below agent name. Add agent type badge:
   - `is_orchestrator === true` → `"ORCHESTRATOR"` badge (purple `#6C63FF`)
   - `['research', 'developer', 'scheduler', 'legal'].includes(dept)` → `"SPECIAL"` badge (teal `#00D4AA`)
   - Otherwise → `"DEPT"` badge (gray `#374151`)

2. **Description:** Show `agent.description` as a muted paragraph below header (2-line clamp)

3. **Skills section:** Label "Skills" (existing, keep as is)

4. **Tools section:** Show `agent.tools_allowed` as gray tags — same pill style as skills, but label "Tools". If empty or undefined, omit section.

5. **Footer row:** Show `agent.llm_model` as a small monospace badge alongside existing tasks-today count

**Complete card structure (replace current card JSX):**

```tsx
<div
  key={agent.department}
  className="rounded-xl border p-5 flex flex-col gap-3"
  style={{ background: '#111827', borderColor: '#1E2A3A' }}
>
  {/* Header */}
  <div className="flex items-start justify-between">
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ background: agent.is_busy ? '#00D4AA' : '#374151' }} />
        <h3 className="text-sm font-semibold text-white">{agent.name}</h3>
        {agent.is_orchestrator && (
          <span className="px-1.5 py-0.5 rounded text-xs font-bold"
            style={{ background: 'rgba(108,99,255,0.15)', color: '#6C63FF', border: '1px solid rgba(108,99,255,0.3)' }}>
            ORCHESTRATOR
          </span>
        )}
        {!agent.is_orchestrator && ['research','developer','scheduler','legal'].includes(agent.department) && (
          <span className="px-1.5 py-0.5 rounded text-xs font-bold"
            style={{ background: 'rgba(0,212,170,0.1)', color: '#00D4AA', border: '1px solid rgba(0,212,170,0.2)' }}>
            SPECIAL
          </span>
        )}
      </div>
      {agent.persona && (
        <div className="text-xs mt-0.5" style={{ color: '#f97316' }}>
          {agent.persona} · {agent.department}
        </div>
      )}
    </div>
    <div className="text-right ml-2 flex-shrink-0">
      <div className="text-lg font-bold" style={{ color: '#f97316' }}>{agent.tasks_today}</div>
      <div className="text-xs" style={{ color: '#6B7280' }}>today</div>
    </div>
  </div>

  {/* Description */}
  {agent.description && (
    <p className="text-xs leading-relaxed line-clamp-2" style={{ color: '#9CA3AF' }}>
      {agent.description}
    </p>
  )}

  {/* Skills */}
  {agent.skills.length > 0 && (
    <div>
      <div className="text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Skills</div>
      <div className="flex flex-wrap gap-1">
        {agent.skills.map((skill) => (
          <span key={skill} className="px-2 py-0.5 rounded text-xs"
            style={{ background: '#1E2A3A', color: '#9CA3AF' }}>
            {skill}
          </span>
        ))}
      </div>
    </div>
  )}

  {/* Tools */}
  {agent.tools_allowed && agent.tools_allowed.length > 0 && (
    <div>
      <div className="text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Tools</div>
      <div className="flex flex-wrap gap-1">
        {agent.tools_allowed.map((tool) => (
          <span key={tool} className="px-2 py-0.5 rounded text-xs"
            style={{ background: 'rgba(249,115,22,0.08)', color: '#f97316', border: '1px solid rgba(249,115,22,0.15)' }}>
            {tool}
          </span>
        ))}
      </div>
    </div>
  )}

  {/* LLM model + Memory toggle */}
  <div className="flex items-center justify-between border-t pt-2" style={{ borderColor: '#1E2A3A' }}>
    {agent.llm_model && (
      <span className="text-xs font-mono" style={{ color: '#6B7280' }}>
        {agent.llm_model}
      </span>
    )}
    <button
      onClick={() => loadMemory(agent.department)}
      className="flex items-center gap-1 text-xs transition-colors hover:text-orange-400 ml-auto"
      style={{ color: '#6B7280' }}
    >
      <span>Memory ({agent.rag_memory_count})</span>
      <span>{expandedAgent === agent.department ? '▲' : '▼'}</span>
    </button>
  </div>

  {/* Memory files (expanded) */}
  {expandedAgent === agent.department && (
    <div className="space-y-1 max-h-40 overflow-y-auto">
      {/* Upload button — keep existing logic */}
      <div className="flex items-center gap-2 mb-2">
        <input
          type="file"
          ref={(el) => { fileInputRefs.current[agent.department] = el }}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleUpload(agent.department, file)
            e.target.value = ''
          }}
        />
        <button
          onClick={() => fileInputRefs.current[agent.department]?.click()}
          disabled={uploadingFor === agent.department}
          className="px-2 py-1 rounded text-xs transition-colors"
          style={{ background: '#1E2A3A', color: '#f97316' }}
        >
          {uploadingFor === agent.department ? 'Uploading...' : '+ Upload Memory'}
        </button>
      </div>
      {(memoryData[agent.department] || []).length > 0 ? (
        memoryData[agent.department].map((f) => (
          <div key={f.filename} className="flex items-center justify-between text-xs py-1">
            <span className="text-gray-300 truncate flex-1">{f.filename}</span>
            <span className="mx-2" style={{ color: '#6B7280' }}>
              {(f.size_bytes / 1024).toFixed(1)}KB
            </span>
            <button
              onClick={() => handleDeleteMemory(agent.department, f.filename)}
              className="text-red-400 hover:text-red-300 px-1"
              title="Delete"
            >
              ×
            </button>
          </div>
        ))
      ) : (
        <p className="text-xs py-2" style={{ color: '#6B7280' }}>No knowledge files</p>
      )}
    </div>
  )}
</div>
```

---

## Deployment Steps (Task 5)

```bash
# Local
git add server/app/api/admin_portal.py
git add portal/src/types/index.ts
git add portal/src/components/AgentOffice.tsx
git add portal/src/pages/AgentsPage.tsx
git commit -m "feat(portal): v1.41.0 — Add Leo (Legal Agent) + agentic agent metadata"

# EC2
git pull
sudo systemctl restart mezzofy-api.service
cd portal && npm install && npm run build
```

---

## Verification Checklist

1. **AgentOffice canvas** — Leo (Legal) sprite visible at position (550, 190) — between management top and research right
2. **Leo sprite** — Amber/gold scales of justice accessory; dark mahogany body
3. **Agents page — 10 agents** — All 10 agent cards appear (Legal card included when Leo is seeded in DB)
4. **Agent cards — persona** — Shows "Max · management", "Leo · legal", etc.
5. **Agent cards — type badge** — Management shows "ORCHESTRATOR" badge; Research/Developer/Scheduler/Legal show "SPECIAL" badge
6. **Agent cards — description** — 2-line description visible below persona
7. **Agent cards — skills** — Accurate skills matching AGENTS.md (not old simplified labels)
8. **Agent cards — tools** — Tools section shows with orange-tint pills
9. **Agent cards — LLM** — "claude-sonnet-4-6" shown in footer
10. **Memory upload/delete** — Still functional (no regression)
11. **Dashboard AgentOffice** — 10 agent sprites visible; Leo is idle (no tasks) until backend is seeded

---

## Notes

- **Leo backend NOT yet implemented** — `legal-agent-backend-plan.md` covers that separately. This portal update prepares the UI to display Leo once the backend is ready.
- **AGENT_REGISTRY in admin_portal.py is hardcoded** — it does NOT read from the PostgreSQL `agents` table. The `**agent` spread in `list_agents()` means all new fields (persona, description, tools_allowed, llm_model, is_orchestrator) are automatically included in API responses.
- **Leo will show in AgentOffice canvas** immediately (hardcoded position), but will be **idle** (no tasks, no skills shown) until Leo is seeded in the `agents` DB table and the Leo backend is implemented.
- **Legal card in AgentsPage** will appear only after Leo is in `AGENT_REGISTRY` (which this plan does) — but the card's skills/tools/description come from the registry data, so they'll show immediately.

---

## Delegation

**Backend Agent (Session 1):** Task 1 — Replace `AGENT_REGISTRY` in `admin_portal.py`

**Frontend Agent (Session 1):** Tasks 2, 3, 4 — types/index.ts + AgentOffice.tsx + AgentsPage.tsx

**Both can run in parallel.** Backend and Frontend are fully independent for this change.

After both complete → commit → deploy (Task 5).
