---
name: coupon-domain-expert
description: Domain expert for coupon business logic and multi-portal operations. Use for coupon lifecycle management, state machines, validation rules, NFC integration, payment processing (Stripe), fraud detection, white-label configuration, and complex coupon-specific business requirements across B2B, B2C, and C2C portals.
---

# Coupon Domain Expert

Specialized knowledge for coupon business logic and multi-portal operations.

## Coupon Lifecycle States

```python
from enum import Enum
from datetime import datetime
from typing import Optional

class CouponStatus(Enum):
    DRAFT = "draft"              # Created but not published
    ACTIVE = "active"            # Available for use
    RESERVED = "reserved"        # Temporarily held by user
    REDEEMED = "redeemed"       # Successfully used
    EXPIRED = "expired"          # Past expiration date
    SUSPENDED = "suspended"      # Temporarily disabled
    CANCELLED = "cancelled"      # Permanently disabled
    TRANSFERRED = "transferred"  # Moved to another user (C2C)

class CouponType(Enum):
    PERCENTAGE = "percentage"    # % off discount
    FIXED_AMOUNT = "fixed"      # Fixed $ off
    BOGO = "bogo"               # Buy one get one
    FREE_SHIPPING = "shipping"  # Free shipping
    BUNDLE = "bundle"           # Bundle discount
```

## State Machine Implementation

```python
from typing import Dict, Set, Optional
from dataclasses import dataclass

@dataclass
class CouponStateMachine:
    """Manage coupon state transitions with validation"""
    
    # Define valid state transitions
    TRANSITIONS: Dict[CouponStatus, Set[CouponStatus]] = {
        CouponStatus.DRAFT: {
            CouponStatus.ACTIVE,
            CouponStatus.CANCELLED
        },
        CouponStatus.ACTIVE: {
            CouponStatus.RESERVED,
            CouponStatus.REDEEMED,
            CouponStatus.EXPIRED,
            CouponStatus.SUSPENDED,
            CouponStatus.TRANSFERRED
        },
        CouponStatus.RESERVED: {
            CouponStatus.ACTIVE,      # Release reservation
            CouponStatus.REDEEMED,
            CouponStatus.EXPIRED
        },
        CouponStatus.SUSPENDED: {
            CouponStatus.ACTIVE,
            CouponStatus.CANCELLED
        },
        CouponStatus.REDEEMED: set(),      # Terminal state
        CouponStatus.EXPIRED: set(),       # Terminal state
        CouponStatus.CANCELLED: set(),     # Terminal state
        CouponStatus.TRANSFERRED: set()    # Terminal state
    }
    
    def can_transition(
        self,
        current: CouponStatus,
        target: CouponStatus
    ) -> bool:
        """Check if state transition is valid"""
        return target in self.TRANSITIONS.get(current, set())
    
    def transition(
        self,
        coupon: 'Coupon',
        target: CouponStatus,
        actor_id: str,
        reason: Optional[str] = None
    ) -> 'Coupon':
        """Execute state transition with audit trail"""
        if not self.can_transition(coupon.status, target):
            raise ValueError(
                f"Invalid transition: {coupon.status} -> {target}"
            )
        
        # Record transition in audit log
        audit_entry = {
            "coupon_id": coupon.id,
            "from_status": coupon.status.value,
            "to_status": target.value,
            "actor_id": actor_id,
            "timestamp": datetime.utcnow(),
            "reason": reason
        }
        
        # Update coupon
        coupon.status = target
        coupon.updated_at = datetime.utcnow()
        
        # Log to DynamoDB
        log_audit_event(audit_entry)
        
        return coupon
```

## Business Validation Rules

```python
from datetime import datetime, timedelta
from typing import List

class CouponValidator:
    """Validate coupon business rules"""
    
    @staticmethod
    def validate_creation(dto: CreateCouponDTO) -> List[str]:
        """Validate coupon creation rules"""
        errors = []
        
        # Discount validation
        if dto.discount <= 0:
            errors.append("Discount must be positive")
        
        if dto.type == CouponType.PERCENTAGE and dto.discount > 100:
            errors.append("Percentage discount cannot exceed 100%")
        
        if dto.type == CouponType.FIXED_AMOUNT and dto.discount > 10000:
            errors.append("Fixed discount cannot exceed $10,000")
        
        # Expiration validation
        min_duration = timedelta(hours=1)
        max_duration = timedelta(days=365)
        
        duration = dto.expires_at - datetime.utcnow()
        
        if duration < min_duration:
            errors.append("Coupon must be valid for at least 1 hour")
        
        if duration > max_duration:
            errors.append("Coupon validity cannot exceed 1 year")
        
        # Usage limits
        if dto.max_uses and dto.max_uses < 1:
            errors.append("Max uses must be at least 1")
        
        if dto.max_uses_per_user and dto.max_uses_per_user < 1:
            errors.append("Max uses per user must be at least 1")
        
        return errors
    
    @staticmethod
    def can_redeem(coupon: Coupon, user_id: str) -> tuple[bool, Optional[str]]:
        """Check if coupon can be redeemed by user"""
        # Status check
        if coupon.status != CouponStatus.ACTIVE:
            return False, f"Coupon is {coupon.status.value}"
        
        # Expiration check
        if datetime.utcnow() > coupon.expires_at:
            return False, "Coupon has expired"
        
        # Usage limit check
        if coupon.max_uses and coupon.current_uses >= coupon.max_uses:
            return False, "Coupon usage limit reached"
        
        # Per-user limit check
        if coupon.max_uses_per_user:
            user_usage = get_user_coupon_usage(coupon.id, user_id)
            if user_usage >= coupon.max_uses_per_user:
                return False, "User usage limit reached"
        
        # Minimum purchase check
        if coupon.min_purchase_amount:
            # This would be checked during checkout
            pass
        
        return True, None
```

## NFC Integration

```python
import hashlib
import hmac
from typing import Dict

class NFCCouponManager:
    """Manage NFC-based coupon operations"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    def generate_nfc_payload(self, coupon: Coupon) -> Dict[str, str]:
        """Generate secure NFC payload for coupon"""
        # Create payload
        payload = {
            "coupon_id": coupon.id,
            "merchant_id": coupon.merchant_id,
            "discount": str(coupon.discount),
            "type": coupon.type.value,
            "expires_at": coupon.expires_at.isoformat()
        }
        
        # Generate HMAC signature
        message = f"{payload['coupon_id']}:{payload['expires_at']}"
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        payload["signature"] = signature
        
        return payload
    
    def verify_nfc_payload(self, payload: Dict[str, str]) -> bool:
        """Verify NFC payload authenticity"""
        # Extract signature
        received_signature = payload.pop("signature", None)
        if not received_signature:
            return False
        
        # Recalculate signature
        message = f"{payload['coupon_id']}:{payload['expires_at']}"
        expected_signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        return hmac.compare_digest(received_signature, expected_signature)
    
    def write_to_nfc(self, coupon: Coupon) -> str:
        """Generate NFC NDEF message"""
        payload = self.generate_nfc_payload(coupon)
        
        # Format as NDEF text record
        ndef_message = {
            "records": [
                {
                    "recordType": "text",
                    "data": json.dumps(payload),
                    "encoding": "UTF-8",
                    "language": "en"
                }
            ]
        }
        
        return json.dumps(ndef_message)
```

## Payment Processing (Stripe)

```python
import stripe
from typing import Optional

class CouponPaymentProcessor:
    """Handle coupon-related payments via Stripe"""
    
    def __init__(self, stripe_key: str):
        stripe.api_key = stripe_key
    
    def create_payment_intent(
        self,
        coupon: Coupon,
        user_id: str,
        original_amount: int  # In cents
    ) -> stripe.PaymentIntent:
        """Create Stripe PaymentIntent with coupon discount"""
        # Calculate discounted amount
        discounted_amount = self._calculate_discount(
            original_amount,
            coupon
        )
        
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=discounted_amount,
            currency="usd",
            metadata={
                "coupon_id": coupon.id,
                "user_id": user_id,
                "original_amount": original_amount,
                "discount": original_amount - discounted_amount
            }
        )
        
        return intent
    
    def _calculate_discount(
        self,
        amount: int,
        coupon: Coupon
    ) -> int:
        """Calculate discounted amount"""
        if coupon.type == CouponType.PERCENTAGE:
            discount = int(amount * (coupon.discount / 100))
            return max(amount - discount, 0)
        
        elif coupon.type == CouponType.FIXED_AMOUNT:
            # Convert discount to cents
            discount_cents = int(coupon.discount * 100)
            return max(amount - discount_cents, 0)
        
        return amount
    
    def handle_webhook(self, event: Dict) -> Optional[str]:
        """Handle Stripe webhook events"""
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            coupon_id = payment_intent["metadata"]["coupon_id"]
            
            # Mark coupon as redeemed
            redeem_coupon(coupon_id, payment_intent["metadata"]["user_id"])
            
            return coupon_id
        
        return None
```

## Portal-Specific Logic

```python
class PortalCouponRules:
    """Portal-specific coupon business rules"""
    
    @staticmethod
    def b2b_rules(coupon: Coupon, company_id: str) -> bool:
        """B2B portal validation"""
        # Minimum bulk purchase
        if coupon.min_quantity and coupon.min_quantity < 10:
            return False
        
        # Corporate approval required for high-value
        if coupon.discount > 5000:  # $5000+
            return requires_approval(company_id)
        
        return True
    
    @staticmethod
    def b2c_rules(coupon: Coupon, user_id: str) -> bool:
        """B2C portal validation"""
        # Check user tier eligibility
        user_tier = get_user_tier(user_id)
        
        if coupon.min_tier and user_tier < coupon.min_tier:
            return False
        
        return True
    
    @staticmethod
    def c2c_rules(
        coupon: Coupon,
        seller_id: str,
        buyer_id: str
    ) -> bool:
        """C2C portal validation"""
        # Verify seller owns coupon
        if coupon.owner_id != seller_id:
            return False
        
        # Check both parties are verified
        if not (is_verified(seller_id) and is_verified(buyer_id)):
            return False
        
        # Escrow service required for high-value
        if coupon.value > 500:  # $500+
            return has_escrow_agreement(seller_id, buyer_id)
        
        return True
```

## Fraud Detection

```python
from typing import List, Tuple

class CouponFraudDetector:
    """Detect fraudulent coupon activity"""
    
    def check_suspicious_activity(
        self,
        user_id: str,
        coupon_id: str
    ) -> Tuple[bool, List[str]]:
        """Check for fraud indicators"""
        flags = []
        
        # Rapid redemption attempts
        recent_attempts = get_recent_redemption_attempts(user_id)
        if len(recent_attempts) > 10:  # 10 in last hour
            flags.append("Rapid redemption attempts")
        
        # Multiple accounts from same IP
        user_ips = get_user_ips(user_id)
        other_users = find_users_by_ips(user_ips)
        if len(other_users) > 5:
            flags.append("Multiple accounts from same IP")
        
        # Coupon value spike
        avg_redemption = get_user_avg_redemption_value(user_id)
        coupon_value = get_coupon_value(coupon_id)
        
        if coupon_value > avg_redemption * 5:
            flags.append("Unusually high value redemption")
        
        # Geolocation mismatch
        if not verify_geolocation(user_id, coupon_id):
            flags.append("Location mismatch")
        
        is_suspicious = len(flags) >= 2
        
        return is_suspicious, flags
    
    def apply_risk_mitigation(
        self,
        user_id: str,
        risk_level: str
    ) -> Dict:
        """Apply fraud prevention measures"""
        if risk_level == "high":
            return {
                "action": "block",
                "require_verification": True,
                "manual_review": True
            }
        
        elif risk_level == "medium":
            return {
                "action": "flag",
                "require_2fa": True,
                "limit_daily_redemptions": 5
            }
        
        return {"action": "allow"}
```

## White-Label Configuration

```python
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class PortalConfiguration:
    """White-label configuration per portal"""
    portal_type: str
    brand_name: str
    theme_colors: Dict[str, str]
    logo_url: str
    custom_domain: Optional[str]
    
    # Business rules
    max_discount_percentage: int
    max_discount_amount: float
    min_coupon_validity: int  # Days
    max_coupon_validity: int
    
    # Features
    allow_nfc: bool
    allow_c2c_trading: bool
    require_merchant_verification: bool
    enable_analytics: bool

# Portal configs
PORTAL_CONFIGS = {
    "b2b": PortalConfiguration(
        portal_type="b2b",
        brand_name="Mezzofy Business",
        theme_colors={"primary": "#1e40af", "accent": "#3b82f6"},
        logo_url="/assets/b2b-logo.png",
        custom_domain="business.mezzofy.com",
        max_discount_percentage=50,
        max_discount_amount=10000,
        min_coupon_validity=7,
        max_coupon_validity=365,
        allow_nfc=True,
        allow_c2c_trading=False,
        require_merchant_verification=True,
        enable_analytics=True
    ),
    # ... other portals
}
```

## Quality Checklist

- [ ] State machine transitions validated
- [ ] Business rules enforced
- [ ] NFC payload secured with HMAC
- [ ] Stripe integration tested
- [ ] Fraud detection active
- [ ] Portal-specific rules applied
- [ ] Audit trail logged
- [ ] White-label configs respected
- [ ] Expiration handling automated
- [ ] Usage limits tracked
