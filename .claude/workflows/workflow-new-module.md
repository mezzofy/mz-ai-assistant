---
name: workflow-new-module
description: New module development workflow specialist for Mezzofy's 7-phase development process. Use for building completely new features, portals, or integrations from scratch. Guides teams through requirements gathering, UI/UX validation, technical design, development, QA, production release, and post-launch monitoring with proper quality gates and AI assistance at each phase.
---

# Workflow: New Module Development

Guide teams through Mezzofy's structured 7-phase development process with proper gates and AI integration.

## Overview

This workflow ensures **module-by-module delivery** with clear ownership, quality gates, and appropriate AI assistance at each phase.

**Key Principles:**
- ❌ No phase skipping without approval
- ✅ Each phase has clear outputs and sign-offs
- 🤖 AI assists but humans decide
- 📋 Documentation is mandatory, not optional

## Phase 1: Requirements & Scope Lock

**Owner:** Product  
**Contributors:** Support, Engineering  
**Duration:** 1-2 weeks per module

### Objectives

Define **complete and unambiguous** requirements for a single module before any design or development begins.

### Activities

#### 1.1 Gather Requirements by Module

```markdown
## Module: [Module Name]

### Purpose
What problem does this solve?

### Scope
**In Scope:**
- Feature A
- Feature B
- Integration with X

**Out of Scope:**
- Feature C (deferred to Phase 2)
- Complex edge case D (requires research)

### User Stories
As a [role], I want [capability] so that [benefit].

Examples:
- As a B2B admin, I want to bulk upload coupons via CSV so that I can onboard 1000+ coupons quickly
- As a merchant, I want to set expiration dates so that coupons automatically expire
```

#### 1.2 Define Fields & Data Model

```yaml
Field Specifications:
  coupon_title:
    type: string
    min_length: 3
    max_length: 100
    mandatory: true
    validation: alphanumeric + spaces
    example: "50% Off Italian Restaurant"
  
  discount:
    type: number
    min: 0
    max: 100 (for percentage), 10000 (for fixed)
    mandatory: true
    validation: positive number
    example: 50
  
  discount_type:
    type: enum
    values: [percentage, fixed, bogo, shipping]
    mandatory: true
    default: percentage
```

#### 1.3 Define Business Logic

```markdown
## Business Rules

### Validation Rules
1. Discount percentage cannot exceed 100%
2. Expiration date must be at least 1 hour in future
3. Max uses must be ≥ 1 if specified

### State Transitions
DRAFT → ACTIVE (merchant publishes)
ACTIVE → REDEEMED (user redeems)
ACTIVE → EXPIRED (time-based)
ACTIVE → SUSPENDED (admin action)

### Permissions
- Merchants: Create, Edit (own), Delete (own)
- Admins: Create, Edit (all), Delete (all), Suspend
- Users: View, Redeem
```

#### 1.4 Identify Edge Cases

**Work with Support team:**
- What do users struggle with?
- What support tickets exist for similar features?
- What misuse scenarios have occurred?

```markdown
## Edge Cases

1. **Expired on redemption attempt**
   - Scenario: User clicks redeem, but coupon expires mid-flow
   - Solution: Lock coupon for 5 minutes on redemption start

2. **Concurrent redemption**
   - Scenario: 2 users redeem last coupon simultaneously
   - Solution: Database-level locking with max_uses check

3. **Invalid NFC signature**
   - Scenario: Tampered NFC tag with modified discount
   - Solution: HMAC signature verification, reject invalid
```

#### 1.5 Define Acceptance Criteria

```markdown
## Acceptance Criteria

### Functional
- [ ] User can create coupon with all required fields
- [ ] Validation errors display clearly for invalid input
- [ ] Coupon status transitions work correctly
- [ ] Permission checks enforce role-based access

### Non-Functional
- [ ] Page load < 2 seconds
- [ ] API response < 500ms (p95)
- [ ] Mobile-responsive on all breakpoints
- [ ] WCAG 2.1 AA accessibility compliance

### Edge Cases
- [ ] Expired coupon cannot be redeemed
- [ ] Usage limit prevents over-redemption
- [ ] Invalid NFC signature is rejected
```

### Claude Code Usage (Phase 1)

✅ **Generate:**
- Field validation logic templates
- Sample data structures
- Edge case test scenarios

❌ **Do NOT:**
- Make final decisions on business rules
- Prioritize requirements
- Approve scope without Product sign-off

**Example Prompt:**
```
"workflow-new-module, help me create requirement specification for bulk coupon upload module.

Module details:
- Merchants need to upload 1000+ coupons via CSV
- Support fields: title, discount, expiration, merchant_id
- Must validate all rows before commit
- Must show progress during upload

Generate:
1. Complete field specifications
2. Validation rules
3. Edge cases to consider
4. Acceptance criteria"
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Create Module Folder** (in repo)
   ```
   /documents/modules/bulk-coupon-upload/
   ├── requirements-v1.0.md
   ├── edge-cases.md
   └── acceptance-criteria.md
   ```

2. **Approved Requirement Specification** (AI-assisted)
   - Versioned (v1.0, v1.1, etc.)
   - Signed off by Product, Engineering, Support

3. **Updated Project Plan** (AI-assisted)
   - Timeline estimates
   - Resource allocation
   - Dependencies identified

❌ **Quality Gate:**
**STOP: No Phase 2 work without signed-off requirements**

---

## Phase 2: UI/UX Validation

**Owner:** Product  
**Contributors:** Support, Design  
**Duration:** 1 week per module

### Objectives

Validate user flows, states, and interactions **before writing code**.

### Activities

#### 2.1 Generate UI Drafts

Use Claude + ui-ux-designer skill:

```
"ui-ux-designer, create wireframes for bulk coupon upload flow.

Requirements:
- File upload (drag & drop + click)
- Validation feedback (row-by-row errors)
- Progress indicator
- Success/failure summary

Include:
- Empty state (no file selected)
- Loading state (parsing CSV)
- Error state (validation failures)
- Success state (upload complete)"
```

#### 2.2 Review Flows with Support

**Questions to ask Support:**
- Is the error messaging clear enough?
- Will users understand what went wrong?
- Are the steps intuitive?
- What have users struggled with in similar features?

#### 2.3 Validate States

```markdown
## UI States Checklist

### Empty States
- [ ] No coupons uploaded yet
- [ ] Search returns zero results
- [ ] Filter has no matches

### Loading States
- [ ] File parsing in progress
- [ ] API call pending
- [ ] Background job running

### Error States
- [ ] Validation failure (which field, which row)
- [ ] Network error (retry option)
- [ ] Permission denied (clear explanation)
- [ ] Server error (contact support)

### Success States
- [ ] Upload complete (count, summary)
- [ ] Action confirmed (visual feedback)
- [ ] Background job started (track progress)

### Misuse Scenarios
- [ ] File too large (>10MB rejected)
- [ ] Wrong format (only CSV accepted)
- [ ] Empty file (show helpful message)
- [ ] Duplicate entries (flag conflicts)
```

#### 2.4 Build Reusable Templates

Identify patterns for future modules:
- File upload component
- Progress indicator
- Error display component
- Success confirmation

Use `template-architect` skill to extract templates.

### Claude Code Usage (Phase 2)

✅ **Generate:**
- UI component structures
- State management boilerplate
- Accessibility attributes
- Responsive layout templates

❌ **Do NOT:**
- Make design decisions without Product approval
- Skip state validations
- Proceed without Support review

### Outputs & Gates

✅ **Required Deliverables:**

1. **Approved UI Flow & States**
   ```
   /documents/modules/bulk-coupon-upload/
   ├── wireframes/
   │   ├── upload-empty.png
   │   ├── upload-progress.png
   │   ├── upload-error.png
   │   └── upload-success.png
   └── ui-flow-v1.0.md
   ```

2. **Updated Requirement Specification** (versioned v1.1)
   - UI details added
   - States documented

3. **Exported Templates** (AI-assisted)
   ```
   /templates/shared/composite/FileUpload/
   /templates/shared/composite/ProgressIndicator/
   ```

❌ **Quality Gate:**
**STOP: No Phase 3 without UI approval from Product + Support**

---

## Phase 3: Technical Design

**Owner:** Engineering  
**Contributors:** Product (for clarifications)  
**Duration:** 3-5 days per module

### Objectives

Define **how** the system will be built before writing code.

### Activities

#### 3.1 Architecture Design

```markdown
## Architecture: Bulk Coupon Upload

### Components
1. **Frontend**: File upload component + validation display
2. **API**: POST /api/v2/coupons/bulk
3. **Background Worker**: Async CSV processing
4. **Database**: Coupons table + bulk_uploads audit table

### Data Flow
User → Frontend → API → Queue → Worker → Database
                    ↓
              Validation → Error response
```

#### 3.2 API Contracts

```yaml
# POST /api/v2/coupons/bulk

Request:
  Content-Type: multipart/form-data
  Body:
    file: coupons.csv (max 10MB)
    merchant_id: uuid

Response (202 Accepted):
  {
    "upload_id": "uuid",
    "status": "processing",
    "total_rows": 1500,
    "estimated_time": "2 minutes"
  }

# GET /api/v2/coupons/bulk/{upload_id}

Response (200 OK):
  {
    "upload_id": "uuid",
    "status": "completed",
    "total_rows": 1500,
    "success_count": 1480,
    "error_count": 20,
    "errors": [
      {
        "row": 5,
        "field": "discount",
        "message": "Must be between 0 and 100"
      }
    ]
  }

Error Responses:
  400: Invalid file format
  413: File too large
  422: Validation errors
```

#### 3.3 Database Schema

```sql
-- New table for tracking bulk uploads
CREATE TABLE bulk_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES merchants(id),
    filename VARCHAR(255) NOT NULL,
    total_rows INTEGER NOT NULL,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'processing',
    error_details JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    CONSTRAINT valid_status CHECK (status IN ('processing', 'completed', 'failed'))
);

CREATE INDEX idx_bulk_uploads_merchant ON bulk_uploads(merchant_id);
CREATE INDEX idx_bulk_uploads_status ON bulk_uploads(status);

-- Update coupons table
ALTER TABLE coupons ADD COLUMN bulk_upload_id UUID REFERENCES bulk_uploads(id);
```

#### 3.4 Security Baseline

```markdown
## Security Checklist

- [ ] Authentication: JWT token required
- [ ] Authorization: Merchant can only upload to own account
- [ ] Input validation: CSV structure validated
- [ ] File scanning: Virus scan on upload
- [ ] Rate limiting: Max 5 uploads per hour per merchant
- [ ] Data sanitization: All fields escaped before DB insert
- [ ] Audit logging: All uploads logged to DynamoDB
- [ ] CORS: Only allow from mezzofy.com domains
```

#### 3.5 Effort Estimation

```markdown
## Effort Estimate

### Frontend (2 days)
- File upload component: 4 hours
- Progress tracking UI: 4 hours
- Error display: 2 hours
- Integration testing: 2 hours

### Backend (3 days)
- API endpoint: 4 hours
- CSV parser: 4 hours
- Background worker: 8 hours
- Database migrations: 2 hours
- Unit tests: 4 hours

### Total: 5 days (1 engineer)
```

### Claude Code Usage (Phase 3)

✅ **Generate:**
- API endpoint boilerplate
- Database migration scripts
- Schema definitions
- Architecture diagrams (Mermaid)

❌ **Do NOT:**
- Make architecture decisions without review
- Commit to timelines without feasibility check
- Skip security considerations

**Example Prompt:**
```
"backend-developer, create API specification for bulk coupon upload.

Requirements:
- Async processing (background worker)
- CSV validation before commit
- Track progress per upload
- Return detailed error report

Generate:
1. OpenAPI specification
2. Database schema
3. Background worker pseudocode"
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Architecture Document** (AI-assisted + Manual review)
   ```
   /documents/modules/bulk-coupon-upload/
   └── architecture-v1.0.md
       ├── Component diagram
       ├── Data flow
       ├── Security baseline
       └── Effort estimate
   ```

2. **API Specification** (OpenAPI 3.1)
   ```
   /documents/modules/bulk-coupon-upload/
   └── api-spec-v1.0.yaml
   ```

3. **Database Schema** (SQL + ER Diagram)
   ```
   /documents/modules/bulk-coupon-upload/
   └── schema-v1.0.sql
   ```

❌ **Quality Gate:**
**STOP: No coding until architecture approved by Engineering Lead**

---

## Phase 4: Development (Iterative)

**Owner:** Engineering  
**Duration:** 1-2 weeks per module

### Module-by-Module Development Order

For each module, complete in this sequence:

1. **Frontend UI** → 2. **Backend Logic & APIs** → 3. **Validation & Permissions** → 4. **Tests** → 5. **Internal Demo**

### 4.1 Frontend UI

```bash
# Use frontend-developer skill
"frontend-developer, implement file upload component with:
- Drag & drop support
- CSV validation (client-side preview)
- Progress indicator
- Error display with row numbers
- Retry capability"
```

**Checklist:**
- [ ] Component follows Clean Architecture (domain/data/presentation)
- [ ] MVVM pattern with Zustand ViewModels
- [ ] Shadcn UI components used
- [ ] Mobile-responsive (tested on 3 breakpoints)
- [ ] Accessibility (keyboard navigation, ARIA labels)
- [ ] i18n ready (EN, zh-CN, zh-TW)

### 4.2 Backend Logic & APIs

```bash
# Use backend-developer skill
"backend-developer, implement bulk coupon upload API with:
- Multipart file upload
- CSV parsing and validation
- Background job for processing
- Progress tracking
- Detailed error reporting"
```

**Checklist:**
- [ ] CSR pattern followed (Controller → Service → Repository)
- [ ] Three-model pattern (DTO, DataModel, SchemaModel)
- [ ] OAuth2 authentication enforced
- [ ] Rate limiting applied
- [ ] Error handling comprehensive
- [ ] Logging to DynamoDB

### 4.3 Validation & Permissions

```python
# Business validation in service layer
class BulkUploadService:
    def validate_upload(self, file, merchant_id):
        # Check file size
        if file.size > 10 * 1024 * 1024:  # 10MB
            raise ValidationError("File too large")
        
        # Check format
        if not file.name.endswith('.csv'):
            raise ValidationError("Only CSV files allowed")
        
        # Check permission
        if not user_can_upload(merchant_id):
            raise PermissionError("Merchant not authorized")
        
        # Parse and validate rows
        errors = []
        for row_num, row in enumerate(parse_csv(file)):
            if not validate_row(row):
                errors.append({
                    "row": row_num,
                    "errors": get_row_errors(row)
                })
        
        return errors
```

**Checklist:**
- [ ] All fields validated per spec
- [ ] Edge cases handled
- [ ] Permissions checked
- [ ] Error messages clear and actionable

### 4.4 Tests

```bash
# Use test-automation-engineer skill
"test-automation-engineer, create tests for bulk upload:
1. Unit tests for validation logic
2. Integration tests for API
3. E2E tests for full flow
4. Edge case tests (large files, invalid data)"
```

**Test Coverage Requirements:**
- Unit tests: >80% coverage
- Integration tests: All API endpoints
- E2E tests: Happy path + 3 error scenarios
- Performance tests: <500ms response time

### 4.5 Internal Demo

**Before Phase 5 UAT:**
- Demo to Product team
- Walk through all states
- Show error handling
- Get preliminary feedback

### Claude Code Usage (Phase 4)

✅ **Generate:**
- Component implementations
- API endpoints
- Validation logic
- Test cases
- Refactoring suggestions

❌ **Do NOT:**
- Deploy without testing
- Skip code review
- Merge without CI passing
- Proceed without demo approval

**Critical Context Rules:**
```
When using Claude Code in Phase 4:

1. Always provide FULL context:
   - Module requirements doc
   - API specification
   - Database schema
   - Existing related code

2. Never provide partial context expecting correct output

3. All generated code MUST:
   - Pass linting and type checking
   - Include unit tests
   - Follow project architecture
   - Be reviewed by senior engineer
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Feature-Complete Module** (AI-assisted)
   - Frontend implemented
   - Backend implemented
   - All acceptance criteria met

2. **Updated API Documentation** (AI-generated)
   ```
   /documents/modules/bulk-coupon-upload/
   └── api-docs-v1.0.md
   ```

3. **Unit Testing Plan** (AI-assisted)
   ```
   /tests/modules/bulk-coupon-upload/
   ├── test_validation.py
   ├── test_api.py
   └── test_worker.py
   ```

4. **Test Results**
   - All acceptance criteria tests passing
   - Coverage report >80%

❌ **Quality Gate:**
**STOP: No Phase 5 without passing tests + internal demo approval**

---

## Phase 5: QA & UAT

**Owner:** Engineering (QA), Product & Support (UAT)  
**Duration:** 3-5 days per module

### 5.1 QA Testing (Engineering)

**Functional Testing:**
- [ ] All features work as specified
- [ ] All acceptance criteria pass
- [ ] No critical bugs

**Edge Case Testing:**
- [ ] All documented edge cases tested
- [ ] Error messages clear
- [ ] System degrades gracefully

**Performance Testing:**
- [ ] Load testing completed
- [ ] Response times acceptable
- [ ] No memory leaks

**Security Testing:**
- [ ] Authentication/authorization verified
- [ ] Input validation comprehensive
- [ ] No SQL injection vulnerabilities
- [ ] CSRF protection enabled

### 5.2 UAT (Product & Support)

**Product Validation:**
- Does it solve the original problem?
- Is the UX intuitive?
- Are there any usability issues?

**Support Validation:**
- Are error messages clear to users?
- Can users self-recover from errors?
- Will this reduce support tickets?

**UAT Test Script:**
```markdown
## UAT: Bulk Coupon Upload

### Scenario 1: Successful Upload
1. Login as merchant
2. Navigate to "Upload Coupons"
3. Upload valid CSV with 100 rows
4. Verify progress indicator shows
5. Verify success message with count
6. Verify all 100 coupons appear in dashboard

**Expected:** All steps complete without errors
**Actual:** [PASS/FAIL + Notes]

### Scenario 2: Invalid Data
1. Upload CSV with invalid discounts (>100%)
2. Verify specific error for row 5
3. Fix row 5, re-upload
4. Verify success

**Expected:** Clear error, easy to fix
**Actual:** [PASS/FAIL + Notes]

### Scenario 3: Large File
1. Upload CSV with 10,000 rows
2. Verify background processing
3. Check progress endpoint
4. Verify completion in ~5 minutes

**Expected:** Handles large files gracefully
**Actual:** [PASS/FAIL + Notes]
```

### Fix & Re-test Cycle

**Bug Triage:**
- **Critical**: Blocks core functionality → Fix immediately
- **High**: Major usability issue → Fix before release
- **Medium**: Minor issue → Fix if time allows
- **Low**: Cosmetic → Backlog for next release

**Re-test after fixes:**
- Rerun failed test cases
- Regression test related features
- Get UAT sign-off on fixes

### Outputs & Gates

✅ **Required Deliverables:**

1. **QA Test Report**
   ```
   /documents/modules/bulk-coupon-upload/
   └── qa-report-v1.0.md
       ├── Test cases executed
       ├── Bugs found & fixed
       └── Performance metrics
   ```

2. **UAT Sign-off** (from Product + Support)
   - Formal approval document
   - List of known issues (if any)
   - Go/No-go decision

❌ **Quality Gate:**
**STOP: No Phase 6 production release without UAT sign-off**

---

## Phase 6: Production Release

**Owner:** Engineering  
**Duration:** 1-2 days

### 6.1 Create Release Notes (REQUIRED)

**Before deployment, create comprehensive release notes for tracking and communication.**

```markdown
# Release Notes: v[VERSION] - [MODULE NAME]

**Release Date:** [YYYY-MM-DD]  
**Module:** [Module Name]  
**Version:** [X.Y.Z]  
**Type:** Major Feature / Enhancement / Bug Fix  
**Portals Affected:** [B2B / B2C / C2C / Admin / Merchant / Partnership / Customer]

---

## 📋 Summary

Brief 2-3 sentence overview of what this release includes and why it matters.

Example: This release introduces bulk coupon upload functionality for B2B merchants, enabling them to upload up to 10,000 coupons at once via CSV. This feature significantly reduces the time required for large-scale coupon creation from hours to minutes.

---

## ✨ New Features

### [Feature Name]
- **Description:** What the feature does
- **User Benefit:** How it helps users
- **Access:** Who can use it (role/portal)
- **Documentation:** Link to user guide

**Example:**
### Bulk Coupon Upload
- **Description:** Merchants can now upload multiple coupons simultaneously via CSV file
- **User Benefit:** Reduces coupon creation time by 95% for bulk operations
- **Access:** B2B Portal - Merchant Admin role
- **Documentation:** See [Bulk Upload Guide](link)

---

## 🔧 Improvements

### [Improvement Area]
- **Before:** Previous behavior
- **After:** New behavior
- **Impact:** Who benefits

**Example:**
### Validation Feedback
- **Before:** Generic error messages for invalid coupons
- **After:** Specific row-by-row error feedback with actionable messages
- **Impact:** Merchants can fix issues 80% faster

---

## 🐛 Bug Fixes

### [Bug Description]
- **Issue:** What was broken
- **Fix:** How it was resolved
- **Affected Users:** Who experienced the bug
- **Ticket:** BUG-XXX

**Example:**
### NFC Redemption Signature Validation
- **Issue:** NFC redemptions failing with "Invalid signature" error
- **Fix:** Added backward compatibility for SHA256 signatures
- **Affected Users:** All mobile app users (iOS & Android)
- **Ticket:** BUG-456

---

## 🔄 Breaking Changes

**⚠️ IMPORTANT: List any breaking changes that require action**

### [Breaking Change]
- **What Changed:** Technical description
- **Migration Required:** Yes/No
- **Action Required:** Steps users/developers must take
- **Deadline:** When migration must be completed

**Example:**
### API Response Format Change
- **What Changed:** Coupon API now returns `title_long` field in addition to `title`
- **Migration Required:** No (backward compatible)
- **Action Required:** Update client applications to use `title_long` for longer titles
- **Deadline:** Optional - old `title` field still supported

---

## 📊 Database Changes

### Schema Migrations
- **Tables Modified:** List of tables
- **New Tables:** List if any
- **Migration Script:** `migrations/v1.2.0-bulk-upload.sql`
- **Rollback Script:** `migrations/v1.2.0-rollback.sql`
- **Estimated Duration:** Expected migration time

**Example:**
- **Tables Modified:** `coupons` (added `bulk_upload_id` column)
- **New Tables:** `bulk_uploads` (tracks upload jobs)
- **Migration Script:** `migrations/v1.2.0-bulk-upload.sql`
- **Rollback Script:** `migrations/v1.2.0-rollback.sql`
- **Estimated Duration:** ~2 minutes for 1M rows

---

## 🔐 Security Updates

- **Authentication:** Any auth changes
- **Authorization:** Permission changes
- **Data Protection:** Encryption updates
- **Vulnerabilities Fixed:** CVE references if applicable

**Example:**
- **Authorization:** Added new `bulk_upload` permission for B2B merchant admins
- **Data Protection:** CSV files encrypted at rest in S3
- **Rate Limiting:** 5 uploads per hour per merchant

---

## 📈 Performance Impact

### Expected Changes
- **API Response Time:** Impact on latency
- **Database Load:** Expected increase/decrease
- **Storage:** Additional storage requirements
- **Cost:** Estimated monthly cost impact

**Example:**
- **API Response Time:** No impact (async processing)
- **Database Load:** +5% during upload processing
- **Storage:** +100MB per 10,000 coupons uploaded
- **Cost:** ~$50/month for S3 + Lambda processing

---

## 🧪 Testing Coverage

- **Unit Tests:** X tests added
- **Integration Tests:** Y tests added
- **E2E Tests:** Z scenarios covered
- **Test Coverage:** Overall percentage
- **UAT Completed:** Date and sign-off

**Example:**
- **Unit Tests:** 45 tests added
- **Integration Tests:** 12 API endpoint tests
- **E2E Tests:** 5 complete upload scenarios
- **Test Coverage:** 87% overall
- **UAT Completed:** 2026-01-15 (Signed off by Product + Support)

---

## 📚 Documentation Updates

- [ ] API Documentation updated
- [ ] User Guide created/updated
- [ ] Admin Guide updated
- [ ] Developer README updated
- [ ] Architecture Decision Records (ADRs) added

**Links:**
- API Docs: [Link]
- User Guide: [Link]
- Admin Guide: [Link]

---

## 🚀 Deployment Information

### Deployment Strategy
- **Type:** Blue-Green / Rolling / Canary / Direct
- **Downtime:** Expected downtime (if any)
- **Rollback Plan:** Available/Tested
- **Feature Flags:** Used/Not Used

### Deployment Steps
1. Database migration (2 minutes)
2. Backend deployment (5 minutes)
3. Frontend deployment (3 minutes)
4. Smoke testing (10 minutes)
5. Monitoring period (30 minutes)

### Rollback Procedure
If issues detected:
1. Disable feature flag (instant)
2. Rollback backend (5 minutes)
3. Rollback database if needed (2 minutes)
4. Notify stakeholders

---

## ⚠️ Known Issues

### [Issue Description]
- **Impact:** Who/what is affected
- **Workaround:** Temporary solution
- **Fix Planned:** Timeline for permanent fix
- **Ticket:** Issue tracking number

**Example:**
### CSV Upload Limited to 10,000 Rows
- **Impact:** Merchants with >10,000 coupons must split into multiple uploads
- **Workaround:** Upload in batches of 10,000
- **Fix Planned:** v1.3.0 (February 2026) - increase to 50,000
- **Ticket:** FEATURE-789

---

## 👥 Team & Contributors

- **Product Owner:** [Name]
- **Engineering Lead:** [Name]
- **Developers:** [Names]
- **QA:** [Name]
- **Support:** [Name]
- **Reviewers:** [Names]

---

## 📞 Support & Feedback

### For Issues
- **Support Email:** support@mezzofy.com
- **Incident Channel:** #incidents (Slack)
- **Ticket System:** [Link to ticket system]

### For Feedback
- **Product Feedback:** product@mezzofy.com
- **Feature Requests:** [Link to feedback form]

---

## 📅 Timeline

- **Development Started:** [Date]
- **Code Complete:** [Date]
- **QA Started:** [Date]
- **UAT Completed:** [Date]
- **Deployed to Production:** [Date]
- **Stable Declared:** [Date] (after 24h monitoring)

---

## 🔗 Related Releases

- **Previous:** v1.1.0 (2025-12-15)
- **Next Planned:** v1.3.0 (2026-02-01)

---

## 📝 Additional Notes

Any other important information, context, or considerations.

---

**Approved By:**
- [ ] Product: [Name] - [Date]
- [ ] Engineering: [Name] - [Date]
- [ ] QA: [Name] - [Date]
- [ ] Support: [Name] - [Date]

**Published By:** [Name]  
**Publication Date:** [YYYY-MM-DD HH:MM UTC]
```

### Using AI to Generate Release Notes

```
"technical-writer, create release notes for v1.2.0 - Bulk Coupon Upload.

Context:
- New feature: Merchants can upload 1000+ coupons via CSV
- Affected portal: B2B
- Breaking changes: None
- Database: Added bulk_uploads table
- Testing: 87% coverage, UAT passed
- Deployment: Scheduled for Jan 15, 2026

Generate complete release notes following the template."
```

---

### 6.2 Pre-Launch Checklist

### 6.2 Pre-Launch Checklist

```markdown
## Production Readiness Checklist

### Code
- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Merged to main branch
- [ ] Version tagged (v1.2.0)

### Infrastructure
- [ ] Database migrations tested
- [ ] CDK infrastructure updated
- [ ] Environment variables configured
- [ ] Monitoring alerts set up

### Documentation (MANDATORY)
- [ ] **Release notes created and approved** ⭐
- [ ] API docs published
- [ ] User guide updated
- [ ] Runbook created
- [ ] Release notes published to team wiki/portal

### Backout Plan
- [ ] Rollback procedure documented
- [ ] Database migration rollback tested
- [ ] Feature flag ready (if applicable)
- [ ] Backup verified
```

### 6.2 Deployment

```bash
# Production deployment steps

# 1. Database migration (manual verification)
alembic upgrade head

# 2. Backend deployment
cdk deploy BackendStack --require-approval never

# 3. Frontend deployment
aws amplify publish

# 4. Smoke test
curl -X GET https://api.mezzofy.com/v2/health
# Expected: {"status": "ok", "version": "1.2.0"}

# 5. Monitor for 30 minutes
watch -n 10 'aws cloudwatch get-metric-statistics ...'
```

### 6.3 Post-Deployment Monitoring

**First 30 minutes:**
- Monitor error rates
- Check response times
- Verify no 500 errors
- Watch database connections

**First 24 hours:**
- Monitor support tickets
- Check user feedback
- Review logs for anomalies
- Track feature adoption

### 6.4 Rollback-Ready

**If issues detected:**
```bash
# 1. Disable feature via feature flag (instant)
curl -X POST https://api.mezzofy.com/v2/admin/feature-flags \
  -d '{"bulk_upload": false}'

# 2. Rollback code (5 minutes)
cdk deploy BackendStack --version v1.1.0

# 3. Rollback database (if needed)
alembic downgrade -1

# 4. Notify stakeholders
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Release Notes** (MANDATORY - AI-assisted) ⭐
   ```
   /documents/modules/bulk-coupon-upload/
   └── release-notes-v1.2.0.md
   ```
   - Published to team wiki/portal
   - Approved by Product, Engineering, QA, Support
   - Used for tracking and communication

2. **Live System Deployment** (Manual)
   - Production environment live
   - All systems green

3. **Updated API Documentation** (AI-assisted)
   ```
   /documents/modules/bulk-coupon-upload/
   └── api-docs-v1.0.md
   ```

4. **Updated User Guide** (AI-assisted)
   ```markdown
   # Release v1.2.0 - Bulk Coupon Upload
   
   ## New Features
   - Merchants can now upload coupons via CSV
   - Support for up to 10,000 coupons per upload
   - Real-time progress tracking
   
   ## Improvements
   - Better error messages for invalid data
   - Faster background processing
   
   ## Bug Fixes
   - Fixed issue with special characters in titles
   ```

3. **Updated User Guide** (AI-assisted)
   ```
   /documents/user-guides/
   └── bulk-upload-guide-v1.0.md
   ```

❌ **Quality Gate:**
**STOP: Monitor for 24 hours before declaring stable**

---

## Phase 7: Post-Launch

**Owner:** Support  
**Contributors:** Product, Engineering  
**Duration:** Ongoing (2 weeks active monitoring)

### 7.1 Issue Monitoring

**Support tracks:**
- Bug reports
- Feature requests
- Usability complaints
- Performance feedback

**Triage Process:**
```markdown
## Issue Priority

**P0 - Critical** (Fix within 4 hours)
- System down
- Data loss
- Security breach

**P1 - High** (Fix within 24 hours)
- Core feature broken
- Widespread user impact
- Workaround exists but poor UX

**P2 - Medium** (Fix in next sprint)
- Edge case issue
- Limited user impact
- Workaround available

**P3 - Low** (Backlog)
- Feature request
- Cosmetic issue
- Enhancement
```

### 7.2 Feedback Collection

**Sources:**
- Support tickets
- User surveys
- Product analytics
- Social media monitoring

**Feed into backlog:**
- What's working well?
- What's confusing?
- What's missing?
- What's slow?

### 7.3 Success Metrics

```markdown
## Post-Launch KPIs

### Adoption
- [ ] 50% of merchants tried bulk upload (Week 1)
- [ ] 80% success rate on uploads
- [ ] <5% error rate

### Performance
- [ ] <500ms API response time (p95)
- [ ] <2 minutes processing for 1000 rows
- [ ] <1% failed background jobs

### Support
- [ ] <10 support tickets in Week 1
- [ ] <2 critical bugs found
- [ ] >4.0/5.0 user satisfaction score
```

### 7.4 Iteration Planning

**After 2 weeks:**
- Retrospective meeting
- What went well?
- What needs improvement?
- Plan next module/iteration

**Feed learnings back to Phase 1** for next module.

---

## Quality Checklist (All Phases)

### Phase 1 ✅
- [ ] Requirements signed off by Product, Engineering, Support
- [ ] All fields defined with validation rules
- [ ] Edge cases documented
- [ ] Acceptance criteria clear

### Phase 2 ✅
- [ ] UI flows approved by Product
- [ ] All states validated (empty, loading, error, success)
- [ ] Support reviewed for clarity
- [ ] Templates extracted for reuse

### Phase 3 ✅
- [ ] Architecture approved by Engineering Lead
- [ ] API contracts defined (OpenAPI)
- [ ] Database schema designed
- [ ] Security baseline met
- [ ] Effort estimated

### Phase 4 ✅
- [ ] Code follows project standards
- [ ] All tests passing (>80% coverage)
- [ ] Internal demo approved
- [ ] Documentation updated

### Phase 5 ✅
- [ ] QA tests passing
- [ ] UAT signed off by Product + Support
- [ ] All critical bugs fixed
- [ ] Performance acceptable

### Phase 6 ✅
- [ ] Pre-launch checklist complete
- [ ] Production deployment successful
- [ ] Monitoring active
- [ ] Rollback plan tested

### Phase 7 ✅
- [ ] Support monitoring for 2 weeks
- [ ] Issues triaged and resolved
- [ ] Success metrics tracked
- [ ] Retrospective completed

---

## Critical Rules for Claude Code Integration

### Context is Everything

**Always provide Claude with:**
```
1. Current Phase (which phase are we in?)
2. Module Name (what are we building?)
3. Requirements Doc (what does it need to do?)
4. Existing Code (what already exists?)
5. Architecture (how does it fit in?)
6. Constraints (what are the limits?)
```

**Never:**
- Paste partial context
- Skip background information
- Assume Claude remembers previous sessions
- Expect correct output from incomplete prompts

### Human-in-the-Loop Requirements

**All Claude-generated content MUST:**
1. Be reviewed by appropriate owner
2. Pass automated tests
3. Align with architecture
4. Meet security standards
5. Be approved before merge

**Humans decide:**
- Business priorities
- Architecture choices
- Security policies
- Release timing
- Resource allocation

**Claude assists:**
- Code generation
- Documentation
- Test cases
- Refactoring
- Explanation

### Appropriate Use by Phase

| Phase | Claude CAN | Claude CANNOT |
|-------|------------|---------------|
| 1. Requirements | Generate field specs, edge cases | Decide business priorities |
| 2. UI/UX | Generate wireframes, components | Make design decisions |
| 3. Tech Design | Generate API specs, schemas | Approve architecture |
| 4. Development | Generate code, tests | Deploy to production |
| 5. QA/UAT | Generate test cases | Sign off on quality |
| 6. Release | Generate docs, release notes | Authorize deployment |
| 7. Post-Launch | Analyze issues, suggest fixes | Prioritize bugs |

---

**Workflow Owner:** Product Team  
**Last Updated:** December 2025  
**Version:** 2.0
