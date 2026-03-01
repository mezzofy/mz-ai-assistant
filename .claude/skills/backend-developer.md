---
name: backend-developer
description: Backend development specialist for Python FastAPI + GraphQL APIs with Controller-Service-Repository (CSR) pattern. Use for API endpoints, GraphQL schemas, business logic, database design, OAuth2 authentication, AWS Lambda deployment, PostgreSQL/DynamoDB integration, and scalable backend architecture for multi-portal coupon exchange platforms.
---

# Backend Developer

Build production-ready FastAPI + GraphQL APIs using Controller-Service-Repository (CSR) pattern.

## Architecture: CSR Pattern

Each CSR layer owns its model — no standalone `models/` folder. Dependency flow: `Controller (DTO) → Service (DataModel) → Repository (SchemaModel)`

```
src/
├── controllers/           # HTTP/GraphQL entry points
│   ├── dto/               # Data Transfer Objects (API validation)
│   ├── rest/              # FastAPI route handlers
│   └── graphql/           # GraphQL resolvers
├── services/              # Business logic layer
│   └── data_model/        # Application domain models
├── repositories/          # Data access layer
│   └── schema_model/      # Database ORM schemas
├── schemas/               # API schemas (GraphQL/Pydantic)
├── utils/                 # Utilities & helpers
└── core/                  # Shared: config, auth, errors, database
```

**Project layout** (within a module):
```
svc-module-name/
├── src/                   # All source under src/
│   ├── controllers/
│   │   └── dto/
│   ├── services/
│   │   └── data_model/
│   ├── repositories/
│   │   └── schema_model/
│   ├── schemas/
│   └── utils/
├── tests/
│   ├── unit/
│   └── integration/
├── alembic/               # Database migrations
│   └── versions/
├── requirements.txt
└── main.py
```

## Tech Stack

- **Framework**: FastAPI + Strawberry GraphQL
- **Lambda Adapter**: Mangum (AWS Lambda compatibility)
- **Database**: PostgreSQL (RDS) + DynamoDB
- **ORM**: SQLAlchemy (PostgreSQL)
- **Auth**: OAuth2 with JWT tokens
- **Validation**: Pydantic v2
- **Testing**: pytest + pytest-asyncio

## Three-Model Pattern

### 1. DTO (Controller Layer)

Data Transfer Objects for API requests/responses — co-located in `controllers/dto/`:

```python
# controllers/dto/coupon_dto.py
from pydantic import BaseModel, Field
from datetime import datetime

class CreateCouponDTO(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    discount: int = Field(..., ge=1, le=100)
    merchant_id: str
    expires_at: datetime

class CouponResponseDTO(BaseModel):
    id: str
    title: str
    discount: int
    merchant_id: str
    expires_at: datetime
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True  # For SQLAlchemy models
```

### 2. DataModel (Service Layer)

Domain business objects — co-located in `services/data_model/`:

```python
# services/data_model/coupon.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class CouponStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REDEEMED = "redeemed"

@dataclass
class Coupon:
    id: str
    title: str
    discount: int
    merchant_id: str
    expires_at: datetime
    status: CouponStatus
    created_at: datetime
    updated_at: datetime
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def can_redeem(self) -> bool:
        return self.status == CouponStatus.ACTIVE and not self.is_expired()
```

### 3. SchemaModel (Repository Layer)

Database ORM schemas — co-located in `repositories/schema_model/`:

```python
# repositories/schema_model/coupon_schema.py
from sqlalchemy import Column, String, Integer, DateTime, Enum
from sqlalchemy.sql import func
from core.database import Base

class CouponSchema(Base):
    __tablename__ = "coupons"
    
    id = Column(String, primary_key=True)
    title = Column(String(100), nullable=False)
    discount = Column(Integer, nullable=False)
    merchant_id = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

## Controller Layer (REST)

```python
# controllers/rest/coupon_controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from services.coupon_service import CouponService
from controllers.dto.coupon_dto import CreateCouponDTO, CouponResponseDTO
from core.auth import get_current_user

router = APIRouter(prefix="/api/v1/coupons", tags=["coupons"])

@router.post("/", response_model=CouponResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    dto: CreateCouponDTO,
    user=Depends(get_current_user),
    service: CouponService = Depends()
):
    """Create a new coupon"""
    coupon = await service.create_coupon(dto)
    return CouponResponseDTO.from_orm(coupon)

@router.get("/{coupon_id}", response_model=CouponResponseDTO)
async def get_coupon(
    coupon_id: str,
    user=Depends(get_current_user),
    service: CouponService = Depends()
):
    """Get coupon by ID"""
    coupon = await service.get_coupon(coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return CouponResponseDTO.from_orm(coupon)

@router.get("/", response_model=List[CouponResponseDTO])
async def list_coupons(
    skip: int = 0,
    limit: int = 100,
    user=Depends(get_current_user),
    service: CouponService = Depends()
):
    """List all coupons"""
    coupons = await service.list_coupons(skip=skip, limit=limit)
    return [CouponResponseDTO.from_orm(c) for c in coupons]
```

## Controller Layer (GraphQL)

```python
# controllers/graphql/coupon_resolver.py
import strawberry
from typing import List, Optional
from strawberry.types import Info
from services.coupon_service import CouponService
from controllers.dto.coupon_dto import CreateCouponDTO

@strawberry.type
class CouponType:
    id: str
    title: str
    discount: int
    merchant_id: str
    expires_at: str
    status: str

@strawberry.input
class CreateCouponInput:
    title: str
    discount: int
    merchant_id: str
    expires_at: str

@strawberry.type
class Query:
    @strawberry.field
    async def coupon(self, info: Info, id: str) -> Optional[CouponType]:
        service = CouponService()
        coupon = await service.get_coupon(id)
        return CouponType(**coupon.__dict__) if coupon else None
    
    @strawberry.field
    async def coupons(self, info: Info) -> List[CouponType]:
        service = CouponService()
        coupons = await service.list_coupons()
        return [CouponType(**c.__dict__) for c in coupons]

@strawberry.type
class Mutation:
    @strawberry.mutation
    async def create_coupon(self, info: Info, input: CreateCouponInput) -> CouponType:
        service = CouponService()
        dto = CreateCouponDTO(**input.__dict__)
        coupon = await service.create_coupon(dto)
        return CouponType(**coupon.__dict__)

schema = strawberry.Schema(query=Query, mutation=Mutation)
```

## Service Layer

```python
# services/coupon_service.py
from typing import List, Optional
from services.data_model.coupon import Coupon, CouponStatus
from controllers.dto.coupon_dto import CreateCouponDTO
from repositories.coupon_repository import CouponRepository
from core.errors import BusinessLogicError
import uuid

class CouponService:
    def __init__(self, repo: CouponRepository = None):
        self.repo = repo or CouponRepository()
    
    async def create_coupon(self, dto: CreateCouponDTO) -> Coupon:
        """Create a new coupon with business validation"""
        # Business logic validation
        if dto.discount > 90:
            raise BusinessLogicError("Discount cannot exceed 90%")
        
        # Create domain model
        coupon = Coupon(
            id=str(uuid.uuid4()),
            title=dto.title,
            discount=dto.discount,
            merchant_id=dto.merchant_id,
            expires_at=dto.expires_at,
            status=CouponStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Persist via repository
        return await self.repo.create(coupon)
    
    async def get_coupon(self, coupon_id: str) -> Optional[Coupon]:
        """Get coupon by ID"""
        return await self.repo.get_by_id(coupon_id)
    
    async def list_coupons(self, skip: int = 0, limit: int = 100) -> List[Coupon]:
        """List coupons with pagination"""
        return await self.repo.get_all(skip=skip, limit=limit)
    
    async def redeem_coupon(self, coupon_id: str, user_id: str) -> Coupon:
        """Redeem a coupon with business rules"""
        coupon = await self.repo.get_by_id(coupon_id)
        
        if not coupon:
            raise BusinessLogicError("Coupon not found")
        
        if not coupon.can_redeem():
            raise BusinessLogicError("Coupon cannot be redeemed")
        
        # Update status
        coupon.status = CouponStatus.REDEEMED
        return await self.repo.update(coupon)
```

## Repository Layer

```python
# repositories/coupon_repository.py
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.data_model.coupon import Coupon
from repositories.schema_model.coupon_schema import CouponSchema
from core.database import get_db

class CouponRepository:
    def __init__(self, db: AsyncSession = None):
        self.db = db or get_db()
    
    async def create(self, coupon: Coupon) -> Coupon:
        """Persist coupon to database"""
        schema = CouponSchema(
            id=coupon.id,
            title=coupon.title,
            discount=coupon.discount,
            merchant_id=coupon.merchant_id,
            expires_at=coupon.expires_at,
            status=coupon.status.value
        )
        self.db.add(schema)
        await self.db.commit()
        await self.db.refresh(schema)
        return self._to_domain(schema)
    
    async def get_by_id(self, coupon_id: str) -> Optional[Coupon]:
        """Retrieve coupon by ID"""
        result = await self.db.execute(
            select(CouponSchema).where(CouponSchema.id == coupon_id)
        )
        schema = result.scalar_one_or_none()
        return self._to_domain(schema) if schema else None
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Coupon]:
        """List all coupons with pagination"""
        result = await self.db.execute(
            select(CouponSchema).offset(skip).limit(limit)
        )
        schemas = result.scalars().all()
        return [self._to_domain(s) for s in schemas]
    
    async def update(self, coupon: Coupon) -> Coupon:
        """Update existing coupon"""
        schema = await self.db.get(CouponSchema, coupon.id)
        if not schema:
            raise ValueError("Coupon not found")
        
        schema.status = coupon.status.value
        await self.db.commit()
        await self.db.refresh(schema)
        return self._to_domain(schema)
    
    def _to_domain(self, schema: CouponSchema) -> Coupon:
        """Convert SchemaModel to DataModel"""
        return Coupon(
            id=schema.id,
            title=schema.title,
            discount=schema.discount,
            merchant_id=schema.merchant_id,
            expires_at=schema.expires_at,
            status=CouponStatus(schema.status),
            created_at=schema.created_at,
            updated_at=schema.updated_at
        )
```

## OAuth2 Authentication

```python
# core/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return {"user_id": user_id}
    except JWTError:
        raise credentials_exception
```

## Lambda Deployment (Mangum)

```python
# main.py
from fastapi import FastAPI
from mangum import Mangum
from controllers.rest import coupon_controller
from controllers.graphql.coupon_resolver import schema
from strawberry.fastapi import GraphQLRouter

app = FastAPI(title="Mezzofy API")

# REST endpoints
app.include_router(coupon_controller.router)

# GraphQL endpoint
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")

# Lambda handler
handler = Mangum(app)
```

## Database Setup

**Databases used:**
- **PostgreSQL (AWS RDS)** — Core relational data (coupons, merchants, users)
- **DynamoDB** — Logs, cache, audit trails (pay-per-request, auto-scaling)
- **Alembic** — Schema migrations for PostgreSQL

```python
# core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/mezzofy"

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session
```

### Alembic Migrations

```bash
# Initialize alembic (first time)
alembic init alembic

# Generate new migration from SchemaModel changes
alembic revision --autogenerate -m "add_coupon_table"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```

## Testing

```python
# tests/test_coupon_service.py
import pytest
from services.coupon_service import CouponService
from controllers.dto.coupon_dto import CreateCouponDTO
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_create_coupon():
    service = CouponService()
    dto = CreateCouponDTO(
        title="Test Coupon",
        discount=50,
        merchant_id="merchant123",
        expires_at=datetime.utcnow() + timedelta(days=30)
    )
    
    coupon = await service.create_coupon(dto)
    assert coupon.title == "Test Coupon"
    assert coupon.discount == 50
    assert coupon.status == CouponStatus.ACTIVE
```

## Quality Checklist

- [ ] CSR pattern followed (Controller → Service → Repository)
- [ ] Co-located three-model pattern (controllers/dto, services/data_model, repositories/schema_model)
- [ ] No standalone models/ folder — each CSR layer owns its model
- [ ] OAuth2 authentication implemented
- [ ] Pydantic validation on DTOs
- [ ] Business logic in service layer
- [ ] Database operations in repository layer
- [ ] Async/await used throughout
- [ ] Error handling with custom exceptions
- [ ] Unit tests for services
- [ ] Integration tests for endpoints
- [ ] Mangum handler for Lambda deployment
