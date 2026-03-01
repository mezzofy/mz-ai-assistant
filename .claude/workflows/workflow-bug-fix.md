---
name: workflow-bug-fix
description: Bug fix and hotfix workflow specialist for handling production defects and critical issues. Use when production systems have incorrect behavior, errors, performance problems, or critical failures. Follows a rapid response process prioritized by severity with emphasis on quick resolution, minimal risk, and comprehensive testing to prevent regressions.
---

# Workflow: Bug Fix

Rapid response workflow for production defects and critical issues.

## Overview

This workflow handles **defects in production systems** where something is broken, incorrect, or not working as designed.

**Key Characteristics:**
- ⚡ Speed-focused (especially for critical bugs)
- 🎯 Minimal scope (fix only the bug)
- 🔒 Risk-averse (no enhancements)
- ✅ Regression testing mandatory
- 📊 Root cause analysis required

## Bug Severity Classification

### P0 - Critical (Fix within 4 hours)

**System Down or Data Loss:**
- Production system completely unavailable
- Data corruption or loss
- Security breach
- Payment processing failures
- Critical functionality blocked for all users

**Response:**
- Immediate all-hands
- Hotfix directly to production
- Post-mortem required

**Examples:**
- Database connection lost
- API returning 500 errors
- All coupon redemptions failing
- User data exposed

---

### P1 - High (Fix within 24 hours)

**Core Feature Broken:**
- Major functionality not working
- Affects large portion of users
- Workaround exists but poor UX
- Business impact significant

**Response:**
- Priority shift for team
- Fast-track through QA
- Deploy in next release window

**Examples:**
- Coupon search returns no results
- NFC redemption fails intermittently
- Email notifications not sending
- Mobile app crashes on launch

---

### P2 - Medium (Fix within 1 week)

**Edge Case or Minor Issue:**
- Affects small portion of users
- Workaround available
- Non-critical functionality
- Business impact limited

**Response:**
- Include in current sprint
- Normal testing process
- Deploy with next batch

**Examples:**
- Incorrect date format in specific timezone
- UI alignment issue on specific screen size
- Error message not localized
- Minor validation bug

---

### P3 - Low (Fix when convenient)

**Cosmetic or Nice-to-Have:**
- Visual issue only
- Rare edge case
- Minimal user impact
- No business impact

**Response:**
- Backlog for future sprint
- May be bundled with other fixes

**Examples:**
- Button color slightly off
- Typo in help text
- Console warning (no user impact)
- Minor logging improvement

---

## Phase 1: Bug Triage (Minutes to Hours)

**Owner:** Engineering + Support  
**Duration:** 15 min (P0), 1 hour (P1), 1 day (P2-P3)

### Objectives

Understand the bug, assess severity, and assign ownership immediately.

### Activities

#### 1.1 Initial Report

```markdown
# Bug Report: BUG-XXX

## Reported By
- **Reporter:** [Name/User ID]
- **Source:** [Support Ticket/Internal/User Report]
- **Date:** [YYYY-MM-DD HH:MM]
- **Environment:** [Production/Staging]

## Severity Assessment
- **Initial Severity:** [P0/P1/P2/P3]
- **Affects:** [All users / X% / Specific portal / Edge case]
- **Business Impact:** [Critical / High / Medium / Low]

## Bug Description
**What's broken:**
Coupon redemption fails with "Invalid signature" error

**Expected behavior:**
User taps NFC, coupon redeems successfully

**Actual behavior:**
Error message appears, coupon not redeemed

**Frequency:**
- 100% reproducible
- Affects all NFC redemptions
- Started 2 hours ago (12:00 PM UTC)

## Steps to Reproduce
1. Open B2C mobile app
2. Navigate to active coupon
3. Tap "Redeem with NFC"
4. Hold phone to NFC reader
5. Error: "Invalid signature"

## Environment Details
- **Platform:** iOS 17.2, Android 13
- **App Version:** 2.1.0
- **API Version:** v2.0
- **Affected Portals:** B2C, C2C
- **Started:** 2024-12-31 12:00 UTC
```

#### 1.2 Severity Validation

```markdown
## Severity Decision Matrix

### Questions:
1. Is production down? YES → P0
2. Is data at risk? YES → P0
3. Is core feature broken? YES → P1
4. Are all users affected? YES → P1
5. Is there a workaround? NO → Increase priority
6. Is business impacted? YES → Increase priority

### This Bug:
- Production: ✅ UP
- Data: ✅ Safe
- Core feature: ❌ BROKEN (NFC redemption)
- All users: ✅ YES (all NFC redemptions)
- Workaround: ⚠️ Manual code entry works
- Business impact: 🔴 HIGH (holiday shopping season)

**Final Severity:** P1 (High) → Fix within 24 hours
```

#### 1.3 Initial Investigation

```bash
# Quick checks for immediate root cause

# Check recent deployments
git log --oneline --since="4 hours ago"
# Recent commit: "feat: update NFC signature algorithm"

# Check error logs
aws logs tail /aws/lambda/coupon-redemption --since 2h
# Error: "HMAC signature mismatch"

# Check monitoring
aws cloudwatch get-metric-statistics \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=coupon-redemption
# Spike at 12:00 PM UTC

# Root cause suspected: Recent NFC signature algorithm change
```

#### 1.4 Assignment

```markdown
## Bug Assignment

- **Assigned To:** [Engineer Name]
- **Backup:** [Senior Engineer]
- **Notified:** Product, Support, CTO (for P0/P1)
- **ETA:** [Timeline based on severity]
- **Status Channel:** #incident-bug-xxx (for P0/P1)
```

### Claude Code Usage (Phase 1)

✅ **Generate:**
- Bug report templates
- Severity assessment checklists
- Initial investigation queries

❌ **Do NOT:**
- Change severity without team agreement
- Skip investigation
- Assign without engineer confirmation

**Example Prompt:**
```
"workflow-bug-fix, help me triage this bug:

Issue: NFC coupon redemption failing with 'Invalid signature'
Started: 2 hours ago
Affects: All NFC redemptions on mobile app
Recent change: Updated NFC signature algorithm yesterday

Generate:
1. Severity assessment
2. Initial investigation checklist
3. Rollback decision tree"
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Bug Report** (BUG-XXX)
   ```
   /documents/bugs/BUG-XXX/
   └── bug-xxx-report-v1.0.md
   ```

2. **Severity Classification**
   - P0/P1/P2/P3 assigned
   - Team notified

3. **Assignment**
   - Engineer assigned
   - ETA set

❌ **Quality Gate:**
**STOP: No Phase 2 without severity + assignment**

---

## Phase 2: Root Cause Analysis (Hours to Days)

**Owner:** Assigned Engineer  
**Duration:** 1-4 hours (P0/P1), 1-2 days (P2/P3)

### Objectives

Find the **exact cause** of the bug, not just symptoms.

### Activities

#### 2.1 Reproduce the Bug

```markdown
## Reproduction Steps

### Local Environment
1. Checkout main branch
2. Run local backend + frontend
3. Attempt NFC redemption
4. Result: Works correctly ✅

### Staging Environment
1. Deploy to staging
2. Attempt NFC redemption
3. Result: Works correctly ✅

### Production Environment
1. Check production logs
2. Attempt NFC redemption with production data
3. Result: FAILS ❌

**Conclusion:** Issue specific to production environment
```

#### 2.2 Investigate Logs

```bash
# Backend logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/coupon-redemption \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '4 hours ago' +%s)000

# Output:
# "HMAC verification failed: expected=abc123, received=def456"
# "NFC signature algorithm mismatch"
# "Fallback to old algorithm failed"

# Database queries
SELECT signature_algorithm, COUNT(*) 
FROM coupons 
GROUP BY signature_algorithm;

# Results:
# SHA256: 10,000 coupons (old)
# SHA512: 50 coupons (new, created today)
```

#### 2.3 Identify Root Cause

```markdown
## Root Cause Analysis

### The Problem
NFC signature verification failing for all redemptions

### The Cause
1. Yesterday: Deployed new code using SHA512 for signatures
2. New code generates SHA512 signatures for new coupons
3. Old code (mobile app, not updated) expects SHA256 signatures
4. Mobile app v2.0 still uses SHA256 verification
5. Server sends SHA512, app verifies with SHA256 → MISMATCH

### Why It Happened
- Backend updated without mobile app coordination
- No backward compatibility check
- Insufficient testing of existing app versions
- Missing feature flag for gradual rollout

### Why It Wasn't Caught
- E2E tests only tested latest app + latest backend
- No tests for old app + new backend compatibility
- Staging doesn't have production app distribution
- No canary deployment used

### Contributing Factors
- Holiday deployment during high-traffic period
- Rushed deployment without full QA
- Documentation didn't specify app version compatibility
```

### Claude Code Usage (Phase 2)

✅ **Generate:**
- Log query scripts
- Root cause analysis templates
- Debugging checklist

❌ **Do NOT:**
- Jump to solutions before understanding cause
- Skip reproduction
- Assume cause without evidence

**Example Prompt:**
```
"workflow-bug-fix, help analyze this root cause:

Symptoms:
- NFC redemption failing with signature mismatch
- Started after backend deployment yesterday
- Affects all users

Evidence:
- Backend using SHA512 signatures
- Mobile app v2.0 using SHA256 verification
- Mismatch causing failures

Generate:
1. Complete root cause analysis
2. Why this wasn't caught
3. Prevention measures for future"
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Root Cause Document**
   ```
   /documents/bugs/BUG-XXX/
   └── root-cause-analysis-v1.0.md
   ```

2. **Reproduction Steps** (verified)

3. **Fix Strategy** (preliminary)

❌ **Quality Gate:**
**STOP: No Phase 3 without root cause identified**

---

## Phase 3: Fix Development (Hours to Days)

**Owner:** Assigned Engineer  
**Duration:** 2-8 hours (P0/P1), 1-3 days (P2/P3)

### Objectives

Develop **minimal, safe fix** that addresses root cause without introducing new issues.

### Fix Strategy Selection

#### Option 1: Rollback (Fastest, Safest for P0)

**When to use:**
- Recent deployment caused issue
- Old version was working
- No data corruption
- Quick restoration needed

```bash
# Rollback to previous version
git revert abc123  # Revert problematic commit
cdk deploy BackendStack --version v2.0.0

# Or use feature flag
curl -X POST https://api.mezzofy.com/admin/feature-flags \
  -d '{"use_sha512_signatures": false}'
```

**Pros:**
- ✅ Instant fix
- ✅ Known working state
- ✅ Low risk

**Cons:**
- ❌ Loses any other fixes in that release
- ❌ Temporary solution only

---

#### Option 2: Backward Compatible Fix (Recommended for P1)

**When to use:**
- Can't rollback (data migration done)
- Need to support old clients
- Time allows (P1, P2)

```python
# Add backward compatibility
class SignatureVerifier:
    def verify(self, payload: str, signature: str, algorithm: str = None):
        """Verify signature with fallback to old algorithm"""
        
        # Try new algorithm (SHA512)
        if self._verify_sha512(payload, signature):
            return True
        
        # Fallback to old algorithm (SHA256) for backward compat
        if self._verify_sha256(payload, signature):
            logger.warning(f"Used SHA256 fallback for signature verification")
            return True
        
        # Both failed
        raise SignatureError("Invalid signature")
    
    def _verify_sha512(self, payload, signature):
        expected = hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    
    def _verify_sha256(self, payload, signature):
        expected = hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
```

**Pros:**
- ✅ Supports old and new clients
- ✅ No breaking changes
- ✅ Safe gradual migration

**Cons:**
- ❌ More complex
- ❌ Temporary backward compat code

---

#### Option 3: Hotfix (For Edge Cases)

**When to use:**
- Specific condition causing issue
- Can patch without full deployment
- Minimal code change

```python
# Quick patch for specific issue
if coupon.created_at < datetime(2024, 12, 30):
    # Old coupons use SHA256
    algorithm = 'sha256'
else:
    # New coupons use SHA512
    algorithm = 'sha512'

verify_signature(payload, signature, algorithm)
```

**Pros:**
- ✅ Quick implementation
- ✅ Targeted fix

**Cons:**
- ❌ Technical debt
- ❌ Needs cleanup later

---

### Implementation

```python
# Fix for BUG-XXX: NFC Signature Verification Failure

# services/nfc_service.py
class NFCService:
    def verify_coupon_signature(
        self,
        coupon_id: str,
        payload: str,
        signature: str
    ) -> bool:
        """
        Verify NFC signature with backward compatibility.
        
        BUG-XXX Fix: Support both SHA256 (old) and SHA512 (new)
        """
        coupon = self.repo.get_by_id(coupon_id)
        
        # Determine algorithm based on coupon creation date
        # Coupons created before SHA512 deployment use SHA256
        sha512_deployment = datetime(2024, 12, 30, 12, 0, 0)
        
        if coupon.created_at < sha512_deployment:
            # Old coupon: use SHA256
            algorithm = 'sha256'
        else:
            # New coupon: try SHA512 first, fallback to SHA256
            if self._verify_with_algorithm(payload, signature, 'sha512'):
                return True
            # Fallback for clients not yet updated
            algorithm = 'sha256'
        
        return self._verify_with_algorithm(payload, signature, algorithm)
    
    def _verify_with_algorithm(
        self,
        payload: str,
        signature: str,
        algorithm: str
    ) -> bool:
        """Verify signature using specified algorithm"""
        hash_func = hashlib.sha512 if algorithm == 'sha512' else hashlib.sha256
        
        expected = hmac.new(
            self.secret.encode(),
            payload.encode(),
            hash_func
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
```

### Testing

```python
# tests/test_bug_xxx_signature_verification.py
import pytest
from datetime import datetime
from services.nfc_service import NFCService

class TestBugXXXSignatureFix:
    def test_old_coupon_uses_sha256(self):
        """Old coupons (pre-deployment) use SHA256"""
        coupon = create_test_coupon(
            created_at=datetime(2024, 12, 29)  # Before deployment
        )
        
        # Generate SHA256 signature (old algorithm)
        signature = generate_sha256_signature(coupon)
        
        # Should verify successfully
        assert nfc_service.verify_coupon_signature(
            coupon.id,
            coupon.payload,
            signature
        )
    
    def test_new_coupon_accepts_sha512(self):
        """New coupons accept SHA512 signatures"""
        coupon = create_test_coupon(
            created_at=datetime(2024, 12, 31)  # After deployment
        )
        
        # Generate SHA512 signature (new algorithm)
        signature = generate_sha512_signature(coupon)
        
        # Should verify successfully
        assert nfc_service.verify_coupon_signature(
            coupon.id,
            coupon.payload,
            signature
        )
    
    def test_new_coupon_accepts_sha256_fallback(self):
        """New coupons accept SHA256 for backward compatibility"""
        coupon = create_test_coupon(
            created_at=datetime(2024, 12, 31)
        )
        
        # Generate SHA256 signature (old app)
        signature = generate_sha256_signature(coupon)
        
        # Should still verify (backward compatibility)
        assert nfc_service.verify_coupon_signature(
            coupon.id,
            coupon.payload,
            signature
        )
    
    def test_invalid_signature_rejected(self):
        """Invalid signatures rejected"""
        coupon = create_test_coupon()
        
        # Invalid signature
        with pytest.raises(SignatureError):
            nfc_service.verify_coupon_signature(
                coupon.id,
                coupon.payload,
                "invalid_signature"
            )
    
    def test_regression_all_existing_coupons_work(self):
        """Regression: All existing coupons still work"""
        # Test sample of production coupons
        for coupon_id in production_coupon_sample:
            coupon = get_production_coupon(coupon_id)
            signature = get_original_signature(coupon)
            
            # All should verify
            assert nfc_service.verify_coupon_signature(
                coupon.id,
                coupon.payload,
                signature
            )
```

### Claude Code Usage (Phase 3)

✅ **Generate:**
- Fix implementation code
- Test cases for fix
- Regression test suite

❌ **Do NOT:**
- Add features while fixing bugs
- Make unrelated changes
- Skip testing

**Example Prompt:**
```
"workflow-bug-fix, implement fix for signature verification bug.

Root cause:
- Backend using SHA512, mobile app using SHA256
- Need backward compatibility

Requirements:
- Support both SHA256 and SHA512
- No breaking changes
- Minimal code change
- Comprehensive tests

Generate:
1. Backward compatible implementation
2. Unit tests
3. Regression tests"
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Fix Implementation**
   - Code changes minimal
   - Only addresses bug
   - No new features

2. **Tests Passing**
   - Unit tests for fix
   - Regression tests
   - All existing tests still pass

3. **Code Review**
   - Peer reviewed (required for P0/P1)
   - Senior engineer approved

❌ **Quality Gate:**
**STOP: No Phase 4 without tests passing + review**

---

## Phase 4: Deployment (Minutes to Hours)

**Owner:** Engineering  
**Duration:** 15 min (P0 hotfix), 2 hours (P1), next release (P2/P3)

### 4.1 Create Release Notes (REQUIRED for P0/P1/P2)

**All production deployments must have release notes for tracking and communication.**

**Note:** P0 hotfixes may create minimal release notes immediately after deployment due to urgency, but must be completed within 2 hours.

```markdown
# Release Notes: BUG-[NUMBER] - [BUG TITLE]

**Release Date:** [YYYY-MM-DD HH:MM UTC]  
**Bug Ticket:** BUG-[NUMBER]  
**Severity:** P0 / P1 / P2 / P3  
**Version:** [X.Y.Z]  
**Type:** Hotfix / Bug Fix  
**Affected Components:** [List components]

---

## 📋 Summary

Brief description of the bug and the fix.

Example: Fixed critical issue where NFC coupon redemptions were failing with "Invalid signature" error due to signature algorithm mismatch between backend and mobile app.

---

## 🐛 Bug Description

### Issue
- **What was broken:** NFC signature verification failing
- **Symptom:** "Invalid signature" error on redemption
- **Started:** 2024-12-31 12:00 PM UTC
- **Impact:** 100% of NFC redemptions affected
- **Affected Users:** All mobile app users (iOS & Android)

### Root Cause
Backend updated to SHA512 signature algorithm without mobile app coordination. Mobile app v2.0 still using SHA256 verification, causing signature mismatches.

---

## ✅ Fix Applied

### Solution
Added backward compatibility to signature verification:
1. Try SHA512 verification first
2. If fails, fallback to SHA256 verification
3. Log warning when SHA256 fallback used
4. Allows gradual mobile app migration

### Technical Changes
- **File Modified:** `services/nfc_service.py`
- **Lines Changed:** 45 lines
- **Method:** `verify_coupon_signature()`
- **Strategy:** Backward compatible fix (no breaking changes)

### Code Diff Summary
```python
# Before: Only SHA512
verify_with_sha512(payload, signature)

# After: SHA512 with SHA256 fallback
if not verify_with_sha512(payload, signature):
    return verify_with_sha256(payload, signature)  # Fallback
```

---

## 🚀 Deployment Details

### Deployment Type
- **P0:** Emergency hotfix (deployed immediately)
- **P1:** Fast-track (staged → prod in 2 hours)
- **P2:** Next release cycle

### Deployment Steps
1. Code review: 15 minutes (P0) / 1 hour (P1)
2. Testing: Critical tests only (P0) / Full test suite (P1)
3. Staging deployment: Skipped (P0) / Required (P1)
4. Production deployment: Immediate (P0) / After staging (P1)
5. Monitoring: 30 minutes intensive (P0) / 2 hours (P1)

### Actual Timeline
- **Bug Reported:** 12:15 PM UTC
- **Root Cause Identified:** 12:45 PM UTC
- **Fix Implemented:** 1:30 PM UTC
- **Tests Passed:** 2:00 PM UTC
- **Deployed to Production:** 3:00 PM UTC
- **Verified Resolved:** 3:30 PM UTC
- **Total Time:** 3 hours 15 minutes

---

## 📊 Impact Assessment

### Before Fix
- **Error Rate:** 100% of NFC redemptions
- **Affected Users:** ~5,000 attempted redemptions
- **Support Tickets:** 47 tickets in 2 hours
- **Business Impact:** Critical - no NFC redemptions possible

### After Fix
- **Error Rate:** 0% (returned to normal)
- **Successful Redemptions:** 100% success rate restored
- **Support Tickets:** Dropped to baseline
- **Business Impact:** Resolved - full functionality restored

---

## 🧪 Testing Performed

### Before Deployment
- [x] Unit tests for fix (5 tests added)
- [x] Regression tests (existing NFC tests)
- [x] Manual testing on dev environment
- [x] Backward compatibility verified

### After Deployment
- [x] Smoke test (old mobile app + new backend)
- [x] Smoke test (new mobile app + new backend)
- [x] Production monitoring (30 minutes)
- [x] User acceptance (support feedback)

---

## ⚠️ Breaking Changes

**None** - This is a backward compatible fix.

- Old mobile apps (SHA256): Still work
- New mobile apps (SHA512): Still work
- No user action required
- No data migration needed

---

## 📚 Related Documentation

- [x] Post-mortem created (P0/P1 only): See POST_MORTEM.md
- [x] Runbook updated with prevention steps
- [x] Incident report filed: INC-2024-456
- [x] Knowledge base article created

---

## 🔄 Rollback Plan

If issues detected:
1. Revert to previous version: v2.0.1
2. Command: `cdk deploy BackendStack --version v2.0.1`
3. Rollback time: 5 minutes
4. No data loss (backward compatible)

---

## 🎯 Success Criteria

- [x] Bug resolved (no more signature errors)
- [x] No new issues introduced
- [x] Error rate back to normal
- [x] User feedback positive
- [x] Support tickets resolved

---

## 🔍 Prevention Measures

### Immediate Actions Taken
- Added backward compatibility tests to CI/CD
- Updated deployment checklist
- Improved staging testing procedures

### Long-term Improvements (from Post-Mortem)
- Implement canary deployments
- Add feature flags for algorithm changes
- Create compatibility matrix (backend × mobile versions)
- Automated compatibility testing across versions

---

## 👥 Team

- **Reported By:** Support Team
- **Triaged By:** [Engineer Name]
- **Fixed By:** [Engineer Name]
- **Reviewed By:** [Senior Engineer Name]
- **Deployed By:** [Engineer Name]
- **Verified By:** QA Team

---

## 📞 Communication

### Stakeholders Notified
- [x] Engineering team (#incidents Slack)
- [x] Product team (email)
- [x] Support team (briefing call)
- [x] Users (status page update)

### Communication Timeline
- 12:15 PM: Bug reported in #incidents
- 12:45 PM: Root cause identified, fix ETA shared
- 3:00 PM: Hotfix deployed, monitoring started
- 3:30 PM: All-clear posted, incident closed

---

## 📅 Timeline

| Time | Event |
|------|-------|
| 12:00 PM | Backend deployment (SHA512 algorithm) |
| 12:15 PM | First user reports received |
| 12:30 PM | Bug triaged as P0 (critical) |
| 12:45 PM | Root cause identified |
| 1:30 PM | Fix implemented |
| 2:00 PM | Tests passing |
| 3:00 PM | Hotfix deployed to production |
| 3:30 PM | Verified resolved |
| 4:00 PM | Incident closed |

---

## 🔗 Related Issues

- **Similar Past Issue:** BUG-234 (API version mismatch, 2024-09)
- **Related Enhancement:** FEATURE-456 (Mobile app v2.1 update)
- **Follow-up Work:** CR-130 (Remove SHA256 support after migration)

---

**Approved By:**
- [ ] Engineering Lead: [Name] - [Date]
- [ ] On-call Engineer: [Name] - [Date]

**Published By:** [Name]  
**Publication Date:** [YYYY-MM-DD HH:MM UTC]
```

### Using AI to Generate Release Notes

```
"technical-writer, create release notes for BUG-456 hotfix.

Bug: NFC signature verification failing
Severity: P0
Root cause: SHA512/SHA256 algorithm mismatch
Fix: Added backward compatibility
Impact: 5000 users, 3 hour outage
Deployment: Emergency hotfix

Generate complete release notes."
```

---

### 4.2 Deployment Strategy by Severity

#### P0 - Emergency Hotfix

```bash
# Immediate deployment to production

# 1. Fast-track code review (< 15 min)
# 2. Run critical tests only
pytest tests/test_bug_xxx_*.py -v

# 3. Deploy directly to production
cdk deploy BackendStack --require-approval never

# 4. Monitor intensely for 30 minutes
watch -n 10 'aws cloudwatch get-metric-statistics ...'

# 5. Communicate to team
# Post in #incidents: "Hotfix deployed for BUG-XXX"
```

#### P1 - Fast-Track

```bash
# Deploy to staging first, then production

# 1. Deploy to staging
cdk deploy BackendStack --profile staging

# 2. Smoke test on staging (30 min)
./scripts/smoke-test-staging.sh

# 3. Deploy to production
cdk deploy BackendStack --profile production

# 4. Monitor for 2 hours
# 5. Announce in #releases
```

#### P2/P3 - Normal Release

```bash
# Include in next regular release

# 1. Merge to develop branch
git checkout develop
git merge fix/bug-xxx

# 2. Deploy with next batch
# Wait for next release window (e.g., Tuesday/Thursday)

# 3. Include in release notes
```

### Monitoring Post-Deployment

```markdown
## Post-Deployment Checklist

### Immediate (15 minutes)
- [ ] Error rate back to normal
- [ ] No new errors introduced
- [ ] Core functionality working
- [ ] Users can redeem coupons via NFC

### Short-term (2 hours)
- [ ] Redemption success rate restored
- [ ] Performance metrics normal
- [ ] No increased support tickets
- [ ] Monitoring dashboard green

### Long-term (24 hours)
- [ ] No regressions detected
- [ ] User feedback positive
- [ ] Bug confirmed resolved
- [ ] Close incident
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Release Notes** (MANDATORY for P0/P1/P2) ⭐
   ```
   /documents/bugs/BUG-XXX/
   └── release-notes-bug-xxx-v1.0.md
   ```
   - P0: Can be created within 2 hours after deployment
   - P1/P2: Must be created before deployment
   - Published to team wiki/incident log

2. **Deployed Fix**
   - Production updated
   - Bug resolved

3. **Monitoring Data**
   - Error rate normalized
   - Metrics healthy

4. **Communication**
   - Team notified
   - Users informed (if needed)

❌ **Quality Gate:**
**STOP: Rollback if new issues detected**

---

## Phase 5: Post-Mortem (P0/P1 only)

**Owner:** Engineering Lead  
**Duration:** 1-2 days after fix  
**Required for:** P0 and P1 bugs only

### Objectives

Learn from the incident to prevent future occurrences.

### Post-Mortem Template

```markdown
# Post-Mortem: BUG-XXX - NFC Signature Verification Failure

## Incident Summary
- **Date:** 2024-12-31
- **Duration:** 4 hours (12:00 PM - 4:00 PM UTC)
- **Severity:** P1
- **Impact:** All NFC redemptions failed
- **Users Affected:** ~5,000 users attempted NFC redemption

## Timeline
- **12:00 PM:** Deployment of new signature algorithm
- **12:15 PM:** First user reports received
- **12:30 PM:** Bug triaged as P1
- **12:45 PM:** Root cause identified
- **2:00 PM:** Fix implemented and tested
- **3:00 PM:** Hotfix deployed to production
- **4:00 PM:** Verified resolved, monitoring continues

## Root Cause
Backend deployed SHA512 signature algorithm without coordinating mobile app update. Mobile app v2.0 still using SHA256 verification, causing signature mismatches.

## What Went Well
✅ Quick triage and severity assessment
✅ Root cause identified within 30 minutes
✅ Communication channels worked well
✅ Rollback plan was available

## What Went Wrong
❌ No backward compatibility testing
❌ Deployed during high-traffic period
❌ No canary deployment used
❌ Insufficient coordination between backend/mobile teams

## Action Items

### Immediate (This Week)
- [ ] Add backward compatibility tests to CI/CD
- [ ] Document mobile app version compatibility
- [ ] Add pre-deployment checklist

### Short-term (This Month)
- [ ] Implement canary deployments
- [ ] Add feature flags for algorithm changes
- [ ] Create compatibility matrix (backend x mobile versions)

### Long-term (This Quarter)
- [ ] Automated compatibility testing across versions
- [ ] Improve deployment coordination process
- [ ] Incident response training

## Prevention Measures
1. **Testing:** Add tests for old app + new backend
2. **Process:** Require cross-team review for breaking changes
3. **Deployment:** Use feature flags for algorithm changes
4. **Monitoring:** Alert on signature verification failures

## Lessons Learned
- Always test backward compatibility
- Coordinate deployments across platforms
- Use feature flags for risky changes
- Avoid deployments during peak traffic
```

### Outputs & Gates

✅ **Required Deliverables:**

1. **Post-Mortem Document**
   ```
   /documents/bugs/BUG-XXX/
   └── post-mortem-v1.0.md
   ```

2. **Action Items**
   - Assigned owners
   - Due dates
   - Tracked in backlog

3. **Team Review**
   - Meeting held
   - Lessons shared

---

## Bug Fix Checklist

### All Bugs
- [ ] Bug report created
- [ ] Severity assigned
- [ ] Engineer assigned
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] Tests passing (including regression)
- [ ] Code reviewed
- [ ] Deployed successfully
- [ ] Monitoring confirms resolution

### P0/P1 Only
- [ ] Incident channel created
- [ ] Stakeholders notified
- [ ] Rollback plan tested
- [ ] Post-deployment monitoring (2+ hours)
- [ ] Post-mortem completed
- [ ] Action items tracked

### Technical Debt
- [ ] Document any technical debt introduced
- [ ] Create follow-up ticket for cleanup
- [ ] Schedule debt paydown

---

## Critical Rules for Bug Fixes

### Do's ✅
- Fix the bug, nothing else
- Test regression thoroughly
- Have rollback plan ready
- Monitor after deployment
- Document root cause
- Learn from incidents

### Don'ts ❌
- Don't add features
- Don't refactor unrelated code
- Don't skip tests
- Don't deploy without review (P0/P1)
- Don't ignore root cause
- Don't forget post-mortem (P0/P1)

### Emergency Contacts

```markdown
## Escalation Path

**P0 Incident:**
1. On-call engineer (PagerDuty)
2. Engineering Lead
3. CTO
4. CEO (if business-critical)

**Contact Info:**
- Slack: #incidents
- PagerDuty: +1-XXX-XXX-XXXX
- Email: incidents@mezzofy.com
```

---

**Workflow Owner:** Engineering Team  
**Last Updated:** December 2025  
**Version:** 1.0
