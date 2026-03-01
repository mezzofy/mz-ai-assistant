---
name: technical-writer
description: Technical writer specialist for user guides, documentation, README files, architecture docs, and troubleshooting guides. Use for user-facing documentation, multi-language support (EN, zh-CN, zh-TW), Mermaid diagrams, Architecture Decision Records (ADRs), API guides, deployment documentation, and creating clear, accessible documentation for coupon exchange platform users and developers.
---

# Technical Writer

Create clear, comprehensive documentation for users and developers.

## Documentation Types

1. **User Guides** - End-user product documentation
2. **README Files** - Project setup and overview
3. **API Documentation** - Developer reference guides
4. **Architecture Docs** - System design and ADRs
5. **Troubleshooting Guides** - Problem resolution
6. **Release Notes** - Version changelogs

## User Guide Template

```markdown
# Mezzofy User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Finding Coupons](#finding-coupons)
3. [Redeeming Coupons](#redeeming-coupons)
4. [Managing Your Account](#managing-your-account)
5. [Troubleshooting](#troubleshooting)
6. [FAQs](#faqs)

---

## Getting Started

### Creating Your Account

**Web App:**
1. Visit [mezzofy.com](https://mezzofy.com)
2. Click **Sign Up** in the top right corner
3. Enter your email and create a password
4. Verify your email address
5. Complete your profile

**Mobile App:**
1. Download Mezzofy from [App Store](https://apps.apple.com/app/mezzofy) or [Google Play](https://play.google.com/store/apps/details?id=com.mezzofy)
2. Open the app and tap **Get Started**
3. Follow the on-screen instructions
4. Allow notifications (optional, but recommended for coupon alerts)

> **Pro Tip**: Enable biometric login for faster access to your coupons!

### Your Dashboard

After logging in, you'll see your personalized dashboard:

- **Featured Coupons**: Hand-picked deals based on your interests
- **Expiring Soon**: Coupons in your collection that expire within 7 days
- **Popular Near You**: Trending deals in your area
- **Recommended for You**: AI-powered suggestions

---

## Finding Coupons

### Search

**Basic Search:**
1. Click the search bar at the top
2. Type what you're looking for (e.g., "pizza", "electronics")
3. Browse the results

**Advanced Filters:**
- **Category**: Food, Shopping, Travel, Entertainment
- **Discount**: Set minimum discount percentage
- **Location**: Within X miles of your location
- **Expiration**: Only show coupons valid for X days

### Browse by Category

Popular categories:
- 🍕 Food & Dining
- 🛍️ Shopping & Retail
- ✈️ Travel & Hotels
- 🎬 Entertainment
- 💪 Health & Fitness

### Save for Later

Found a coupon you like?
1. Click the ❤️ (heart) icon
2. Access saved coupons from **My Coupons** → **Saved**

---

## Redeeming Coupons

### Option 1: NFC Tap (Mobile Only)

**Requirements:**
- iPhone with iOS 14+ or Android with NFC
- Merchant location must support NFC

**Steps:**
1. Open the coupon in the app
2. Tap **Redeem with NFC**
3. Hold your phone near the merchant's NFC reader
4. Wait for confirmation (usually 1-2 seconds)
5. Show the success screen to the merchant

> **Note**: Make sure NFC is enabled in your phone settings.

### Option 2: QR Code

**Steps:**
1. Open the coupon
2. Tap **Show QR Code**
3. Let the merchant scan your screen
4. Confirm redemption

### Option 3: Code Entry

**Steps:**
1. Open the coupon
2. Tap **View Code**
3. Read the code to the merchant (e.g., "SAVE50")
4. Merchant enters the code at checkout

---

## Managing Your Account

### Profile Settings

Access via **Profile** → **Settings**

**Personal Information:**
- Name, email, phone
- Location preferences
- Language (English, 简体中文, 繁體中文)

**Notifications:**
- New coupon alerts
- Expiration reminders (3 days, 1 day, 1 hour)
- Weekly digest

**Privacy:**
- Who can see your profile
- Data sharing preferences
- Delete account

### Payment Methods (B2C/C2C Portals)

For purchasing premium coupons or trading:

1. Go to **Profile** → **Payment Methods**
2. Click **Add Payment Method**
3. Enter card details (secured by Stripe)
4. Set as default (optional)

---

## Troubleshooting

### I can't find a specific coupon

**Solution:**
- Check your search filters (category, location, expiration)
- Try different search terms
- Check if the coupon has expired
- Contact the merchant to see if they're still offering it

### My coupon won't redeem

**Possible Causes:**
1. **Expired**: Check the expiration date
2. **Usage Limit Reached**: Some coupons have limited uses
3. **Location Restricted**: Coupon may only work at certain locations
4. **Technical Issue**: Try closing and reopening the app

**Still not working?** Contact support at help@mezzofy.com

### NFC redemption isn't working

**Troubleshooting Steps:**
1. Ensure NFC is enabled (Settings → NFC)
2. Remove phone case (metal cases block NFC)
3. Hold phone still for 2-3 seconds
4. Try different angles
5. Ask merchant to restart their NFC reader

### I didn't receive my verification email

**Solutions:**
- Check spam/junk folder
- Wait 5-10 minutes (emails can be delayed)
- Click **Resend Verification Email** on login page
- Ensure email address is correct

---

## FAQs

**Q: Is Mezzofy free to use?**  
A: Yes! Creating an account and browsing coupons is completely free. Some premium features may require payment.

**Q: Can I use a coupon more than once?**  
A: It depends on the coupon. Check the "Usage Limit" in the coupon details. Most coupons are one-time use per person.

**Q: What happens if a merchant refuses my coupon?**  
A: Contact us immediately at help@mezzofy.com with:
- Coupon ID
- Merchant name
- Date and time of attempt
We'll investigate and issue a refund if applicable.

**Q: Can I gift a coupon to someone else?**  
A: Yes! Use the C2C (peer-to-peer) portal to transfer or sell coupons to other users.

**Q: How do I know if a coupon is legitimate?**  
A: All Mezzofy coupons are:
- ✅ Verified by our team
- ✅ Secured with digital signatures
- ✅ Tracked for fraud prevention

**Q: What languages does Mezzofy support?**  
A: Currently: English, Simplified Chinese (简体中文), Traditional Chinese (繁體中文)

---

## Need More Help?

- **Email**: help@mezzofy.com
- **Live Chat**: Available 9 AM - 9 PM EST
- **Help Center**: [support.mezzofy.com](https://support.mezzofy.com)
- **Community Forum**: [community.mezzofy.com](https://community.mezzofy.com)

---

*Last Updated: January 2026 | Version 2.0*
```

## README Template

```markdown
# Mezzofy B2C Portal

> 🎟️ The consumer-facing marketplace for discovering and redeeming coupons

## 📖 Overview

The B2C (Business-to-Consumer) portal is Mezzofy's primary customer-facing application where users can:
- Discover coupons from thousands of merchants
- Search and filter by category, location, and discount
- Redeem coupons via NFC, QR code, or manual entry
- Save favorite coupons and receive expiration reminders
- Share deals with friends

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm 9+
- React development experience
- Access to Mezzofy API (contact api@mezzofy.com)

### Installation

```bash
# Clone the repository
git clone https://github.com/mezzofy/b2c-portal.git
cd b2c-portal

# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local

# Add your API key to .env.local
VITE_API_URL=https://api.mezzofy.com/v2
VITE_API_KEY=your-api-key

# Start development server
npm run dev
```

Visit http://localhost:5173

### First-Time Setup

1. **Create an account** at http://localhost:5173/signup
2. **Browse coupons** on the home page
3. **Search** for specific merchants or categories
4. **Redeem** a test coupon (use test mode in settings)

## 📁 Project Structure

```
b2c-portal/
├── src/
│   ├── domain/          # Business entities and use cases
│   ├── data/            # Repository implementations
│   ├── presentation/    # React components and ViewModels
│   ├── core/           # Shared utilities and DI
│   └── main.tsx        # App entry point
├── public/             # Static assets
├── tests/              # Test files
└── docs/               # Additional documentation
```

## 🛠️ Development

### Running Tests

```bash
npm test                 # Run all tests
npm run test:watch      # Watch mode
npm run test:coverage   # With coverage report
```

### Building for Production

```bash
npm run build           # Build optimized bundle
npm run preview         # Preview production build
```

### Code Quality

```bash
npm run lint            # ESLint
npm run type-check      # TypeScript
npm run format          # Prettier
```

## 🏗️ Architecture

### Clean Architecture + MVVM

```
View (React Components)
    ↓
ViewModel (Zustand Stores)
    ↓
Use Cases (Business Logic)
    ↓
Repository (Data Access)
```

**Key Principles:**
- Dependencies point inward
- UI has no business logic
- Business logic is framework-agnostic
- Easy to test in isolation

### State Management

- **ViewModels**: Zustand for UI state
- **Server State**: React Query for API data
- **Form State**: React Hook Form
- **Global State**: Zustand stores

## 🎨 Styling

- **Framework**: Tailwind CSS
- **Components**: Shadcn UI
- **Icons**: Lucide React
- **Theme**: Purple/pink gradient (B2C branding)

## 🔐 Authentication

Uses OAuth2 with JWT tokens:
- Access token: 1 hour expiration
- Refresh token: 30 days expiration
- Automatic token refresh

## 📱 Features

### Core Features
- ✅ Coupon search and filtering
- ✅ NFC-based redemption
- ✅ QR code redemption
- ✅ Save favorite coupons
- ✅ Expiration reminders
- ✅ User profile management

### Coming Soon
- 🚧 AI-powered recommendations
- 🚧 Social sharing
- 🚧 Loyalty rewards program
- 🚧 Merchant reviews

## 🌍 Localization

Supported languages:
- English (en)
- Simplified Chinese (zh-CN)
- Traditional Chinese (zh-TW)

Add translations to `src/locales/`

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

**Coding Standards:**
- Follow existing code style
- Write tests for new features
- Update documentation
- Use conventional commits

## 📄 License

Proprietary - © 2025 Mezzofy Inc.

## 📞 Support

- **Email**: dev@mezzofy.com
- **Docs**: https://docs.mezzofy.com
- **Slack**: #b2c-portal channel

---

**Made with ❤️ by the Mezzofy Team**
```

## Architecture Decision Record (ADR)

```markdown
# ADR-001: Clean Architecture with MVVM Pattern

**Date**: 2025-01-15  
**Status**: Accepted  
**Deciders**: CPO Eric, CTO Kris, Frontend Team  

## Context

We need to choose an architecture pattern for the Mezzofy frontend applications that:
- Separates business logic from UI
- Makes testing easier
- Supports 7 different portals with shared components
- Scales with team growth

## Decision

We will use **Clean Architecture with MVVM (Model-View-ViewModel) pattern**.

### Structure

```
domain/           # Business entities and use cases (core)
  ├── entities/   # Coupon, User, Merchant
  └── usecases/   # GetCoupon, RedeemCoupon

data/             # Data access implementations
  ├── repositories/  # CouponRepository
  └── datasources/   # API, LocalStorage

presentation/     # UI layer
  ├── viewmodels/    # Zustand stores (state + logic)
  └── views/         # React components (pure UI)
```

### Rationale

**Pros:**
- ✅ Clear separation of concerns
- ✅ Business logic independent of framework
- ✅ Easy to test (can test use cases without React)
- ✅ Supports multiple portals (shared domain layer)
- ✅ Dependency Injection makes components loosely coupled

**Cons:**
- ❌ More boilerplate than simpler patterns
- ❌ Steeper learning curve for new developers
- ❌ Requires discipline to maintain boundaries

### Alternatives Considered

**1. Simple Component-Based** (e.g., create-react-app default)
- Rejected: Business logic mixed with UI, hard to test

**2. Redux + Saga/Thunk**
- Rejected: Too much boilerplate, overkill for our needs

**3. MVC Pattern**
- Rejected: Controllers can become bloated, less clear separation

## Consequences

### Positive
- Easier to maintain 7 different portals
- Can swap React for another framework if needed
- Business logic is fully testable
- Onboarding includes architecture training

### Negative
- Initial development slower due to setup
- Requires architecture documentation
- Need to enforce patterns in code review

## Implementation

1. Create domain layer with entities and use cases
2. Implement data layer with repositories
3. Build presentation layer with ViewModels (Zustand)
4. Create React views that consume ViewModels
5. Set up Dependency Injection container

## Validation

- ✅ Successfully implemented in B2C portal
- ✅ Test coverage > 80% for use cases
- ✅ Components are pure and easy to test
- ✅ Shared components work across portals

## References

- [Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [MVVM Pattern](https://en.wikipedia.org/wiki/Model%E2%80%93view%E2%80%93viewmodel)
- [Dependency Injection in TypeScript](https://www.typescriptlang.org/docs/handbook/decorators.html)

---

**Next Review**: June 2026
```

## Mermaid Diagrams

### System Architecture

```markdown
## System Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        B2B[B2B Portal]
        B2C[B2C Portal]
        C2C[C2C Portal]
        Admin[Admin Portal]
    end
    
    subgraph "API Gateway"
        Gateway[API Gateway]
    end
    
    subgraph "Backend Services"
        CouponAPI[Coupon Service]
        UserAPI[User Service]
        PaymentAPI[Payment Service]
    end
    
    subgraph "Data Layer"
        RDS[(PostgreSQL)]
        DynamoDB[(DynamoDB)]
        S3[(S3 Storage)]
    end
    
    B2B --> Gateway
    B2C --> Gateway
    C2C --> Gateway
    Admin --> Gateway
    
    Gateway --> CouponAPI
    Gateway --> UserAPI
    Gateway --> PaymentAPI
    
    CouponAPI --> RDS
    UserAPI --> RDS
    PaymentAPI --> RDS
    
    CouponAPI --> DynamoDB
    UserAPI --> S3
```\`\`\`

### Coupon Redemption Flow

```mermaid
sequenceDiagram
    actor User
    participant App
    participant API
    participant DB
    participant Payment
    
    User->>App: Open coupon
    App->>API: GET /coupons/:id
    API->>DB: Query coupon
    DB-->>API: Coupon data
    API-->>App: Coupon details
    
    User->>App: Tap "Redeem"
    App->>App: Request biometric auth
    User->>App: Authenticate (Face ID/Touch ID)
    
    App->>API: POST /coupons/:id/redeem
    API->>DB: Check coupon validity
    
    alt Coupon Valid
        DB-->>API: Valid
        API->>Payment: Apply discount
        Payment-->>API: Success
        API->>DB: Update coupon status
        DB-->>API: Updated
        API-->>App: Redemption success
        App-->>User: Show confirmation
    else Coupon Invalid
        DB-->>API: Invalid (expired/used)
        API-->>App: Error message
        App-->>User: Show error
    end
```\`\`\`
```

## Multi-Language Support

### English (en)
```json
{
  "home": {
    "title": "Find Amazing Deals",
    "search_placeholder": "Search for coupons...",
    "featured": "Featured Coupons",
    "expiring_soon": "Expiring Soon"
  },
  "coupon": {
    "redeem": "Redeem Now",
    "save": "Save for Later",
    "share": "Share with Friends",
    "expires": "Expires {{date}}",
    "discount": "{{amount}}% OFF"
  }
}
```

### Simplified Chinese (zh-CN)
```json
{
  "home": {
    "title": "发现优惠好物",
    "search_placeholder": "搜索优惠券...",
    "featured": "精选优惠券",
    "expiring_soon": "即将过期"
  },
  "coupon": {
    "redeem": "立即使用",
    "save": "保存备用",
    "share": "分享给朋友",
    "expires": "有效期至{{date}}",
    "discount": "{{amount}}%折扣"
  }
}
```

### Traditional Chinese (zh-TW)
```json
{
  "home": {
    "title": "發現優惠好物",
    "search_placeholder": "搜尋優惠券...",
    "featured": "精選優惠券",
    "expiring_soon": "即將過期"
  },
  "coupon": {
    "redeem": "立即使用",
    "save": "儲存備用",
    "share": "分享給朋友",
    "expires": "有效期至{{date}}",
    "discount": "{{amount}}%折扣"
  }
}
```

## Quality Checklist

- [ ] Clear, concise language (8th grade reading level)
- [ ] Proper heading hierarchy (H1, H2, H3)
- [ ] Screenshots/images where helpful
- [ ] Code examples formatted correctly
- [ ] Links tested and working
- [ ] Multi-language versions provided
- [ ] Mermaid diagrams render correctly
- [ ] Table of contents for long docs
- [ ] Consistent terminology throughout
- [ ] Reviewed by technical and non-technical readers
- [ ] Version and last-updated date included
- [ ] Contact information for support
- [ ] Accessibility considerations (alt text, contrast)
- [ ] Mobile-friendly formatting
- [ ] Searchable (good keywords, headings)
