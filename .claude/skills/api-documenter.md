---
name: api-documenter
description: API documentation specialist for creating comprehensive OpenAPI specifications, GraphQL schemas, API reference guides, and SDK generation. Use for REST API documentation, GraphQL type definitions, Postman collections, integration guides, authentication flows, error handling documentation, and developer onboarding materials for coupon exchange platform APIs.
---

# API Documenter

Create comprehensive, developer-friendly API documentation.

## Tech Stack

- **OpenAPI**: 3.1 specification
- **GraphQL**: Schema-first with Strawberry
- **Tools**: Swagger UI, GraphQL Playground, Postman
- **Docs**: Markdown + Docusaurus
- **SDK Generation**: openapi-generator, graphql-code-generator

## OpenAPI 3.1 Specification

### Complete API Specification

```yaml
# openapi.yaml
openapi: 3.1.0
info:
  title: Mezzofy API
  version: 2.0.0
  description: |
    RESTful API for Mezzofy coupon exchange platform.
    
    ## Authentication
    All endpoints require Bearer token authentication except `/auth/*` endpoints.
    
    ## Rate Limiting
    - Public endpoints: 100 requests/hour per IP
    - Authenticated endpoints: 1000 requests/hour per user
    
    ## Environments
    - **Production**: https://api.mezzofy.com
    - **Staging**: https://api-staging.mezzofy.com
    - **Development**: http://localhost:8000
  contact:
    name: Mezzofy API Support
    email: api@mezzofy.com
    url: https://docs.mezzofy.com
  license:
    name: Proprietary
    url: https://mezzofy.com/terms

servers:
  - url: https://api.mezzofy.com/v2
    description: Production server
  - url: https://api-staging.mezzofy.com/v2
    description: Staging server
  - url: http://localhost:8000/v2
    description: Development server

tags:
  - name: Authentication
    description: User authentication and authorization
  - name: Coupons
    description: Coupon management operations
  - name: Redemptions
    description: Coupon redemption operations
  - name: Users
    description: User management

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: |
        JWT token obtained from `/auth/login` endpoint.
        
        Example: `Authorization: Bearer eyJhbGciOiJIUzI1NiIs...`

  schemas:
    Coupon:
      type: object
      required:
        - id
        - title
        - discount
        - discountType
        - merchantId
        - expiresAt
        - status
      properties:
        id:
          type: string
          format: uuid
          example: "550e8400-e29b-41d4-a716-446655440000"
        title:
          type: string
          minLength: 3
          maxLength: 100
          example: "50% Off Italian Restaurant"
        description:
          type: string
          maxLength: 500
          example: "Get 50% off your entire meal at Luigi's Bistro"
        discount:
          type: number
          minimum: 0
          example: 50
        discountType:
          type: string
          enum: [percentage, fixed, bogo, shipping]
          example: "percentage"
        merchantId:
          type: string
          format: uuid
          example: "7c9e6679-7425-40de-944b-e07fc1f90ae7"
        merchantName:
          type: string
          example: "Luigi's Bistro"
        expiresAt:
          type: string
          format: date-time
          example: "2025-12-31T23:59:59Z"
        status:
          type: string
          enum: [draft, active, expired, redeemed, suspended, cancelled]
          example: "active"
        maxUses:
          type: integer
          minimum: 1
          nullable: true
          example: 1000
        currentUses:
          type: integer
          minimum: 0
          example: 247
        createdAt:
          type: string
          format: date-time
          example: "2025-01-01T00:00:00Z"
        updatedAt:
          type: string
          format: date-time
          example: "2025-01-15T10:30:00Z"

    CreateCouponRequest:
      type: object
      required:
        - title
        - discount
        - discountType
        - merchantId
        - expiresAt
      properties:
        title:
          type: string
          minLength: 3
          maxLength: 100
        description:
          type: string
          maxLength: 500
        discount:
          type: number
          minimum: 0
        discountType:
          type: string
          enum: [percentage, fixed, bogo, shipping]
        merchantId:
          type: string
          format: uuid
        expiresAt:
          type: string
          format: date-time
        maxUses:
          type: integer
          minimum: 1
          nullable: true

    Error:
      type: object
      required:
        - error
        - message
      properties:
        error:
          type: string
          example: "ValidationError"
        message:
          type: string
          example: "Discount must be between 0 and 100"
        details:
          type: object
          nullable: true
          additionalProperties: true

  responses:
    Unauthorized:
      description: Authentication required
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            error: "Unauthorized"
            message: "Valid authentication token required"

    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            error: "NotFound"
            message: "Coupon not found"

    ValidationError:
      description: Invalid request data
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
          example:
            error: "ValidationError"
            message: "Invalid request data"
            details:
              discount: "Must be between 0 and 100"

security:
  - BearerAuth: []

paths:
  /auth/login:
    post:
      tags:
        - Authentication
      summary: User login
      description: Authenticate user and receive JWT token
      security: []  # No auth required
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - email
                - password
              properties:
                email:
                  type: string
                  format: email
                  example: "user@example.com"
                password:
                  type: string
                  format: password
                  example: "SecurePassword123!"
      responses:
        '200':
          description: Login successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  accessToken:
                    type: string
                    example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                  refreshToken:
                    type: string
                    example: "8f7d6e5c4b3a2..."
                  expiresIn:
                    type: integer
                    example: 3600
        '401':
          description: Invalid credentials
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

  /coupons:
    get:
      tags:
        - Coupons
      summary: List coupons
      description: Retrieve paginated list of coupons with optional filters
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            minimum: 1
            default: 1
          description: Page number
        - name: limit
          in: query
          schema:
            type: integer
            minimum: 1
            maximum: 100
            default: 20
          description: Items per page
        - name: status
          in: query
          schema:
            type: string
            enum: [draft, active, expired, redeemed]
          description: Filter by status
        - name: merchantId
          in: query
          schema:
            type: string
            format: uuid
          description: Filter by merchant
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: array
                    items:
                      $ref: '#/components/schemas/Coupon'
                  pagination:
                    type: object
                    properties:
                      page:
                        type: integer
                        example: 1
                      limit:
                        type: integer
                        example: 20
                      total:
                        type: integer
                        example: 150
                      pages:
                        type: integer
                        example: 8
        '401':
          $ref: '#/components/responses/Unauthorized'

    post:
      tags:
        - Coupons
      summary: Create coupon
      description: Create a new coupon
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateCouponRequest'
      responses:
        '201':
          description: Coupon created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Coupon'
        '400':
          $ref: '#/components/responses/ValidationError'
        '401':
          $ref: '#/components/responses/Unauthorized'

  /coupons/{couponId}:
    get:
      tags:
        - Coupons
      summary: Get coupon by ID
      description: Retrieve detailed information about a specific coupon
      parameters:
        - name: couponId
          in: path
          required: true
          schema:
            type: string
            format: uuid
          description: Coupon ID
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Coupon'
        '404':
          $ref: '#/components/responses/NotFound'

  /coupons/{couponId}/redeem:
    post:
      tags:
        - Redemptions
      summary: Redeem coupon
      description: |
        Redeem a coupon for the authenticated user.
        
        ## Business Rules
        - Coupon must be in `active` status
        - Coupon must not be expired
        - User must not have exceeded usage limits
        - Biometric verification may be required for high-value coupons
      parameters:
        - name: couponId
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: false
        content:
          application/json:
            schema:
              type: object
              properties:
                location:
                  type: string
                  example: "123 Main St, San Francisco, CA"
                nfcSignature:
                  type: string
                  example: "a7f3b2c1d4e5..."
      responses:
        '200':
          description: Redemption successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  redemptionId:
                    type: string
                    format: uuid
                  couponId:
                    type: string
                    format: uuid
                  redeemedAt:
                    type: string
                    format: date-time
                  discountApplied:
                    type: number
        '400':
          description: Cannot redeem coupon
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
              examples:
                expired:
                  value:
                    error: "CouponExpired"
                    message: "This coupon has expired"
                limitReached:
                  value:
                    error: "UsageLimitReached"
                    message: "You have reached the usage limit for this coupon"
```

## GraphQL Schema Documentation

```graphql
"""
Mezzofy GraphQL API

Authentication: Include JWT token in Authorization header
Example: Authorization: Bearer <token>
"""
schema {
  query: Query
  mutation: Mutation
}

"""
Main query type
"""
type Query {
  """
  Get a single coupon by ID
  
  Example:
  ```graphql
  query {
    coupon(id: "550e8400-e29b-41d4-a716-446655440000") {
      id
      title
      discount
      merchant {
        name
      }
    }
  }
  ```
  """
  coupon(id: ID!): Coupon
  
  """
  List coupons with optional filters
  
  Example:
  ```graphql
  query {
    coupons(status: ACTIVE, limit: 10) {
      edges {
        node {
          id
          title
        }
      }
      pageInfo {
        hasNextPage
      }
    }
  }
  ```
  """
  coupons(
    status: CouponStatus
    merchantId: ID
    first: Int = 20
    after: String
  ): CouponConnection!
  
  """
  Get current authenticated user
  """
  me: User!
}

"""
Main mutation type
"""
type Mutation {
  """
  Create a new coupon
  
  Requires: MERCHANT role
  
  Example:
  ```graphql
  mutation {
    createCoupon(input: {
      title: "50% Off Pizza"
      discount: 50
      discountType: PERCENTAGE
      merchantId: "7c9e6679-7425-40de-944b-e07fc1f90ae7"
      expiresAt: "2025-12-31T23:59:59Z"
    }) {
      coupon {
        id
        title
      }
      errors {
        field
        message
      }
    }
  }
  ```
  """
  createCoupon(input: CreateCouponInput!): CreateCouponPayload!
  
  """
  Redeem a coupon
  
  Business rules:
  - Coupon must be ACTIVE
  - Coupon must not be expired
  - User usage limits apply
  
  Example:
  ```graphql
  mutation {
    redeemCoupon(couponId: "550e8400...") {
      redemption {
        id
        redeemedAt
      }
      errors {
        message
      }
    }
  }
  ```
  """
  redeemCoupon(couponId: ID!): RedeemCouponPayload!
}

"""
Coupon entity
"""
type Coupon {
  """Unique identifier"""
  id: ID!
  
  """Coupon title (3-100 characters)"""
  title: String!
  
  """Detailed description (max 500 characters)"""
  description: String
  
  """Discount amount"""
  discount: Float!
  
  """Type of discount"""
  discountType: DiscountType!
  
  """Associated merchant"""
  merchant: Merchant!
  
  """Expiration date and time"""
  expiresAt: DateTime!
  
  """Current status"""
  status: CouponStatus!
  
  """Maximum number of uses (null = unlimited)"""
  maxUses: Int
  
  """Current number of uses"""
  currentUses: Int!
  
  """Creation timestamp"""
  createdAt: DateTime!
  
  """Last update timestamp"""
  updatedAt: DateTime!
  
  """Check if coupon is expired"""
  isExpired: Boolean!
  
  """Check if coupon can be redeemed"""
  canRedeem: Boolean!
}

"""
Discount type enumeration
"""
enum DiscountType {
  """Percentage discount (e.g., 50% off)"""
  PERCENTAGE
  
  """Fixed amount discount (e.g., $10 off)"""
  FIXED
  
  """Buy one get one"""
  BOGO
  
  """Free shipping"""
  SHIPPING
}

"""
Coupon status enumeration
"""
enum CouponStatus {
  DRAFT
  ACTIVE
  EXPIRED
  REDEEMED
  SUSPENDED
  CANCELLED
}

"""
Date and time scalar (ISO 8601 format)
"""
scalar DateTime

"""
Input for creating a coupon
"""
input CreateCouponInput {
  title: String!
  description: String
  discount: Float!
  discountType: DiscountType!
  merchantId: ID!
  expiresAt: DateTime!
  maxUses: Int
}

"""
Payload for createCoupon mutation
"""
type CreateCouponPayload {
  """Created coupon (null if errors)"""
  coupon: Coupon
  
  """Validation or business logic errors"""
  errors: [Error!]
}

"""
Error type
"""
type Error {
  """Error code"""
  code: String!
  
  """Human-readable error message"""
  message: String!
  
  """Field that caused the error (for validation errors)"""
  field: String
}
```

## Integration Guide

````markdown
# Mezzofy API Integration Guide

## Getting Started

### 1. Obtain API Credentials

Contact api@mezzofy.com to request:
- Client ID
- Client Secret
- Portal-specific permissions

### 2. Authentication

```bash
# Get access token
curl -X POST https://api.mezzofy.com/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your@email.com",
    "password": "your-password"
  }'

# Response
{
  "accessToken": "eyJhbGci...",
  "refreshToken": "8f7d6e5c...",
  "expiresIn": 3600
}
```

### 3. Making Authenticated Requests

```bash
curl -X GET https://api.mezzofy.com/v2/coupons \
  -H "Authorization: Bearer eyJhbGci..."
```

## Code Examples

### JavaScript/TypeScript

```typescript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'https://api.mezzofy.com/v2',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Get coupons
const coupons = await apiClient.get('/coupons', {
  params: { status: 'active', limit: 20 }
});

// Create coupon
const newCoupon = await apiClient.post('/coupons', {
  title: '50% Off Pizza',
  discount: 50,
  discountType: 'percentage',
  merchantId: '7c9e6679-7425-40de-944b-e07fc1f90ae7',
  expiresAt: '2025-12-31T23:59:59Z',
});

// Redeem coupon
const redemption = await apiClient.post(
  `/coupons/${couponId}/redeem`
);
```

### Python

```python
import requests

class MezzofyClient:
    def __init__(self, access_token):
        self.base_url = 'https://api.mezzofy.com/v2'
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        })
    
    def get_coupons(self, status=None, limit=20):
        params = {'limit': limit}
        if status:
            params['status'] = status
        
        response = self.session.get(
            f'{self.base_url}/coupons',
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def create_coupon(self, coupon_data):
        response = self.session.post(
            f'{self.base_url}/coupons',
            json=coupon_data
        )
        response.raise_for_status()
        return response.json()
    
    def redeem_coupon(self, coupon_id):
        response = self.session.post(
            f'{self.base_url}/coupons/{coupon_id}/redeem'
        )
        response.raise_for_status()
        return response.json()

# Usage
client = MezzofyClient(access_token='your-token')
coupons = client.get_coupons(status='active')
```

## Error Handling

All error responses follow this format:

```json
{
  "error": "ErrorCode",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional context"
  }
}
```

### Common Error Codes

- `Unauthorized` (401): Missing or invalid authentication token
- `Forbidden` (403): Insufficient permissions
- `NotFound` (404): Resource not found
- `ValidationError` (400): Invalid request data
- `RateLimitExceeded` (429): Too many requests

### Retry Strategy

```typescript
async function apiCallWithRetry(fn, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (error.response?.status === 429) {
        // Rate limited, wait and retry
        await sleep(2 ** i * 1000);
        continue;
      }
      throw error;
    }
  }
  throw new Error('Max retries exceeded');
}
```

## Webhooks

Subscribe to events:
- `coupon.created`
- `coupon.redeemed`
- `coupon.expired`

```bash
POST /webhooks
{
  "url": "https://your-domain.com/webhook",
  "events": ["coupon.redeemed"],
  "secret": "your-webhook-secret"
}
```

Webhook payload:

```json
{
  "event": "coupon.redeemed",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": {
    "couponId": "550e8400-...",
    "userId": "7c9e6679-...",
    "redeemedAt": "2025-01-15T10:30:00Z"
  },
  "signature": "sha256=..."
}
```
````

## Postman Collection

```json
{
  "info": {
    "name": "Mezzofy API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "baseUrl",
      "value": "https://api.mezzofy.com/v2"
    },
    {
      "key": "accessToken",
      "value": ""
    }
  ],
  "auth": {
    "type": "bearer",
    "bearer": [
      {
        "key": "token",
        "value": "{{accessToken}}"
      }
    ]
  },
  "item": [
    {
      "name": "Authentication",
      "item": [
        {
          "name": "Login",
          "request": {
            "method": "POST",
            "url": "{{baseUrl}}/auth/login",
            "body": {
              "mode": "raw",
              "raw": "{\n  \"email\": \"user@example.com\",\n  \"password\": \"password123\"\n}"
            }
          }
        }
      ]
    },
    {
      "name": "Coupons",
      "item": [
        {
          "name": "List Coupons",
          "request": {
            "method": "GET",
            "url": {
              "raw": "{{baseUrl}}/coupons?status=active&limit=20",
              "query": [
                { "key": "status", "value": "active" },
                { "key": "limit", "value": "20" }
              ]
            }
          }
        },
        {
          "name": "Create Coupon",
          "request": {
            "method": "POST",
            "url": "{{baseUrl}}/coupons",
            "body": {
              "mode": "raw",
              "raw": "{\n  \"title\": \"50% Off Pizza\",\n  \"discount\": 50,\n  \"discountType\": \"percentage\",\n  \"merchantId\": \"7c9e6679-7425-40de-944b-e07fc1f90ae7\",\n  \"expiresAt\": \"2025-12-31T23:59:59Z\"\n}"
            }
          }
        }
      ]
    }
  ]
}
```

## Quality Checklist

- [ ] OpenAPI 3.1 specification complete
- [ ] All endpoints documented
- [ ] Request/response examples provided
- [ ] Authentication flow explained
- [ ] Error codes documented
- [ ] Rate limits specified
- [ ] GraphQL schema documented
- [ ] Integration guide written
- [ ] Code examples in multiple languages
- [ ] Postman collection exported
- [ ] Webhook documentation complete
- [ ] SDK generation configured
- [ ] Changelog maintained
- [ ] Breaking changes highlighted
- [ ] Developer portal published
