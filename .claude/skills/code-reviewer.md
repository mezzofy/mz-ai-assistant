# Code Reviewer

Standardized review process for Mezzofy multi-agent development. Used by Lead Agent (quality gates) and Tester Agent (code review assistance).

---

## Review Triggers

- Lead reviewing agent output at quality gates (between phases)
- Tester reviewing code during QA phase
- Any agent reviewing another agent's handoff

---

## Frontend Review Checklist

- [ ] Clean Architecture layers respected (domain → data → presentation)
- [ ] MVVM pattern: Zustand ViewModels, not component state for business logic
- [ ] Shadcn UI components used (no custom components for standard elements)
- [ ] TypeScript strict mode, no `any` types
- [ ] Mobile-first responsive design
- [ ] i18n keys for all user-facing text (EN, zh-CN, zh-TW)
- [ ] WCAG 2.1 AA accessibility (aria labels, keyboard navigation, contrast ratios)
- [ ] Portal theming applied correctly (colors, branding, layout)
- [ ] Module independence (no cross-module imports)
- [ ] Dependency flow: View → ViewModel → UseCase → Entity (inward only)
- [ ] Shared components in `src/shared/` (duplicated per module, not imported)
- [ ] Error states handled (loading, empty, error, success)
- [ ] Vite dev server on correct port (5173–5180 range)

---

## Backend Review Checklist

- [ ] CSR pattern: Controller/DTO → Service/DataModel → Repository/SchemaModel
- [ ] Co-located models (no standalone `models/` folder)
- [ ] OAuth2 authentication on all endpoints
- [ ] Input validation in controller layer (Pydantic models)
- [ ] Business logic in service layer (not in controller or repository)
- [ ] Parameterized queries (SQL injection prevention)
- [ ] Error handling with proper HTTP status codes (RFC 7807 Problem Details)
- [ ] API response < 500ms (p95)
- [ ] GraphQL schema follows Strawberry conventions
- [ ] Mangum adapter configured for Lambda deployment
- [ ] Types/interfaces exported for Frontend and Mobile consumption
- [ ] Coupon state machine transitions validated (if applicable)

---

## Mobile Review Checklist

- [ ] Clean Architecture + MVVM pattern (same as Frontend)
- [ ] Offline-first with WatermelonDB (sync strategy defined)
- [ ] NFC HMAC-SHA256 security for coupon validation
- [ ] NativeUI (nativeui.io) components used
- [ ] Biometric authentication where applicable
- [ ] Deep linking configured correctly
- [ ] Push notifications configured (@notifee/react-native)
- [ ] i18n keys for all user-facing text
- [ ] Platform-specific optimizations (iOS/Android)

---

## Infrastructure Review Checklist

- [ ] CDK stack follows Mezzofy conventions (Python or TypeScript)
- [ ] Lambda cold start < 1s (check bundle size, layers)
- [ ] CloudWatch alarms configured (5xx errors, latency, throttles)
- [ ] X-Ray tracing enabled for Lambda functions
- [ ] Cost tags applied to all resources
- [ ] Security groups properly scoped (principle of least privilege)
- [ ] API Gateway configured correctly (CORS, throttling, stages)
- [ ] Amplify Hosting configured for frontend (if applicable)
- [ ] Environment variables properly managed (no hardcoded secrets)

---

## Documentation Review Checklist

- [ ] Release notes complete (features, breaking changes, migration, rollback)
- [ ] API documentation matches implementation (OpenAPI spec)
- [ ] User guides cover all features with screenshots/examples
- [ ] All docs in 3 languages (EN, zh-CN, zh-TW) where required
- [ ] ADRs document significant architectural decisions
- [ ] File naming follows PREFIX-identifier-version.ext standard
- [ ] Cross-references between documents are valid

---

## Cross-Agent Review Points

- [ ] Shared types match between Backend exports and Frontend/Mobile imports
- [ ] API contracts match between Backend implementation and Frontend/Mobile calls
- [ ] No scope boundary violations (agents only modified their owned directories)
- [ ] Handoff documents complete and accurate
- [ ] No duplicate work between agents

---

## Review Severity Levels

| Level | Label | Action |
|-------|-------|--------|
| 🔴 | **Blocker** | Must fix before merge — architecture violations, security issues, missing tests, broken scope |
| 🟡 | **Warning** | Should fix, can discuss — performance concerns, style inconsistencies, minor gaps |
| 🟢 | **Suggestion** | Nice to have — refactoring ideas, alternative approaches, optimization opportunities |

---

## Review Output Format

```markdown
# Review: [Agent Name] — [Task Name]
**Reviewer:** Lead Agent / Tester Agent
**Date:** YYYY-MM-DD
**Verdict:** PASS / REVISE / BLOCKED

## Findings

### 🔴 Blockers
1. [file:line] — [description] — [fix required]

### 🟡 Warnings
1. [file:line] — [description] — [recommended fix]

### 🟢 Suggestions
1. [file:line] — [description] — [idea]

## Summary
[Brief overall assessment]

## Next Steps
- [ ] [Action required before proceeding]
```
