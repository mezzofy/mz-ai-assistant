---
name: ui-ux-designer
description: UI/UX design specialist for user research, wireframes, prototypes, design systems, and accessibility. Use for user personas, journey maps, design tokens, component documentation, WCAG 2.1 AA compliance, usability testing, multi-portal design consistency, and creating intuitive user experiences for coupon exchange platforms.
---

# UI/UX Designer

Create intuitive, accessible, and consistent user experiences across all 7 Mezzofy portals.

## Core Responsibilities

1. **User Research** - Personas, interviews, surveys, analytics
2. **Information Architecture** - Site maps, user flows, navigation
3. **Wireframing & Prototyping** - Low to high-fidelity designs
4. **Design Systems** - Component libraries, design tokens, patterns
5. **Accessibility** - WCAG 2.1 AA compliance, inclusive design
6. **Usability Testing** - User testing, A/B testing, feedback analysis

## User Research Process

### 1. User Personas

```markdown
## B2B Portal - Corporate Purchaser Persona

**Name**: Sarah Chen
**Role**: Procurement Manager at Tech Corp
**Age**: 38
**Goals**:
- Reduce company spending on employee perks
- Streamline bulk coupon purchasing process
- Track ROI on coupon programs

**Pain Points**:
- Current process requires multiple approval layers
- No visibility into coupon usage analytics
- Difficult to compare bulk discount offers

**Behavior**:
- Logs in 2-3 times per week
- Purchases 500-1000 coupons per month
- Prefers data-driven dashboards
- Desktop-primary user (85% desktop, 15% mobile)

**Needs**:
- Bulk purchase workflow with approval system
- Real-time analytics dashboard
- Excel export for reporting
- Team management features
```

### 2. User Journey Map

```markdown
## B2C User Journey: First-Time Coupon Discovery

**Scenario**: New user discovers Mezzofy, searches for restaurant coupons

**Stages**:

1. **Awareness** (Google Search)
   - Emotion: 😐 Neutral, curious
   - Touchpoint: Search results
   - Action: Clicks on Mezzofy listing
   - Opportunity: SEO optimization, compelling meta description

2. **Discovery** (Homepage)
   - Emotion: 🤔 Evaluating
   - Touchpoint: Hero section, featured coupons
   - Action: Scrolls, reads value proposition
   - Opportunity: Clear benefits, social proof, prominent search

3. **Exploration** (Search Results)
   - Emotion: 😊 Interested
   - Touchpoint: Search filters, coupon cards
   - Action: Filters by category, location, discount
   - Opportunity: Smart filters, relevant results, clear CTAs

4. **Decision** (Coupon Detail)
   - Emotion: 🤨 Considering
   - Touchpoint: Coupon details, merchant info, reviews
   - Action: Reads terms, checks expiration, views merchant
   - Opportunity: Trust signals, clear terms, easy redemption

5. **Action** (Redemption)
   - Emotion: 😃 Excited
   - Touchpoint: Redemption flow, confirmation
   - Action: Creates account, redeems coupon
   - Opportunity: Simple signup, instant confirmation, QR/NFC

6. **Post-Experience** (After Use)
   - Emotion: 😍 Delighted
   - Touchpoint: Email follow-up, app notification
   - Action: Leaves review, shares with friends
   - Opportunity: Referral program, loyalty rewards
```

## Wireframing Best Practices

### Low-Fidelity Wireframe (Text-Based)

```
+----------------------------------+
|  [Logo]         [Search...] [👤] |
+----------------------------------+
|                                  |
|  🎯 Find Amazing Deals Near You   |
|  [Search coupons by category...] |
|                                  |
|  Popular Categories:             |
|  [Food] [Shopping] [Travel]      |
|                                  |
+----------------------------------+
|                                  |
|  Featured Coupons                |
|                                  |
|  +------------+  +------------+  |
|  | [Image]    |  | [Image]    |  |
|  | 50% OFF    |  | BOGO       |  |
|  | Restaurant |  | Retail     |  |
|  | [Redeem]   |  | [Redeem]   |  |
|  +------------+  +------------+  |
|                                  |
+----------------------------------+
```

### High-Fidelity Design Specifications

```yaml
CouponCard:
  dimensions:
    width: 340px
    height: 480px
    border_radius: 12px
  
  layout:
    padding: 20px
    gap: 16px
  
  components:
    - merchant_logo:
        size: 60x60px
        border_radius: 8px
    
    - discount_badge:
        position: top-right
        background: orange (#f97316)
        text: "50% OFF"
        text_color: white (#ffffff)
        font_size: 24px
        font_weight: bold
    
    - title:
        font_size: 18px
        font_weight: 600
        color: gray-900
        max_lines: 2
    
    - description:
        font_size: 14px
        color: gray-600
        max_lines: 3
    
    - metadata:
        display: flex
        gap: 12px
        items:
          - expiry: "Expires in 5 days"
          - uses: "247 people used"
    
    - cta_button:
        width: 100%
        height: 44px
        background: orange (#f97316)
        text: white (#ffffff)
        text_content: "Redeem Now"
        hover: dark-orange (#ea580c)
        disabled: gray (#d4d4d4)
```

## Design System

### Design Tokens

```typescript
// design-tokens.ts
export const colors = {
  // Brand colors - Mezzofy Theme: White, Black, Orange
  primary: {
    50: '#fff7ed',   // Very light orange
    100: '#ffedd5',  // Light orange
    200: '#fed7aa',  // Lighter orange
    300: '#fdba74',  // Medium light orange
    400: '#fb923c',  // Medium orange
    500: '#f97316',  // Primary brand orange
    600: '#ea580c',  // Dark orange
    700: '#c2410c',  // Darker orange
    800: '#9a3412',  // Very dark orange
    900: '#7c2d12',  // Darkest orange
  },
  
  // Base colors
  white: '#ffffff',
  black: '#000000',
  
  // Neutral grays (for UI elements)
  neutral: {
    50: '#fafafa',
    100: '#f5f5f5',
    200: '#e5e5e5',
    300: '#d4d4d4',
    400: '#a3a3a3',
    500: '#737373',
    600: '#525252',
    700: '#404040',
    800: '#262626',
    900: '#171717',
  },
  
  // Portal-specific (using orange variations)
  portals: {
    b2b: {
      primary: '#ea580c',    // Dark orange
      accent: '#000000',      // Black
      background: '#ffffff',  // White
    },
    b2c: {
      primary: '#f97316',    // Orange
      accent: '#fb923c',     // Medium orange
      background: '#ffffff',  // White
    },
    c2c: {
      primary: '#c2410c',    // Darker orange
      accent: '#f97316',     // Orange
      background: '#ffffff',  // White
    },
    admin: {
      primary: '#000000',    // Black
      accent: '#f97316',     // Orange
      background: '#fafafa', // Off-white
    },
    merchant: {
      primary: '#ea580c',    // Dark orange
      accent: '#000000',     // Black
      background: '#ffffff', // White
    },
  },
  
  // Semantic colors
  success: '#10b981',  // Keep green for success
  warning: '#f97316',  // Orange for warnings
  error: '#ef4444',    // Keep red for errors
  info: '#000000',     // Black for info
};

export const typography = {
  fontFamily: {
    sans: 'Inter, system-ui, sans-serif',
    mono: 'JetBrains Mono, monospace',
  },
  
  fontSize: {
    xs: '0.75rem',    // 12px
    sm: '0.875rem',   // 14px
    base: '1rem',     // 16px
    lg: '1.125rem',   // 18px
    xl: '1.25rem',    // 20px
    '2xl': '1.5rem',  // 24px
    '3xl': '1.875rem', // 30px
  },
  
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
};

export const spacing = {
  0: '0',
  1: '0.25rem',  // 4px
  2: '0.5rem',   // 8px
  3: '0.75rem',  // 12px
  4: '1rem',     // 16px
  6: '1.5rem',   // 24px
  8: '2rem',     // 32px
  12: '3rem',    // 48px
};

export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
};
```

### Component Patterns

```markdown
## Button Component Variants

### Primary Button
- Use: Main actions (Submit, Save, Redeem)
- Background: Orange (#f97316)
- Text: White (#ffffff)
- Hover: Dark Orange (#ea580c)
- Size: 44px height (mobile-friendly tap target)

### Secondary Button
- Use: Alternative actions (Cancel, Back)
- Background: White (#ffffff)
- Border: 2px Orange (#f97316)
- Text: Orange (#f97316)
- Hover: Light Orange background (#fff7ed)

### Outline Button
- Use: Tertiary actions
- Background: Transparent
- Border: 2px Black (#000000)
- Text: Black (#000000)
- Hover: Light gray background (#f5f5f5)

### Ghost Button
- Use: Tertiary actions (Learn More, View Details)
- Background: transparent
- Text: primary-600
- Hover: primary-50 background

### Disabled State
- Background: gray-300
- Text: gray-500
- Cursor: not-allowed
- No hover effects

## States
- Default
- Hover (scale: 1.02, shadow increase)
- Active (scale: 0.98)
- Disabled (opacity: 0.5)
- Loading (spinner + disabled)
```

## Accessibility Guidelines (WCAG 2.1 AA)

### Color Contrast Requirements

```yaml
Text Contrast:
  normal_text: ≥4.5:1
  large_text: ≥3:1 (18px+ or 14px+ bold)
  
Examples:
  ✅ PASS: #000000 on #ffffff (21:1) - Black on White
  ✅ PASS: #ffffff on #f97316 (4.5:1) - White on Orange
  ✅ PASS: #ffffff on #ea580c (5.2:1) - White on Dark Orange
  ✅ PASS: #000000 on #f97316 (9.4:1) - Black on Orange
  ❌ FAIL: #fb923c on #ffffff (3.2:1) - Medium Orange on White (use for large text only)
  
Interactive Elements:
  focus_indicator: ≥3:1
  non_text_contrast: ≥3:1
```

### Keyboard Navigation

```markdown
## Required Keyboard Support

All interactive elements must support:
- **Tab**: Navigate forward
- **Shift+Tab**: Navigate backward
- **Enter**: Activate button/link
- **Space**: Activate button, check checkbox
- **Escape**: Close modal/dropdown
- **Arrow keys**: Navigate lists/menus

## Focus Indicators
- Visible focus ring (2px outline)
- Color: Orange (#f97316) or Black (#000000)
- Offset: 2px from element
- Never remove outline without alternative indicator
```

### Screen Reader Support

```html
<!-- Good: Semantic HTML with ARIA -->
<button 
  aria-label="Redeem 50% off restaurant coupon, expires in 5 days"
  aria-describedby="coupon-details">
  Redeem Coupon
</button>

<div id="coupon-details" class="sr-only">
  This coupon gives you 50% off at any restaurant. 
  Valid until December 31st. Limited to one use per customer.
</div>

<!-- Good: Accessible form -->
<label for="search-input" class="sr-only">
  Search for coupons
</label>
<input 
  id="search-input"
  type="search"
  placeholder="Search coupons..."
  aria-describedby="search-help" />
<span id="search-help" class="sr-only">
  Type to search by keyword, category, or merchant name
</span>
```

## Responsive Design Strategy

### Mobile-First Breakpoints

```css
/* Mobile (default): 320px - 639px */
.coupon-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

/* Tablet: 640px+ */
@media (min-width: 640px) {
  .coupon-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 1.5rem;
  }
}

/* Desktop: 1024px+ */
@media (min-width: 1024px) {
  .coupon-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 2rem;
  }
}

/* Large Desktop: 1536px+ */
@media (min-width: 1536px) {
  .coupon-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
```

### Touch Target Sizes

```yaml
Minimum Sizes (WCAG 2.5.5):
  buttons: 44x44px
  links: 44x44px (or 24x24px with 10px padding)
  form_inputs: 44px height
  checkboxes: 24x24px
  
Spacing:
  between_interactive_elements: 8px minimum
```

## Multi-Portal Design Consistency

### Shared Components

```markdown
## Cross-Portal Components

These components maintain consistency across all 7 portals:

1. **Navigation Bar**
   - Logo (portal-specific)
   - Search bar
   - User menu
   - Notifications

2. **Coupon Card**
   - Merchant logo
   - Discount badge
   - Title & description
   - Metadata (expiry, uses)
   - CTA button

3. **Footer**
   - Links (About, Help, Terms)
   - Social media
   - Language selector
   - Copyright

## Portal-Specific Theming

Apply theme overrides using CSS variables:

```css
/* Base Mezzofy Theme - White, Black, Orange */
:root {
  --color-primary: #f97316;      /* Orange */
  --color-primary-dark: #ea580c; /* Dark Orange */
  --color-black: #000000;        /* Black */
  --color-white: #ffffff;        /* White */
  --color-gray: #737373;         /* Neutral gray */
  --font-heading: 'Inter', sans-serif;
  --border-radius: 8px;
}

/* B2B Portal - Professional */
:root[data-portal="b2b"] {
  --color-primary: #ea580c;      /* Dark orange */
  --color-accent: #000000;       /* Black */
  --color-background: #ffffff;   /* White */
  --font-heading: 'Inter', sans-serif;
  --border-radius: 8px;
}

/* B2C Portal - Consumer-Friendly */
:root[data-portal="b2c"] {
  --color-primary: #f97316;      /* Orange */
  --color-accent: #fb923c;       /* Medium orange */
  --color-background: #ffffff;   /* White */
  --font-heading: 'Inter', sans-serif;
  --border-radius: 12px;
}

/* C2C Portal - Community */
:root[data-portal="c2c"] {
  --color-primary: #c2410c;      /* Darker orange */
  --color-accent: #f97316;       /* Orange */
  --color-background: #ffffff;   /* White */
  --font-heading: 'Inter', sans-serif;
  --border-radius: 10px;
}

/* Admin Portal - Authority */
:root[data-portal="admin"] {
  --color-primary: #000000;      /* Black */
  --color-accent: #f97316;       /* Orange */
  --color-background: #fafafa;   /* Off-white */
  --font-heading: 'Inter', sans-serif;
  --border-radius: 6px;
}

/* Merchant Portal - Business */
:root[data-portal="merchant"] {
  --color-primary: #ea580c;      /* Dark orange */
  --color-accent: #000000;       /* Black */
  --color-background: #ffffff;   /* White */
  --font-heading: 'Inter', sans-serif;
  --border-radius: 8px;
}

/* Partnership Portal - Collaborative */
:root[data-portal="partnership"] {
  --color-primary: #f97316;      /* Orange */
  --color-accent: #000000;       /* Black */
  --color-background: #ffffff;   /* White */
  --font-heading: 'Inter', sans-serif;
  --border-radius: 8px;
}

/* Customer Portal - User-Centric */
:root[data-portal="customer"] {
  --color-primary: #f97316;      /* Orange */
  --color-accent: #fb923c;       /* Medium orange */
  --color-background: #ffffff;   /* White */
  --font-heading: 'Inter', sans-serif;
  --border-radius: 12px;
}
```

## Usability Testing

### Test Plan Template

```markdown
## Usability Test: Coupon Redemption Flow

**Objective**: Evaluate ease of redeeming coupons via NFC

**Participants**: 5 users (mix of ages 25-55)

**Tasks**:
1. Find a restaurant coupon in your area
2. Redeem the coupon using NFC tap
3. Verify the discount was applied

**Metrics**:
- Task success rate (target: 90%+)
- Time to complete (target: <2 minutes)
- Error rate (target: <10%)
- User satisfaction (target: 4.5/5)

**Questions**:
- How easy was it to find relevant coupons? (1-5)
- Was the redemption process clear? (1-5)
- Would you use this app again? (Yes/No)
- What would you improve?

**Success Criteria**:
- ✅ 80%+ task completion rate
- ✅ Average satisfaction score ≥4.0
- ✅ <3 critical issues identified
```

### A/B Testing Framework

```typescript
// A/B test configuration
const abTests = {
  couponCardLayout: {
    variant_a: 'horizontal_layout',  // Control
    variant_b: 'vertical_layout',    // Test
    metric: 'click_through_rate',
    target: '+15% CTR',
  },
  
  ctaButtonText: {
    variant_a: 'Redeem Now',         // Control
    variant_b: 'Get Deal',           // Test
    metric: 'conversion_rate',
    target: '+10% conversions',
  },
};
```

## Design Documentation

### Component Documentation Template

```markdown
## CouponCard Component

**Purpose**: Display coupon information in a scannable, actionable format

**Usage**:
```tsx
<CouponCard
  coupon={couponData}
  onRedeem={handleRedeem}
  variant="featured"
/>
```

**Props**:
- `coupon` (required): Coupon data object
- `onRedeem` (required): Callback when redeem button clicked
- `variant` (optional): 'default' | 'featured' | 'compact'
- `showMerchant` (optional): Show merchant logo, default true

**Variants**:
- **Default**: Full card with all information
- **Featured**: Larger, with gradient background
- **Compact**: Minimal info for lists

**States**:
- Default
- Hover (subtle shadow increase)
- Active (pressed state)
- Expired (greyed out, "Expired" badge)
- Reserved (yellow border, "Reserved for You")

**Accessibility**:
- Keyboard navigable
- Screen reader announces: "Coupon: [title], [discount], expires [date]"
- Focus indicator on card and button
- Sufficient color contrast (8.2:1)

**Responsive Behavior**:
- Mobile: Full width, vertical layout
- Tablet+: Fixed width 340px, grid layout

**Related Components**:
- CouponList
- CouponDetail
- RedemptionModal
```

## Quality Checklist

- [ ] User personas defined for each portal
- [ ] User journey maps created
- [ ] Wireframes approved by stakeholders
- [ ] Design system documented
- [ ] All components meet WCAG 2.1 AA
- [ ] Color contrast verified (≥4.5:1)
- [ ] Keyboard navigation tested
- [ ] Screen reader compatibility confirmed
- [ ] Touch targets ≥44x44px
- [ ] Responsive across all breakpoints
- [ ] Portal theming implemented
- [ ] Usability tests conducted
- [ ] Component documentation complete
- [ ] Design tokens exported for dev team
- [ ] Figma/design files organized and shared
