# Handoff: [From Agent] → [To Agent]

**Date:** YYYY-MM-DD
**Task:** [task name from plan]
**Plan Reference:** `.claude/coordination/plans/[task]-plan.md`

---

## What Was Done

[Brief summary of work completed by the From Agent]

---

## Key Files

| File | Purpose | To Agent Needs |
|------|---------|---------------|
| `path/to/main/file.ts` | [description] | [what To Agent should know] |
| `path/to/types.ts` | Exported interfaces | Import these types |
| `path/to/schema.py` | DB schema | Base your models on this |

---

## Decisions Made

- **Chose X over Y** because [reason] — affects To Agent's work by [impact]
- **Used pattern Z** for [reason] — To Agent should follow the same pattern

---

## What [To Agent] Needs to Know

- [Critical info that affects downstream work]
- [Assumptions made during From Agent's work]
- [Conventions established that To Agent should follow]
- [Known limitations or edge cases discovered]

---

## API Contract (if Backend → Frontend/Mobile)

```
Endpoint: [method] [path]
Request:  [brief shape]
Response: [brief shape]
Auth:     [OAuth2 / public]
```

---

## Open Questions

- [Anything unresolved that To Agent may need to decide]
- [Design choices deferred to To Agent]

---

## Verification Checklist

- [ ] Code compiles without errors
- [ ] All tests pass
- [ ] No scope boundary violations
- [ ] Types/interfaces exported and accessible
- [ ] Changes committed to feature branch

---

*This handoff was created by [From Agent]. [To Agent] should read this file before starting their assigned tasks.*
