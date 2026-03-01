---
name: workflow-change-request
description: Change request workflow specialist for handling modifications to existing modules. Use when users request changes to live features, enhancements to deployed functionality, scope expansions, or modifications that impact existing code. Follows a streamlined process focused on impact analysis, backward compatibility, and safe deployment of changes to production systems.
---

# Workflow: Change Request

Handle modifications to existing modules with proper impact analysis and backward compatibility.

## Overview

This workflow handles **changes to existing, deployed features** where functionality already exists but needs modification, enhancement, or expansion.

**Key Differences from New Module Workflow:**
- ❌ Faster than new module (no full design phase)
- ✅ Heavy focus on impact analysis
- ✅ Backward compatibility required
- ✅ Migration strategy needed
- ✅ Rollback plan mandatory

## When to Use This Workflow

✅ **Use Change Request Workflow for:**
- Adding fields to existing forms
- Modifying business logic rules
- Enhancing existing features
- Changing UI/UX of live features
- Performance improvements
- Expanding API capabilities
- Database schema changes

❌ **Use New Module Workflow instead for:**
- Completely new features
- New portals or major sections
- New integrations
- Greenfield development

❌ **Use Bug Fix Workflow instead for:**
- Defects in production
- Incorrect behavior
- Critical issues
- Hot fixes

---

## Phase 1: Change Request Intake (1-2 days)

**Owner:** Product  
**Contributors:** Support, Engineering

### Objectives

Understand the change, validate the need, and assess impact before commitment.

### Activities

#### 1.1 Document the Change Request

```markdown
# Change Request: [CR-XXX]

## Requested By
- **Requestor:** [Name/Team]
- **Date:** [YYYY-MM-DD]
- **Priority:** [P0-Critical / P1-High / P2-Medium / P3-Low]

## Current Behavior
Describe what the system does today:
- Field X accepts only 50 characters
- Discount validation allows max 50%
- UI shows basic coupon info only

## Requested Change
Describe what should change:
- Field X should accept 200 characters
- Discount validation should allow up to 90%
- UI should show merchant details + reviews

## Business Justification
Why is this change needed?
- 30% of merchants hitting 50-char limit
- High-value merchants need >50% discounts
- Users requesting more coupon context

## User Impact
- Affects: All B2B merchants
- Benefits: Can create more descriptive coupons
- Risk: Existing integrations may break
```

#### 1.2 Impact Assessment

```markdown
## Impact Analysis

### Affected Components
- [ ] Frontend (B2B portal)
- [ ] Backend API (PATCH /coupons/:id)
- [ ] Database (coupons table)
- [ ] Mobile app
- [ ] Documentation

### Backward Compatibility
**Breaking Changes:**
- Database schema change (add columns)
- API response includes new fields
- Validation rules changed

**Non-Breaking:**
- Existing data remains valid
- Old API clients still work
- No data migration required

### Technical Debt
- Current validation logic is scattered
- Need to refactor before change
- Opportunity to improve architecture

### Dependencies
- Requires: None
- Blocks: CR-125 (related feature)
- Related: CR-118 (similar change)
```

#### 1.3 Estimate Effort

```markdown
## Effort Estimate

### Development
- Frontend: 1 day (update form, validation)
- Backend: 2 days (API, validation, tests)
- Database: 0.5 days (migration script)
- Total: 3.5 days

### Testing
- QA: 1 day
- UAT: 0.5 days

### Deployment
- Migration: 0.5 days
- Monitoring: Ongoing

**Total Estimate:** 5-6 days
```

#### 1.4 Prioritization

```markdown
## Priority Matrix

### Impact vs Effort
- **High Impact, Low Effort** → Do Now
- **High Impact, High Effort** → Schedule
- **Low Impact, Low Effort** → Backlog
- **Low Impact, High Effort** → Reject

This CR: High Impact, Medium Effort → **Schedule for Sprint 23**
```

### Claude Code Usage (Phase 1)

✅ **Generate:**
- Impact analysis checklists
- Effort estimation templates
- Risk assessment matrices

❌ **Do NOT:**
- Decide priority without stakeholder input
- Approve changes without impact review

**Example Prompt:**
```
"workflow-change-request, analyze impact for this change:

Current: Coupon title max 50 characters
Requested: Increase to 200 characters

Affected: B2B portal, API, database, mobile app

Generate:
1. Complete impact analysis
2. Backward compatibility assessment
3. Breaking changes list
4. Migration strategy"
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Change Request Document** (CR-XXX)
   ```
   /documents/change-requests/CR-XXX/
   └── cr-xxx-request-v1.0.md
   ```

2. **Impact Assessment** (AI-assisted)
   - Affected components
   - Breaking changes
   - Dependencies

3. **Go/No-Go Decision**
   - Approved by Product
   - Effort estimated by Engineering
   - Priority assigned

❌ **Quality Gate:**
**STOP: No Phase 2 without CR approval + impact assessment**

---

## Phase 2: Technical Planning (1-3 days)

**Owner:** Engineering  
**Contributors:** Product (for clarifications)

### Objectives

Plan the implementation with focus on **backward compatibility** and **safe rollout**.

### Activities

#### 2.1 Design the Change

```markdown
## Technical Design: CR-XXX

### Database Changes

#### Option 1: Add New Column (Recommended)
```sql
-- Migration: Add new column
ALTER TABLE coupons 
ADD COLUMN title_long VARCHAR(200);

-- Existing 'title' column remains (backward compatibility)
-- New UI uses 'title_long' if present, falls back to 'title'
```

**Pros:**
- ✅ Backward compatible
- ✅ No data migration needed
- ✅ Can rollback easily

**Cons:**
- ❌ Two columns with similar purpose
- ❌ Slight storage overhead

#### Option 2: Modify Existing Column (Not Recommended)
```sql
-- Migration: Expand column
ALTER TABLE coupons 
ALTER COLUMN title TYPE VARCHAR(200);
```

**Pros:**
- ✅ Cleaner schema

**Cons:**
- ❌ Risky migration on large tables
- ❌ Requires downtime
- ❌ Hard to rollback

**Decision:** Use Option 1 for safety
```

#### 2.2 API Changes

```yaml
# PATCH /api/v2/coupons/:id

Request (v2):
  {
    "title": "50% Off",        # OLD: max 50 chars (still supported)
    "title_long": "50% Off..."  # NEW: max 200 chars (optional)
  }

Response (v2):
  {
    "id": "uuid",
    "title": "50% Off",        # Always present
    "title_long": "50% Off..." # Present if available
  }

Backward Compatibility:
  - Old clients: Can ignore 'title_long' field
  - New clients: Use 'title_long' if present, else 'title'
  - Validation: Both fields validated independently
```

#### 2.3 Migration Strategy

```markdown
## Data Migration Plan

### Phase 1: Deploy Code (No Data Changes)
- Deploy new API version
- New column exists but empty
- Old behavior continues working

### Phase 2: Gradual Migration (Background Job)
- Copy 'title' → 'title_long' for existing records
- Run over 7 days (low priority job)
- No user impact

### Phase 3: UI Cutover
- Frontend starts using 'title_long'
- Users can enter longer titles
- Old data still displays correctly

### Rollback Plan
If issues occur:
1. Revert frontend to use 'title' field
2. Stop background migration
3. No data loss (old column intact)
```

#### 2.4 Feature Flag Strategy

```typescript
// Use feature flags for gradual rollout
const FEATURE_FLAGS = {
  enableLongTitles: {
    enabled: false,  // Start disabled
    rollout: 'gradual', // 10% → 50% → 100%
    rollbackReady: true
  }
};

// In code
if (featureFlags.enableLongTitles) {
  return coupon.title_long || coupon.title;
} else {
  return coupon.title;
}
```

### Claude Code Usage (Phase 2)

✅ **Generate:**
- Migration scripts
- API specifications with versioning
- Feature flag implementations
- Rollback procedures

❌ **Do NOT:**
- Choose migration strategy without review
- Skip backward compatibility testing

**Example Prompt:**
```
"backend-developer, design API change for longer coupon titles.

Current API:
- PATCH /coupons/:id
- Field: title (VARCHAR 50)

Requested:
- Support up to 200 characters
- Must be backward compatible
- Old clients must continue working

Generate:
1. API specification with versioning
2. Database migration (safe strategy)
3. Rollback plan"
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Technical Design Document**
   ```
   /documents/change-requests/CR-XXX/
   └── technical-design-v1.0.md
   ```

2. **Migration Scripts** (AI-generated, reviewed)
   ```sql
   /migrations/cr-xxx-add-title-long.sql
   /migrations/cr-xxx-rollback.sql
   ```

3. **Feature Flag Configuration**
   ```typescript
   /config/feature-flags/cr-xxx.ts
   ```

❌ **Quality Gate:**
**STOP: No Phase 3 without migration strategy approval**

---

## Phase 3: Implementation (2-5 days)

**Owner:** Engineering

### Objectives

Implement the change with **feature flags** and **comprehensive tests**.

### Activities

#### 3.1 Database Migration

```bash
# Create migration
alembic revision -m "CR-XXX: Add title_long column"

# Test migration on staging
alembic upgrade head

# Test rollback
alembic downgrade -1

# Verify data integrity
SELECT COUNT(*) FROM coupons WHERE title IS NULL;  # Should be 0
```

#### 3.2 Backend Implementation

```python
# models/schemas/coupon_schema.py
class CouponSchema(Base):
    __tablename__ = "coupons"
    
    id = Column(String, primary_key=True)
    title = Column(String(50), nullable=False)  # Keep existing
    title_long = Column(String(200), nullable=True)  # NEW
    
# models/dtos/coupon_dto.py
class UpdateCouponDTO(BaseModel):
    title: Optional[str] = Field(None, max_length=50)
    title_long: Optional[str] = Field(None, max_length=200)
    
    @validator('title_long')
    def validate_title_long(cls, v):
        if v and len(v) < 3:
            raise ValueError('Title must be at least 3 characters')
        return v

# services/coupon_service.py
class CouponService:
    def update_coupon(self, coupon_id: str, dto: UpdateCouponDTO):
        # Feature flag check
        if not feature_flags.is_enabled('enable_long_titles'):
            if dto.title_long:
                raise ValueError('Long titles not yet available')
        
        # Update logic
        coupon = self.repo.get_by_id(coupon_id)
        if dto.title:
            coupon.title = dto.title
        if dto.title_long:
            coupon.title_long = dto.title_long
        
        return self.repo.update(coupon)
```

#### 3.3 Frontend Implementation

```typescript
// presentation/viewmodels/useCouponViewModel.ts
import { create } from 'zustand';
import { featureFlags } from '@/core/featureFlags';

export const useCouponViewModel = create<CouponState>((set) => ({
  // ...
  
  getTitleMaxLength: () => {
    return featureFlags.isEnabled('enableLongTitles') ? 200 : 50;
  },
  
  getDisplayTitle: (coupon: Coupon) => {
    // Use long title if available, else short title
    return coupon.title_long || coupon.title;
  },
}));

// presentation/views/CouponForm.tsx
export const CouponForm = () => {
  const { getTitleMaxLength } = useCouponViewModel();
  const maxLength = getTitleMaxLength();
  
  return (
    <Input
      name="title"
      maxLength={maxLength}
      helperText={`Max ${maxLength} characters`}
    />
  );
};
```

#### 3.4 Testing

```python
# tests/test_cr_xxx_long_titles.py
import pytest

class TestLongTitles:
    def test_accepts_long_title_when_enabled(self):
        """Test that long titles work with feature flag"""
        feature_flags.enable('enable_long_titles')
        
        dto = UpdateCouponDTO(
            title_long="A" * 200  # 200 characters
        )
        
        coupon = coupon_service.update_coupon('test-id', dto)
        assert coupon.title_long == "A" * 200
    
    def test_rejects_long_title_when_disabled(self):
        """Test that long titles blocked without flag"""
        feature_flags.disable('enable_long_titles')
        
        dto = UpdateCouponDTO(
            title_long="A" * 200
        )
        
        with pytest.raises(ValueError):
            coupon_service.update_coupon('test-id', dto)
    
    def test_backward_compatibility(self):
        """Test old clients still work"""
        # Old client only sends 'title'
        dto = UpdateCouponDTO(title="Short title")
        
        coupon = coupon_service.update_coupon('test-id', dto)
        assert coupon.title == "Short title"
        assert coupon.title_long is None  # No long title set
    
    def test_migration_preserves_data(self):
        """Test existing data not affected"""
        # Get coupon before migration
        coupon_before = coupon_service.get_coupon('existing-id')
        
        # Run migration
        run_migration('cr-xxx-add-title-long')
        
        # Get coupon after migration
        coupon_after = coupon_service.get_coupon('existing-id')
        
        # Verify old data intact
        assert coupon_before.title == coupon_after.title
```

### Claude Code Usage (Phase 3)

✅ **Generate:**
- Migration scripts
- Model changes
- Feature flag logic
- Test cases

❌ **Do NOT:**
- Deploy without feature flags
- Skip migration testing
- Forget rollback scripts

### Outputs & Gates

✅ **Required Deliverables:**

1. **Code Changes** (with feature flags)
   - Frontend updates
   - Backend updates
   - Database migration

2. **Tests Passing**
   - Unit tests for new logic
   - Backward compatibility tests
   - Migration tests

3. **Rollback Verified**
   - Rollback script tested
   - Feature flag disable tested

❌ **Quality Gate:**
**STOP: No Phase 4 without tests passing + rollback verified**

---

## Phase 4: Staged Rollout (1-2 weeks)

**Owner:** Engineering  
**Contributors:** Product, Support

### Objectives

Roll out change gradually with monitoring at each stage.

### 4.1 Create Release Notes (REQUIRED BEFORE ROLLOUT)

**All change requests must have release notes before beginning staged rollout.**

```markdown
# Release Notes: CR-[NUMBER] - [CHANGE DESCRIPTION]

**Release Date:** [YYYY-MM-DD]  
**Change Request:** CR-[NUMBER]  
**Version:** [X.Y.Z]  
**Type:** Enhancement / Modification / Schema Change  
**Portals Affected:** [List affected portals]

---

## 📋 Summary

Brief description of what changed and why.

Example: This change request increases the coupon title character limit from 50 to 200 characters, allowing merchants to provide more descriptive coupon titles.

---

## 🔄 What Changed

### Before
- Coupon title: VARCHAR(50)
- Maximum 50 characters allowed
- Users frequently hitting limit

### After
- Coupon title: VARCHAR(50) + new title_long VARCHAR(200)
- Support for up to 200 characters
- Backward compatible with existing titles

---

## ✨ User Benefits

- **Merchants:** Can create more descriptive coupon titles
- **Consumers:** Better understanding of coupon offers
- **Impact:** 30% of merchants currently hitting limit

---

## 🔧 Technical Changes

### Database
- **New Column:** `title_long VARCHAR(200)` added to `coupons` table
- **Migration:** `migrations/cr-125-title-long.sql`
- **Rollback:** `migrations/cr-125-rollback.sql`
- **Data Migration:** Background job copies existing titles

### API
- **Endpoint:** PATCH /api/v2/coupons/:id
- **New Field:** `title_long` (optional)
- **Backward Compatible:** Yes - existing `title` field unchanged
- **Response:** Includes both `title` and `title_long` fields

### Frontend
- **Component:** CouponForm updated to support longer titles
- **Validation:** Client-side validation for 200 chars
- **Feature Flag:** `enable_long_titles` controls UI display

---

## 🚀 Rollout Plan

### Stage 1: Internal (Days 1-2)
- 0% users (team only)
- Test all functionality

### Stage 2: Beta (Days 3-5)
- 5% of users
- Monitor error rates and feedback

### Stage 3: Limited (Days 6-9)
- 25% of users
- Monitor adoption metrics

### Stage 4: Majority (Days 10-12)
- 75% of users
- Prepare for full release

### Stage 5: Full (Day 13+)
- 100% of users
- Continue monitoring

---

## ⚠️ Breaking Changes

**None** - This change is backward compatible.

- Old API clients will continue to work
- Existing titles remain valid
- No data migration required for functionality

---

## 🔄 Migration Required

**For Users:** No action required  
**For Developers:** Optional - update clients to use `title_long` field

```javascript
// Old (still works)
const title = coupon.title;

// New (recommended)
const title = coupon.title_long || coupon.title;
```

---

## 📊 Success Metrics

- **Target Adoption:** 50% of new coupons use longer titles within 2 weeks
- **Error Rate:** <0.1% error rate maintained
- **Performance:** No degradation in API response time
- **Support Tickets:** No increase in title-related support issues

---

## 🧪 Testing Completed

- [ ] Unit tests: 15 tests added
- [ ] Integration tests: 8 API tests
- [ ] Backward compatibility tests: Passed
- [ ] Migration tests: Passed on staging
- [ ] E2E tests: 3 complete scenarios
- [ ] UAT: Approved by Product & Support

---

## 📚 Documentation

- [x] API documentation updated
- [x] Migration guide created
- [x] User guide updated
- [x] Developer README updated

**Links:**
- API Docs: [Link to updated API docs]
- User Guide: [Link to user guide]

---

## 🔙 Rollback Plan

If issues occur:
1. Disable feature flag `enable_long_titles`
2. Users fall back to old behavior
3. No data loss (title field intact)
4. Can re-enable after fix

---

## ⚠️ Known Limitations

### CSV Import
- Bulk upload still limited to 50 character titles
- Fix planned: CR-150 (next sprint)

---

## 👥 Team

- **Requestor:** [Name]
- **Product Owner:** [Name]
- **Tech Lead:** [Name]
- **Developers:** [Names]
- **QA:** [Name]

---

## 📅 Timeline

- **CR Created:** [Date]
- **Impact Analysis:** [Date]
- **Development:** [Date]
- **Testing:** [Date]
- **Rollout Start:** [Date]
- **Full Release:** [Date]

---

## 📞 Support

- **Issues:** support@mezzofy.com
- **Slack:** #cr-125-support
- **Documentation:** [Link]

---

**Approved By:**
- [ ] Product: [Name] - [Date]
- [ ] Engineering: [Name] - [Date]
- [ ] QA: [Name] - [Date]

**Published By:** [Name]  
**Publication Date:** [YYYY-MM-DD]
```

### Using AI to Generate Release Notes

```
"technical-writer, create release notes for CR-125.

Change: Increase coupon title from 50 to 200 characters
Type: Enhancement
Affected: B2B portal, API, database
Breaking: No
Rollout: 5-stage gradual rollout

Generate complete release notes."
```

---

### 4.2 Rollout Strategy

```markdown
## Gradual Rollout Plan

### Stage 1: Internal Testing (Days 1-2)
- **Audience:** Internal team only
- **Feature Flag:** 0% → Team members only
- **Monitor:** Basic functionality
- **Rollback Threshold:** Any critical error

### Stage 2: Beta Users (Days 3-5)
- **Audience:** 5% of users (opted-in beta testers)
- **Feature Flag:** 5%
- **Monitor:** 
  - Error rates
  - Performance metrics
  - User feedback
- **Rollback Threshold:** >1% error rate

### Stage 3: Limited Release (Days 6-9)
- **Audience:** 25% of users
- **Feature Flag:** 25%
- **Monitor:**
  - Database performance
  - API response times
  - Support tickets
- **Rollback Threshold:** >0.5% error rate

### Stage 4: Majority Release (Days 10-12)
- **Audience:** 75% of users
- **Feature Flag:** 75%
- **Monitor:** Continued monitoring
- **Rollback Threshold:** >0.3% error rate

### Stage 5: Full Release (Day 13+)
- **Audience:** 100% of users
- **Feature Flag:** 100% (keep flag for emergency)
- **Monitor:** Ongoing monitoring
- **Success Criteria:**
  - <0.1% error rate
  - No critical bugs
  - Positive user feedback
```

### Monitoring

```yaml
Metrics to Track:
  error_rate:
    threshold: <0.5%
    alert_on: >1%
    critical: >2%
  
  api_response_time:
    threshold: <500ms (p95)
    alert_on: >800ms
    critical: >1200ms
  
  database_query_time:
    threshold: <100ms (p95)
    alert_on: >200ms
    critical: >500ms
  
  user_adoption:
    target: >50% using long titles by Week 2
    track: Daily active users with title_long set
  
  support_tickets:
    baseline: Current rate
    alert_on: >150% of baseline
```

### Rollback Procedure

```bash
# Emergency Rollback (if critical issues)

# Step 1: Disable feature flag (instant)
curl -X POST https://api.mezzofy.com/admin/feature-flags \
  -d '{"enable_long_titles": false}'

# Step 2: Verify rollback
# - Old behavior restored
# - Users can still access their data
# - No errors in logs

# Step 3: Investigate & Fix
# - Review error logs
# - Identify root cause
# - Prepare hotfix if needed

# Step 4: Re-enable (after fix)
# - Fix deployed
# - Tests passing
# - Gradual re-rollout from Stage 2
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Release Notes** (MANDATORY) ⭐
   ```
   /documents/change-requests/CR-XXX/
   └── release-notes-cr-xxx-v1.0.md
   ```
   - Published before rollout begins
   - Approved by Product, Engineering, QA
   - Distributed to all stakeholders

2. **Rollout Plan Document**
   ```
   /documents/change-requests/CR-XXX/
   └── rollout-plan-v1.0.md
   ```

2. **Monitoring Dashboard**
   - Error rates by stage
   - Performance metrics
   - User adoption tracking

3. **Success Metrics**
   - All stages completed
   - Metrics within thresholds
   - No rollbacks needed

❌ **Quality Gate:**
**STOP: Pause rollout if metrics exceed thresholds**

---

## Phase 5: Post-Deployment (Ongoing)

**Owner:** Engineering + Support

### Activities

#### 5.1 Monitor Adoption

```markdown
## Adoption Tracking

Week 1:
- [ ] 10% of users tried long titles
- [ ] <5 support tickets related to change
- [ ] No data integrity issues

Week 2:
- [ ] 30% of users tried long titles
- [ ] Positive feedback from merchants
- [ ] Performance stable

Week 4:
- [ ] 60% of users adopted long titles
- [ ] Feature considered stable
- [ ] Ready to remove old field (future CR)
```

#### 5.2 Cleanup (Optional)

After 3-6 months of stability:

```sql
-- Future cleanup (separate CR)
-- Merge title_long back into title
-- This requires another change request!

ALTER TABLE coupons 
DROP COLUMN title,
RENAME COLUMN title_long TO title;
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Adoption Report**
   - Usage statistics
   - User feedback
   - Performance data

2. **Lessons Learned**
   - What went well?
   - What could improve?
   - Apply to future CRs

---

## Critical Rules for Change Requests

### Always Required

- [ ] Impact analysis before approval
- [ ] Backward compatibility maintained
- [ ] Migration strategy defined
- [ ] Feature flags implemented
- [ ] Rollback plan tested
- [ ] Gradual rollout used
- [ ] Monitoring in place

### Never Skip

- ❌ Don't deploy without feature flags
- ❌ Don't modify schema without migration plan
- ❌ Don't break existing API clients
- ❌ Don't skip backward compatibility tests
- ❌ Don't rush rollout (use stages)

### When to Pause

**Immediate Pause if:**
- Error rate >2%
- Data corruption detected
- Critical functionality broken
- API clients failing
- Database performance degraded

---

## Change Request Template

```markdown
# CR-XXX: [Brief Title]

## Metadata
- **Requested:** [Date]
- **Requestor:** [Name]
- **Priority:** [P0-P3]
- **Status:** [Intake/Approved/In Progress/Deployed/Closed]

## Current State
[What exists today]

## Requested Change
[What should change]

## Justification
[Why this is needed]

## Impact Analysis
- [ ] Frontend changes
- [ ] Backend changes
- [ ] Database changes
- [ ] API changes
- [ ] Mobile changes
- [ ] Documentation updates

## Breaking Changes
[List any breaking changes]

## Backward Compatibility
[How will this remain compatible?]

## Effort Estimate
- Dev: X days
- QA: X days
- Rollout: X days
- Total: X days

## Rollout Strategy
- Stage 1: [Description]
- Stage 2: [Description]
- ...

## Success Metrics
- [ ] Metric 1
- [ ] Metric 2

## Rollback Plan
[How to undo if needed]
```

---

**Workflow Owner:** Engineering Team  
**Last Updated:** December 2025  
**Version:** 1.0
