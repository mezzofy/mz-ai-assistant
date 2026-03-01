# Status: [Agent Name]

**Task:** [task name from plan]
**Date:** YYYY-MM-DD HH:MM
**Status:** [NOT STARTED | IN PROGRESS | BLOCKED | DONE]
**Session:** [N] of estimated [M]
**Context Usage:** ~[X]% at time of update

---

## Completed

- ✅ [description] → `file/path`
- ✅ [description] → `file/path`

---

## In Progress

- 🔄 [what remains — specific next step]

---

## Decisions Made This Session

- [Decision]: [Reasoning]
- [Decision]: [Reasoning]

> If any decision is architecturally significant, also add it to `.claude/coordination/memory.md`

---

## Blockers

- ⚠️ [anything blocking progress]
- Reference issue if filed: `.claude/coordination/issues/[agent].md`

---

## Files Created/Modified

- `path/to/file.tsx` (new) — [brief description]
- `path/to/file.py` (modified) — [what changed]

---

## Dependencies Created

- Exported types/interfaces at: `path/to/types.ts`
- [What other agents need from this session's output]

---

## Handoff Ready

- [ ] All files committed to feature branch
- [ ] Types/interfaces exported for downstream agents
- [ ] No TypeScript/Python errors or linting warnings
- [ ] Tests passing (>80% coverage)
- [ ] i18n keys added for all user-facing text

---

## Resume Instructions (for after /clear)

After `/clear`, load these files in order:
1. `CLAUDE.md`
2. `.claude/agents/[agent].md`
3. `.claude/skills/[primary-skill].md`
4. This status file (`.claude/coordination/status/[agent].md`)
5. `.claude/coordination/plans/[task]-plan.md`
6. `.claude/coordination/memory.md`
7. [List specific code files to re-read]

Then continue with: **[exact next action]**

---

*This status file is updated by the [Agent Name] Agent after every task or before `/clear`. The Lead Agent reads all agent status files to track progress.*
