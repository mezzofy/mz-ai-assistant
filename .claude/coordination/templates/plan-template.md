# Plan: [Feature/Task Name]

**Workflow:** [new-module / change-request / bug-fix]
**Date:** YYYY-MM-DD
**Created by:** Lead Agent
**Priority:** [P0 / P1 / P2 / P3]

---

## Overview

[Brief description of the feature/change/fix and its business purpose]

---

## Task Breakdown

| # | Task | Agent | Primary Skills | Scope (directories) | Depends On | Est. Sessions | Status |
|---|------|-------|---------------|---------------------|-----------|:-------------:|--------|
| 1 | [task description] | Backend | backend-developer, coupon-domain-expert | svc-*/src/ | None | 1-2 | NOT STARTED |
| 2 | [task description] | Frontend | frontend-developer, ui-ux-designer | web-*/src/ | Task 1 | 2-3 | NOT STARTED |
| 3 | [task description] | Mobile | mobile-developer | mobile-*/src/ | Task 1 | 2 | NOT STARTED |
| 4 | [task description] | Infra | infrastructure-engineer | infrastructure/ | Task 1 | 1 | NOT STARTED |
| 5 | [task description] | Tester | test-automation-engineer | tests/ | Tasks 2,3,4 | 1-2 | NOT STARTED |
| 6 | [task description] | Docs | api-documenter, technical-writer | docs/ | Tasks 1-5 | 1-2 | NOT STARTED |

> **Note:** Delete rows for agents not needed. Not every task requires all 7 agents.

---

## Parallel Opportunities

- Tasks [X, Y, Z] can run in parallel after Task [N] completes
- [Describe any other parallelization]

---

## Session Architecture

> Lead must estimate sessions upfront so agents know when to checkpoint.

| Agent | Est. Sessions | Session 1 Scope | Session 2 Scope | Session 3 Scope |
|-------|:------------:|----------------|----------------|----------------|
| Backend | 2 | Controllers + Services | Repositories + DB + tests | — |
| Frontend | 3 | Domain layer | Presentation layer | i18n + a11y + integration |
| Mobile | 2 | Screens + navigation | NFC + sync + tests | — |
| Infra | 1 | CDK stacks + deploy | — | — |
| Tester | 1-2 | Unit + integration | E2E (if needed) | — |
| Docs | 1-2 | API docs | User guides + RN | — |

---

## Quality Gates

| Gate | After Task | Lead Reviews | Criteria |
|------|-----------|-------------|----------|
| Gate 1 | Task 1 (Backend) | Schema + exported types | Types compile, CSR pattern followed |
| Gate 2 | Tasks 2-4 (FE/Mobile/Infra) | Integration points | API calls match, no scope violations |
| Gate 3 | Task 5 (Testing) | Test coverage | > 80% coverage, E2E passes |
| Gate 4 | Task 6 (Docs) | Documentation | RN complete, API docs match code |

---

## Acceptance Criteria

- [ ] [Feature-specific criterion from requirements]
- [ ] [Feature-specific criterion]
- [ ] [Feature-specific criterion]
- [ ] All required output documents generated
- [ ] Release notes created and approved (before deploy)

---

## Risk & Dependencies

| Risk | Impact | Mitigation |
|------|--------|-----------|
| [risk description] | [High/Medium/Low] | [mitigation plan] |

---

## Human Checkpoints

| # | What | Who | When |
|---|------|-----|------|
| 1 | [checkpoint] | [role] | [phase] |

---

*This plan was created by the Lead Agent. Tasks are assigned to agents via this file. Agents read their assigned rows and begin work. Status updates go to `.claude/coordination/status/[agent].md`.*
