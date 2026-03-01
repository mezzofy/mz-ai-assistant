---
name: frontend-developer
description: Frontend development specialist for React applications with Clean Architecture and MVVM patterns. Use for UI components, state management, TypeScript development, Shadcn UI integration, Tailwind CSS styling, performance optimization, accessibility (WCAG 2.1 AA), NFC Web API integration, and scalable frontend architecture for multi-portal coupon exchange platforms.
---

# Frontend Developer

Build production-ready React applications using Clean Architecture with MVVM patterns.

## Architecture

### Clean Architecture Layers

```
src/
├── domain/                    # Enterprise Business Rules (innermost)
│   ├── entities/              # Core business objects
│   ├── usecases/              # Application business rules
│   └── repositories/          # Repository interfaces (contracts)
├── data/                      # Interface Adapters
│   ├── repositories/          # Repository implementations
│   ├── datasources/           # API clients, local storage
│   └── mappers/               # Data transformation
├── presentation/              # Frameworks & Drivers (outermost)
│   └── features/              # Feature-based organization
│       └── [feature-name]/
│           ├── components/    # UI components (View)
│           ├── viewmodels/    # Zustand ViewModels (ViewModel)
│           └── hooks/         # View ↔ ViewModel binding
├── core/                      # Shared infrastructure
│   ├── di/                    # Dependency injection (Inversify)
│   ├── errors/                # Centralized error types
│   └── types/                 # Shared TypeScript interfaces
├── shared/                    # Shared presentation components & utilities
└── i18n/                      # Internationalization files
    ├── en.json
    ├── zh-CN.json
    └── zh-TW.json
```

### Dependency Rule

Dependencies always point inward: View → ViewModel → UseCase → Entity

## Tech Stack

- **Framework**: React 18 + TypeScript 5 + Vite
- **Styling**: Tailwind CSS + Shadcn UI
- **State**: Zustand (ViewModels), React Query (server state)
- **DI**: Custom dependency injection container
- **Design**: Mobile-first, responsive breakpoints

## Core Patterns

### 1. Domain Entity

```typescript
// domain/entities/Coupon.ts
export interface Coupon {
  id: string;
  title: string;
  discount: number;
  merchantId: string;
  expiresAt: Date;
  status: CouponStatus;
}

export enum CouponStatus {
  ACTIVE = 'active',
  EXPIRED = 'expired',
  REDEEMED = 'redeemed'
}
```

### 2. Repository Interface (Domain)

```typescript
// domain/repositories/ICouponRepository.ts
export interface ICouponRepository {
  getById(id: string): Promise<Coupon | null>;
  getAll(filter?: CouponFilter): Promise<Coupon[]>;
  create(dto: CreateCouponDTO): Promise<Coupon>;
  update(id: string, dto: UpdateCouponDTO): Promise<Coupon>;
  delete(id: string): Promise<void>;
}
```

### 3. Use Case (Domain)

```typescript
// domain/usecases/GetCouponUseCase.ts
import { ICouponRepository } from '../repositories/ICouponRepository';

export class GetCouponUseCase {
  constructor(private repo: ICouponRepository) {}
  
  async execute(id: string): Promise<Coupon | null> {
    if (!id?.trim()) {
      throw new Error('Coupon ID is required');
    }
    return this.repo.getById(id);
  }
}
```

### 4. Repository Implementation (Data)

```typescript
// data/repositories/CouponRepository.ts
import { ICouponRepository } from '@/domain/repositories/ICouponRepository';
import { ApiDataSource } from '../datasources/ApiDataSource';
import { CouponMapper } from '../mappers/CouponMapper';

export class CouponRepository implements ICouponRepository {
  constructor(private api: ApiDataSource) {}
  
  async getById(id: string): Promise<Coupon | null> {
    const response = await this.api.get(`/coupons/${id}`);
    return response ? CouponMapper.toDomain(response) : null;
  }
  
  async getAll(filter?: CouponFilter): Promise<Coupon[]> {
    const response = await this.api.get('/coupons', { params: filter });
    return response.map(CouponMapper.toDomain);
  }
  
  async create(dto: CreateCouponDTO): Promise<Coupon> {
    const response = await this.api.post('/coupons', dto);
    return CouponMapper.toDomain(response);
  }
}
```

### 5. ViewModel (Presentation)

```typescript
// presentation/features/coupons/viewmodels/useCouponViewModel.ts
import { create } from 'zustand';
import { container } from '@/core/di/container';
import { GetCouponUseCase } from '@/domain/usecases/GetCouponUseCase';

interface CouponState {
  coupon: Coupon | null;
  isLoading: boolean;
  error: string | null;
  fetchCoupon: (id: string) => Promise<void>;
  resetError: () => void;
}

export const useCouponViewModel = create<CouponState>((set) => ({
  coupon: null,
  isLoading: false,
  error: null,
  
  fetchCoupon: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const useCase = container.resolve(GetCouponUseCase);
      const coupon = await useCase.execute(id);
      set({ coupon, isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Unknown error',
        isLoading: false 
      });
    }
  },
  
  resetError: () => set({ error: null })
}));
```

### 6. View Component (Presentation)

```typescript
// presentation/features/coupons/components/CouponDetailView.tsx
import { FC, useEffect } from 'react';
import { useCouponViewModel } from '../viewmodels/useCouponViewModel';
import { CouponCard } from '@/shared/components/CouponCard';
import { LoadingSpinner } from '@/shared/components/LoadingSpinner';
import { ErrorAlert } from '@/shared/components/ErrorAlert';

interface Props {
  couponId: string;
}

export const CouponDetailView: FC<Props> = ({ couponId }) => {
  const { coupon, isLoading, error, fetchCoupon } = useCouponViewModel();
  
  useEffect(() => {
    fetchCoupon(couponId);
  }, [couponId]);
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorAlert message={error} />;
  if (!coupon) return <div>Coupon not found</div>;
  
  return <CouponCard coupon={coupon} />;
};
```

### 7. Dependency Injection Setup

```typescript
// core/di/container.ts
import { Container } from 'inversify';
import { ApiDataSource } from '@/data/datasources/ApiDataSource';
import { CouponRepository } from '@/data/repositories/CouponRepository';
import { ICouponRepository } from '@/domain/repositories/ICouponRepository';
import { GetCouponUseCase } from '@/domain/usecases/GetCouponUseCase';

const container = new Container();

// Data sources
container.bind(ApiDataSource).toSelf().inSingletonScope();

// Repositories
container.bind<ICouponRepository>('ICouponRepository')
  .to(CouponRepository)
  .inSingletonScope();

// Use cases
container.bind(GetCouponUseCase).toSelf();

export { container };
```

## Shadcn UI Integration

Always use Shadcn components for UI elements:

```bash
# Add components via CLI
npx shadcn@latest add button card input dialog
```

```typescript
// Example: Using Shadcn Button
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardContent } from '@/components/ui/card';

export const CouponCard: FC<{ coupon: Coupon }> = ({ coupon }) => (
  <Card className="w-full max-w-md">
    <CardHeader>
      <h3 className="text-lg font-semibold">{coupon.title}</h3>
    </CardHeader>
    <CardContent>
      <p className="text-2xl font-bold">{coupon.discount}% OFF</p>
      <Button onClick={() => redeemCoupon(coupon.id)} className="mt-4">
        Redeem Coupon
      </Button>
    </CardContent>
  </Card>
);
```

## Multi-Portal Theming

```typescript
// core/theme/portal-themes.ts
export const portalThemes = {
  b2b: {
    colors: { 
      primary: '#ea580c',    // Dark orange
      accent: '#000000',     // Black
      background: '#ffffff'  // White
    },
    mode: 'light'
  },
  b2c: {
    colors: { 
      primary: '#f97316',    // Orange
      accent: '#fb923c',     // Medium orange
      background: '#ffffff'  // White
    },
    mode: 'light'
  },
  c2c: {
    colors: { 
      primary: '#c2410c',    // Darker orange
      accent: '#f97316',     // Orange
      background: '#ffffff'  // White
    },
    mode: 'light'
  },
  admin: {
    colors: { 
      primary: '#000000',    // Black
      accent: '#f97316',     // Orange
      background: '#fafafa'  // Off-white
    },
    mode: 'light'
  },
  merchant: {
    colors: { 
      primary: '#ea580c',    // Dark orange
      accent: '#000000',     // Black
      background: '#ffffff'  // White
    },
    mode: 'light'
  },
  partnership: {
    colors: { 
      primary: '#f97316',    // Orange
      accent: '#000000',     // Black
      background: '#ffffff'  // White
    },
    mode: 'light'
  },
  customer: {
    colors: { 
      primary: '#f97316',    // Orange
      accent: '#fb923c',     // Medium orange
      background: '#ffffff'  // White
    },
    mode: 'light'
  }
};

// Apply theme based on portal
const theme = portalThemes[currentPortal];
```

## Performance Standards

- Initial load: <3s on 3G
- Time to Interactive: <5s
- Lazy load routes with `React.lazy()`
- Code splitting by portal
- Image optimization (WebP, lazy loading)

## Accessibility (WCAG 2.1 AA)

- Semantic HTML elements
- ARIA labels for interactive elements
- Keyboard navigation support
- Focus management
- Screen reader testing
- Color contrast ≥4.5:1 for text

## i18n Structure

```typescript
// locales/en.json
{
  "coupon": {
    "title": "Coupon Details",
    "redeem": "Redeem Now",
    "expired": "This coupon has expired"
  }
}

// Usage
import { useTranslation } from 'react-i18next';

const { t } = useTranslation();
<Button>{t('coupon.redeem')}</Button>
```

## NFC Integration

```typescript
// hooks/useNFCReader.ts
export const useNFCReader = () => {
  const readCoupon = async () => {
    if (!('NDEFReader' in window)) {
      throw new Error('NFC not supported');
    }
    
    const reader = new NDEFReader();
    await reader.scan();
    
    reader.onreading = (event) => {
      const { serialNumber, message } = event;
      // Process coupon data
    };
  };
  
  return { readCoupon };
};
```

## Quality Checklist

- [ ] No `any` types - use proper TypeScript
- [ ] Mobile-first responsive design
- [ ] Shadcn components used
- [ ] Clean Architecture layers respected
- [ ] ViewModels use Zustand
- [ ] Use cases handle business logic
- [ ] Repository pattern for data access
- [ ] Dependency injection configured
- [ ] i18n keys structured
- [ ] Accessibility tested
- [ ] Performance metrics met
