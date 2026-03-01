---
name: mezzofy-platform
description: Master skill for Mezzofy multi-portal coupon exchange platform development. Use for understanding the overall system architecture, technology stack, development standards, and when to invoke specialized skills (frontend-developer, backend-developer, ai-llm-engineer, infrastructure-engineer, coupon-domain-expert). Provides context for building B2B, B2C, C2C, Admin, Merchant, Partnership, and Customer portals with shared components and unified architecture.
---

# Mezzofy Platform

Production development system for multi-portal coupon exchange platform.

## Platform Overview

Mezzofy is a comprehensive coupon exchange platform operating **7 distinct portals** with shared component libraries:

1. **B2B Portal** - Company bulk coupon management and analytics
2. **B2C Portal** - Customer coupon discovery and marketplace
3. **C2C Portal** - Peer-to-peer coupon exchange and trading
4. **Admin Portal** - System administration and platform oversight
5. **Merchant Portal** - Business coupon creation and management
6. **Partnership Portal** - Partner integrations and API management
7. **Customer Portal** - End-user account management and preferences

## Technology Stack

### Frontend
- **Framework**: React 18 + TypeScript 5 + Vite
- **Architecture**: Clean Architecture with MVVM pattern
- **UI**: Tailwind CSS + Shadcn UI
- **State**: Zustand (ViewModels) + React Query (server state)
- **Hosting**: AWS Amplify
- **Design**: Mobile-first responsive

### Backend
- **Framework**: Python FastAPI + Strawberry GraphQL
- **Architecture**: Controller-Service-Repository (CSR) pattern
- **Models**: Three-model pattern (DTO, DataModel, SchemaModel)
- **Lambda Adapter**: Mangum for AWS Lambda
- **Auth**: OAuth2 with JWT tokens

### Database
- **Core Data**: PostgreSQL (AWS RDS)
- **Logs/Cache**: DynamoDB
- **ORM**: SQLAlchemy

### Infrastructure
- **IaC**: AWS CDK (Python)
- **Compute**: Lambda functions
- **API**: API Gateway (HTTP APIs)
- **Storage**: S3, RDS, DynamoDB
- **CI/CD**: Jenkins + AWS CodePipeline
- **Monitoring**: CloudWatch + X-Ray

### AI/ML
- **LLM APIs**: OpenAI GPT-4, Anthropic Claude
- **Frameworks**: LangChain, LlamaIndex
- **Vector DB**: Qdrant for semantic search
- **Embeddings**: OpenAI text-embedding-3

### Testing
- **E2E**: Selenium (MCP), Playwright
- **Unit**: pytest (backend), Vitest (frontend)
- **Integration**: pytest with test containers

## Available Skills

Use these specialized skills for specific development tasks:

### 🎨 Frontend Development
**Skill**: `frontend-developer`  
**Use for**: React components, Clean Architecture, MVVM patterns, Shadcn UI, TypeScript, state management, NFC integration, responsive design

```
"Hey frontend-developer, create a coupon card component with NFC scanning"
```

### 🔧 Backend Development
**Skill**: `backend-developer`  
**Use for**: FastAPI endpoints, GraphQL schemas, CSR pattern, business logic, database design, OAuth2, Lambda deployment

```
"backend-developer, create a coupon API with GraphQL mutations"
```

### 🤖 AI/LLM Engineering
**Skill**: `ai-llm-engineer`  
**Use for**: RAG systems, chatbots, semantic search, LLM integration, agent orchestration, recommendation engines

```
"ai-llm-engineer, build a RAG system for coupon recommendations"
```

### ☁️ Infrastructure & DevOps
**Skill**: `infrastructure-engineer`  
**Use for**: AWS CDK stacks, Lambda deployment, API Gateway, RDS setup, CI/CD pipelines, monitoring

```
"infrastructure-engineer, create CDK stack for multi-portal deployment"
```

### 💼 Domain Expert
**Skill**: `coupon-domain-expert`  
**Use for**: Coupon lifecycle, state machines, business validation, NFC security, Stripe integration, fraud detection

```
"coupon-domain-expert, implement coupon state machine with fraud detection"
```

## Architecture Patterns

### Frontend: Clean Architecture + MVVM

```
src/
├── domain/              # Business entities & use cases
├── data/                # Repository implementations & mappers
├── presentation/
│   └── features/        # Feature-based organization
│       └── [name]/
│           ├── components/   # View
│           ├── viewmodels/   # Zustand ViewModel
│           └── hooks/        # View ↔ ViewModel binding
├── core/                # DI, errors, shared types
├── shared/              # Shared components & utilities
└── i18n/                # en.json, zh-CN.json, zh-TW.json
```

**Dependency Rule**: View → ViewModel → UseCase → Entity (inward only)

### Backend: Controller-Service-Repository (CSR)

Each layer owns its model — no standalone `models/` folder:

```
src/
├── controllers/         # REST/GraphQL endpoints
│   └── dto/             # Data Transfer Objects
├── services/            # Business logic
│   └── data_model/      # Application domain models
├── repositories/        # Data access
│   └── schema_model/    # Database ORM schemas
├── schemas/             # API schemas (GraphQL/Pydantic)
└── utils/               # Utilities & helpers
```

**Co-located Model Pattern**: Controller (DTO) → Service (DataModel) → Repository (SchemaModel)

### Multi-Portal: Shared Templates

```
project/
├── packages/
│   ├── app-b2b/          # B2B portal
│   ├── app-b2c/          # B2C portal
│   ├── app-c2c/          # C2C portal
│   ├── shared-components/ # Reusable UI
│   └── shared-types/     # Common types
└── templates/
    └── shared/           # Cross-portal templates
```

## Quick Start Examples

### Create a New Portal Feature

```bash
# 1. Frontend component with Clean Architecture
"frontend-developer, create a coupon redemption flow with MVVM pattern"

# 2. Backend API endpoint
"backend-developer, add redemption endpoint with Stripe integration"

# 3. Infrastructure deployment
"infrastructure-engineer, deploy redemption service to Lambda"

# 4. Add AI recommendations
"ai-llm-engineer, integrate personalized coupon suggestions"
```

### Build Complete Feature

```bash
# Full stack feature development
"I need to build a coupon search feature with semantic search.

frontend-developer: Create search UI with filters
backend-developer: Create search API with GraphQL
ai-llm-engineer: Implement RAG-based semantic search
infrastructure-engineer: Deploy search infrastructure
coupon-domain-expert: Add business validation rules"
```

## Development Standards

### Code Quality
- **TypeScript**: Strict mode, no `any` types
- **Python**: Type hints, PEP 8 compliance
- **Testing**: >80% coverage
- **Documentation**: Inline comments + README

### Architecture
- **Frontend**: Respect Clean Architecture layers
- **Backend**: Follow CSR pattern strictly
- **API**: RESTful + GraphQL best practices
- **Database**: Normalized schemas, proper indexes

### Security
- OAuth2 authentication on all APIs
- Input sanitization (XSS prevention)
- Parameterized queries (SQL injection prevention)
- TLS 1.3 for all connections
- AES-256 encryption at rest
- PII masking in logs

### Performance
- **Frontend**: <3s initial load, <5s TTI
- **Backend**: <500ms API response (p95)
- **Database**: <100ms queries (p95)
- **Lambda**: <1s cold start

## Localization

All portals support:
- English (default)
- Chinese Simplified (zh-CN)
- Chinese Traditional (zh-TW)

Structure all text for i18n from the start.

## MCP Integrations

Available MCP tools:
- **Shadcn MCP**: UI component generation
- **Selenium MCP**: Browser automation testing

## Portal-Specific Guidelines

### B2B Portal
- **Users**: Corporate purchasers, bulk managers
- **Features**: Bulk operations, analytics, team management
- **Theme**: Professional, dark mode
- **Rules**: Minimum quantity 10, approval for $5000+

### B2C Portal
- **Users**: End consumers, shoppers
- **Features**: Discovery, search, wishlists
- **Theme**: Colorful, mobile-optimized
- **Rules**: User tier eligibility

### C2C Portal
- **Users**: Peer-to-peer traders
- **Features**: Listing, bidding, escrow, ratings
- **Theme**: Marketplace-style
- **Rules**: Verified users only, escrow for $500+

### Admin Portal
- **Users**: Platform administrators
- **Features**: User management, monitoring, fraud detection
- **Theme**: Utility-focused, information-dense
- **Rules**: Role-based admin access

### Merchant Portal
- **Users**: Business owners
- **Features**: Coupon creation, campaigns, analytics
- **Theme**: Professional, brand-focused
- **Rules**: Merchant verification required

### Partnership Portal
- **Users**: API partners, developers
- **Features**: API keys, webhooks, documentation
- **Theme**: Developer-focused
- **Rules**: API authentication

### Customer Portal
- **Users**: Registered users
- **Features**: Profile, history, preferences
- **Theme**: Personal, customizable
- **Rules**: User authentication

## Common Commands

### Development
```bash
# Frontend
npm run dev              # Start dev server
npm run build           # Production build
npm run test            # Run tests

# Backend
uvicorn main:app --reload  # Start API
pytest tests/             # Run tests
alembic upgrade head      # Run migrations

# Infrastructure
cdk synth               # Synthesize templates
cdk deploy --all       # Deploy all stacks
```

### Deployment
```bash
# Frontend to Amplify
aws amplify publish

# Backend to Lambda
cdk deploy BackendStack

# Full stack
./scripts/deploy-all.sh
```

## When to Use Which Skill

| Task | Primary Skill | Supporting Skills |
|------|--------------|-------------------|
| UI Component | frontend-developer | - |
| API Endpoint | backend-developer | coupon-domain-expert |
| Database Schema | backend-developer | coupon-domain-expert |
| AWS Infrastructure | infrastructure-engineer | - |
| Chatbot/RAG | ai-llm-engineer | backend-developer |
| State Machine | coupon-domain-expert | backend-developer |
| NFC Integration | coupon-domain-expert | frontend-developer |
| Payment Flow | coupon-domain-expert | backend-developer |
| Fraud Detection | coupon-domain-expert | ai-llm-engineer |
| Multi-Portal Setup | infrastructure-engineer | frontend-developer |

## Project Context

**Version**: 2.0.0  
**Team**: CPO Eric, CEO Dicky, COO Maverick, CTO Kris  
**Repository**: Monorepo with Turborepo  
**Deployment**: AWS (us-east-1)  
**Monitoring**: CloudWatch + LangSmith  

---

For detailed implementation guidance, invoke the specific skill for your task.
