---
name: template-architect
description: Template architect specialist for extracting and managing reusable UI templates across multiple portals. Use for component abstraction, template versioning, portal-agnostic design, shared component libraries, design system consistency, and managing template dependencies across B2B, B2C, C2C, Admin, Merchant, Partnership, and Customer portals.
---

# Template Architect

Design and manage reusable templates for consistent multi-portal architecture.

## Core Responsibilities

1. **Template Extraction** - Identify reusable patterns across portals
2. **Component Abstraction** - Create portal-agnostic components
3. **Version Management** - Semantic versioning for templates
4. **Dependency Management** - Track template usage across portals
5. **Migration Guides** - Document breaking changes
6. **Template Documentation** - Usage guidelines and examples

## Template Extraction Process

### 1. Identify Common Patterns

```markdown
## Cross-Portal Pattern Analysis

### Pattern: Coupon Card Display

**Usage Across Portals**:
- ✅ B2B: Bulk coupon preview cards
- ✅ B2C: Marketplace coupon cards
- ✅ C2C: Trading listing cards
- ✅ Merchant: Created coupon preview
- ✅ Customer: Saved coupons display

**Common Elements**:
- Merchant logo/branding
- Discount amount/percentage
- Title and description
- Expiration date
- Action button (CTA)
- Status indicator

**Portal-Specific Variations**:
- B2B: Shows bulk pricing, quantity available
- B2C: Shows user ratings, redemption count
- C2C: Shows seller info, listing price
- Merchant: Shows creation date, edit controls
- Customer: Shows saved date, reminder toggle

**Extraction Decision**: ✅ EXTRACT
- High reuse (5/7 portals)
- Core business entity (coupon)
- Manageable variation (props-based)
```

### 2. Template Hierarchy

```
templates/shared/
├── core/                    # Fundamental building blocks
│   ├── Button/
│   ├── Card/
│   ├── Modal/
│   └── Input/
├── composite/               # Combined components
│   ├── CouponCard/
│   ├── UserProfile/
│   ├── SearchBar/
│   └── Navigation/
├── layouts/                 # Page layouts
│   ├── DashboardLayout/
│   ├── MarketplaceLayout/
│   └── AuthLayout/
└── patterns/                # Behavioral patterns
    ├── InfiniteScroll/
    ├── DataTable/
    └── FilterPanel/
```

## Component Abstraction

### Portal-Agnostic Base Component

```typescript
// templates/shared/composite/CouponCard/CouponCard.tsx

import { ReactNode } from 'react';
import { Card } from '@/templates/shared/core/Card';
import { Button } from '@/templates/shared/core/Button';

export interface CouponCardConfig {
  // Core coupon data (portal-agnostic)
  id: string;
  title: string;
  discount: number | string;
  discountType: 'percentage' | 'fixed' | 'bogo';
  expiresAt: Date;
  merchantName: string;
  merchantLogo?: string;
  
  // Visual customization
  variant?: 'default' | 'featured' | 'compact';
  theme?: 'light' | 'dark';
  
  // Portal-specific slots
  headerSlot?: ReactNode;      // Extra content in header
  footerSlot?: ReactNode;       // Extra content in footer
  badgeSlot?: ReactNode;        // Custom badges/indicators
  metadataSlot?: ReactNode;     // Portal-specific metadata
  
  // Behavior
  onAction?: () => void;
  actionLabel?: string;
  isDisabled?: boolean;
}

export const CouponCard: React.FC<CouponCardConfig> = ({
  id,
  title,
  discount,
  discountType,
  expiresAt,
  merchantName,
  merchantLogo,
  variant = 'default',
  theme = 'light',
  headerSlot,
  footerSlot,
  badgeSlot,
  metadataSlot,
  onAction,
  actionLabel = 'View Details',
  isDisabled = false,
}) => {
  return (
    <Card variant={variant} theme={theme} className="coupon-card">
      {/* Portal-specific header content */}
      {headerSlot && (
        <div className="coupon-card__header-slot">
          {headerSlot}
        </div>
      )}
      
      {/* Core content (always present) */}
      <div className="coupon-card__core">
        {merchantLogo && (
          <img 
            src={merchantLogo} 
            alt={merchantName}
            className="coupon-card__merchant-logo"
          />
        )}
        
        <div className="coupon-card__discount">
          {formatDiscount(discount, discountType)}
        </div>
        
        {badgeSlot && (
          <div className="coupon-card__badges">
            {badgeSlot}
          </div>
        )}
        
        <h3 className="coupon-card__title">{title}</h3>
        
        <div className="coupon-card__metadata">
          <span>Expires: {formatDate(expiresAt)}</span>
          {metadataSlot}
        </div>
      </div>
      
      {/* Portal-specific footer content */}
      {footerSlot && (
        <div className="coupon-card__footer-slot">
          {footerSlot}
        </div>
      )}
      
      {/* Action button */}
      {onAction && (
        <Button
          onClick={onAction}
          disabled={isDisabled}
          variant="primary"
          fullWidth
        >
          {actionLabel}
        </Button>
      )}
    </Card>
  );
};
```

### Portal-Specific Implementations

```typescript
// packages/app-b2b/src/components/B2BCouponCard.tsx

import { CouponCard, CouponCardConfig } from '@/templates/shared/composite/CouponCard';
import { BulkPricingBadge } from './BulkPricingBadge';
import { QuantityIndicator } from './QuantityIndicator';

interface B2BCouponData extends CouponCardConfig {
  bulkPrice: number;
  quantityAvailable: number;
  minimumOrder: number;
}

export const B2BCouponCard: React.FC<B2BCouponData> = ({
  bulkPrice,
  quantityAvailable,
  minimumOrder,
  ...baseProps
}) => {
  return (
    <CouponCard
      {...baseProps}
      variant="default"
      headerSlot={
        <BulkPricingBadge price={bulkPrice} minOrder={minimumOrder} />
      }
      metadataSlot={
        <QuantityIndicator available={quantityAvailable} />
      }
      actionLabel="Add to Cart"
    />
  );
};
```

```typescript
// packages/app-c2c/src/components/C2CCouponCard.tsx

import { CouponCard, CouponCardConfig } from '@/templates/shared/composite/CouponCard';
import { SellerInfo } from './SellerInfo';
import { ListingPrice } from './ListingPrice';
import { TrustBadge } from './TrustBadge';

interface C2CCouponData extends CouponCardConfig {
  sellerId: string;
  sellerName: string;
  sellerRating: number;
  listingPrice: number;
  isVerifiedSeller: boolean;
}

export const C2CCouponCard: React.FC<C2CCouponData> = ({
  sellerId,
  sellerName,
  sellerRating,
  listingPrice,
  isVerifiedSeller,
  ...baseProps
}) => {
  return (
    <CouponCard
      {...baseProps}
      variant="default"
      headerSlot={
        <SellerInfo 
          name={sellerName}
          rating={sellerRating}
          verified={isVerifiedSeller}
        />
      }
      badgeSlot={
        isVerifiedSeller && <TrustBadge />
      }
      footerSlot={
        <ListingPrice price={listingPrice} />
      }
      actionLabel="Make Offer"
    />
  );
};
```

## Template Versioning Strategy

### Semantic Versioning (MAJOR.MINOR.PATCH)

```yaml
Version Format: X.Y.Z

MAJOR (X): Breaking changes
  - Removed props
  - Changed prop types
  - Removed component exports
  - Changed component structure
  Example: 1.0.0 → 2.0.0

MINOR (Y): New features (backward compatible)
  - New optional props
  - New component variants
  - New utility functions
  Example: 1.2.0 → 1.3.0

PATCH (Z): Bug fixes
  - Style fixes
  - Accessibility improvements
  - Performance optimizations
  Example: 1.2.3 → 1.2.4
```

### Version Management File

```typescript
// templates/shared/composite/CouponCard/version.ts

export const COUPON_CARD_VERSION = {
  major: 2,
  minor: 1,
  patch: 0,
  version: '2.1.0',
  
  changelog: {
    '2.1.0': {
      date: '2025-12-15',
      type: 'minor',
      changes: [
        'Added `badgeSlot` for custom badges',
        'Added `theme` prop for dark mode support',
      ],
      migration: null,
    },
    
    '2.0.0': {
      date: '2025-11-01',
      type: 'major',
      changes: [
        'BREAKING: Renamed `ctaLabel` to `actionLabel`',
        'BREAKING: Removed `showMerchant` prop (always shown if logo provided)',
        'Changed internal layout structure for better responsiveness',
      ],
      migration: './migrations/1.x-to-2.0.md',
    },
    
    '1.5.2': {
      date: '2025-10-20',
      type: 'patch',
      changes: [
        'Fixed focus indicator visibility on dark backgrounds',
        'Improved screen reader announcements',
      ],
      migration: null,
    },
  },
  
  deprecations: {
    'ctaLabel': {
      since: '2.0.0',
      replacement: 'actionLabel',
      removedIn: '3.0.0',
    },
  },
};
```

### Migration Guide Template

```markdown
# Migration Guide: CouponCard v1.x → v2.0

## Breaking Changes

### 1. Renamed Prop: `ctaLabel` → `actionLabel`

**Before (v1.x)**:
```tsx
<CouponCard ctaLabel="Buy Now" />
```

**After (v2.0)**:
```tsx
<CouponCard actionLabel="Buy Now" />
```

**Migration Script**:
```bash
# Automated find-replace
find . -name "*.tsx" -o -name "*.ts" | xargs sed -i 's/ctaLabel=/actionLabel=/g'
```

### 2. Removed Prop: `showMerchant`

**Before (v1.x)**:
```tsx
<CouponCard 
  merchantLogo="logo.png"
  showMerchant={true}
/>
```

**After (v2.0)**:
```tsx
<CouponCard 
  merchantLogo="logo.png"  // Logo shown automatically if provided
/>

// To hide merchant, simply don't provide merchantLogo
<CouponCard 
  // merchantLogo omitted
/>
```

## Estimated Migration Time

- **Small projects** (<50 uses): 30 minutes
- **Medium projects** (50-200 uses): 2 hours
- **Large projects** (200+ uses): 1 day

## Testing Checklist

- [ ] Run automated migration script
- [ ] Update all component usages
- [ ] Run type checker: `npm run type-check`
- [ ] Visual regression tests pass
- [ ] Accessibility tests pass
- [ ] Update documentation references
```

## Dependency Tracking

```typescript
// templates/shared/TEMPLATE_USAGE.json

{
  "CouponCard@2.1.0": {
    "usedBy": [
      {
        "portal": "b2b",
        "version": "1.2.0",
        "files": [
          "src/components/B2BCouponCard.tsx",
          "src/pages/Dashboard.tsx"
        ],
        "usageCount": 23
      },
      {
        "portal": "b2c",
        "version": "2.0.5",
        "files": [
          "src/components/MarketplaceCouponCard.tsx",
          "src/pages/Browse.tsx",
          "src/pages/Favorites.tsx"
        ],
        "usageCount": 47
      },
      {
        "portal": "c2c",
        "version": "1.8.3",
        "files": [
          "src/components/C2CCouponCard.tsx",
          "src/pages/Listings.tsx"
        ],
        "usageCount": 31
      }
    ],
    "totalUsage": 101,
    "deprecated": false,
    "maintenanceStatus": "active"
  },
  
  "Button@3.2.1": {
    "usedBy": [
      {
        "portal": "all",
        "version": "*",
        "usageCount": 892
      }
    ],
    "totalUsage": 892,
    "deprecated": false,
    "maintenanceStatus": "active"
  }
}
```

## Template Documentation

### Component Documentation Template

```markdown
# CouponCard Template

**Version**: 2.1.0  
**Status**: ✅ Active  
**Maintainer**: Template Architecture Team

## Overview

Reusable coupon display card used across all portals. Provides a consistent base structure with portal-specific customization via slots.

## Installation

```bash
# Automatic (via package)
npm install @mezzofy/shared-templates

# Manual (copy to project)
cp templates/shared/composite/CouponCard packages/app-{portal}/src/components/
```

## Basic Usage

```tsx
import { CouponCard } from '@mezzofy/shared-templates';

<CouponCard
  id="coupon-123"
  title="50% Off Italian Restaurant"
  discount={50}
  discountType="percentage"
  expiresAt={new Date('2025-12-31')}
  merchantName="Luigi's Bistro"
  merchantLogo="/logos/luigis.png"
  onAction={() => handleRedeem('coupon-123')}
  actionLabel="Redeem Now"
/>
```

## Portal-Specific Examples

### B2B Portal
```tsx
<CouponCard
  {...couponData}
  headerSlot={<BulkPricingBadge price={bulkPrice} />}
  metadataSlot={<QuantityIndicator available={stock} />}
  actionLabel="Add to Cart"
/>
```

### C2C Portal
```tsx
<CouponCard
  {...couponData}
  headerSlot={<SellerInfo seller={seller} />}
  footerSlot={<ListingPrice price={listingPrice} />}
  badgeSlot={<TrustBadge verified={isVerified} />}
  actionLabel="Make Offer"
/>
```

## Props API

See [CouponCardConfig interface](#component-abstraction) above.

## Customization Slots

- **headerSlot**: Portal-specific header content
- **footerSlot**: Portal-specific footer content
- **badgeSlot**: Custom badges/indicators
- **metadataSlot**: Additional metadata display

## Variants

- **default**: Standard card with all features
- **featured**: Larger, highlighted card
- **compact**: Minimal card for dense lists

## Theming

Supports light and dark themes via `theme` prop.

## Accessibility

- ✅ Keyboard navigable
- ✅ Screen reader compatible
- ✅ WCAG 2.1 AA contrast ratios
- ✅ Focus indicators

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Dependencies

- `@mezzofy/shared-templates/core/Card`
- `@mezzofy/shared-templates/core/Button`
- React 18+

## Migration Guides

- [v1.x → v2.0](./migrations/1.x-to-2.0.md)
- [v2.0 → v2.1](./migrations/2.0-to-2.1.md)

## Related Templates

- `CouponDetail`
- `CouponList`
- `MerchantCard`

## Support

For issues or questions, contact: template-architecture@mezzofy.com
```

## Template Testing Strategy

```typescript
// templates/shared/composite/CouponCard/__tests__/CouponCard.test.tsx

import { render, screen, fireEvent } from '@testing-library/react';
import { CouponCard } from '../CouponCard';

describe('CouponCard Template', () => {
  const mockCoupon = {
    id: 'test-123',
    title: 'Test Coupon',
    discount: 50,
    discountType: 'percentage' as const,
    expiresAt: new Date('2025-12-31'),
    merchantName: 'Test Merchant',
  };
  
  it('renders core content correctly', () => {
    render(<CouponCard {...mockCoupon} />);
    
    expect(screen.getByText('Test Coupon')).toBeInTheDocument();
    expect(screen.getByText('50% OFF')).toBeInTheDocument();
    expect(screen.getByText('Test Merchant')).toBeInTheDocument();
  });
  
  it('renders portal-specific slots', () => {
    render(
      <CouponCard
        {...mockCoupon}
        headerSlot={<div>Header Content</div>}
        footerSlot={<div>Footer Content</div>}
      />
    );
    
    expect(screen.getByText('Header Content')).toBeInTheDocument();
    expect(screen.getByText('Footer Content')).toBeInTheDocument();
  });
  
  it('handles action callback', () => {
    const handleAction = jest.fn();
    
    render(
      <CouponCard
        {...mockCoupon}
        onAction={handleAction}
        actionLabel="Click Me"
      />
    );
    
    fireEvent.click(screen.getByText('Click Me'));
    expect(handleAction).toHaveBeenCalledTimes(1);
  });
  
  it('maintains accessibility standards', () => {
    const { container } = render(<CouponCard {...mockCoupon} />);
    
    // Check for proper semantic structure
    expect(container.querySelector('h3')).toBeInTheDocument();
    
    // Check for keyboard accessibility
    const button = screen.getByRole('button');
    expect(button).toHaveFocus();
  });
});
```

## Template Maintenance

### Backward Compatibility Policy

```yaml
Support Policy:
  current_major: Full support + new features
  previous_major: Bug fixes + security patches (12 months)
  older_versions: Security patches only (6 months)
  
Example Timeline:
  v3.0.0 released: January 2026
  v2.x.x support: Until January 2027 (bug fixes)
  v1.x.x support: Until July 2026 (security only)
  v1.x.x EOL: July 2026
```

### Breaking Change Process

1. **Proposal** (GitHub issue/RFC)
2. **Review** (Template Architecture Team)
3. **Deprecation Notice** (1-2 releases before removal)
4. **Migration Guide** (Detailed steps + scripts)
5. **Breaking Change** (Major version bump)
6. **Support Period** (12 months for old version)

## Quality Checklist

- [ ] Component is truly reusable across 3+ portals
- [ ] Props API is portal-agnostic
- [ ] Customization via slots/props, not inheritance
- [ ] Semantic versioning applied correctly
- [ ] Migration guide created for breaking changes
- [ ] Dependency tracking updated
- [ ] Comprehensive documentation written
- [ ] Unit tests cover core functionality
- [ ] Visual regression tests pass
- [ ] Accessibility standards met (WCAG 2.1 AA)
- [ ] TypeScript types are strict and accurate
- [ ] Examples provided for each portal
- [ ] Performance benchmarks documented
- [ ] Browser compatibility verified
- [ ] Team review completed
