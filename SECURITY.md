# SECURITY.md — Security Architecture

**JWT authentication, role-based access control (RBAC), Microsoft 365 OAuth, webhook verification, department permissions, API security, and data encryption.**

---

## Security Layers

```
Mobile App / Teams / Webhook Request
    │
    ├── 1. HTTPS / TLS          ──  Encrypted in transit (Nginx SSL)
    ├── 2. JWT Authentication    ──  Valid token? User exists? (mobile/API)
    │      MS 365 OAuth          ──  Azure AD service auth (email/calendar/Teams)
    │      Webhook HMAC          ──  Signature verification (webhooks)
    ├── 3. Role-Based Access     ──  Department + role → permissions
    ├── 4. Permission Check      ──  Can this user use this tool/agent?
    ├── 5. Rate Limiting         ──  Too many requests? (Redis)
    ├── 6. Input Validation      ──  Safe inputs, size limits
    ├── 7. Data Scoping          ──  Users only see their department's data
    └── 8. Audit Logging         ──  Every action recorded
```

---

## 1. JWT Authentication (Mobile App + API)

All API endpoints (except `/auth/login` and `/webhooks/*`) require a valid JWT token.

### Token Structure

```json
{
    "user_id": "user_123",
    "email": "john@mezzofy.com",
    "name": "John Tan",
    "department": "sales",
    "role": "sales_rep",
    "permissions": ["sales_read", "sales_write", "email_send", "linkedin_access", "calendar_access"],
    "exp": 1735689600,
    "iat": 1735603200
}
```

### Token Flow

```
1. User logs in via mobile app → POST /auth/login (email + password)
2. Server validates credentials against users table
3. Server returns:
   - access_token (short-lived, 1 hour)
   - refresh_token (long-lived, 7 days)
4. Mobile app stores tokens securely (iOS Keychain / Android Keystore)
5. All requests include: Authorization: Bearer <access_token>
6. When access_token expires → POST /auth/refresh with refresh_token
```

---

## 2. Microsoft 365 OAuth (Azure AD)

The server authenticates to Microsoft Graph API using **client credentials flow** (application permissions, not delegated). This means the AI assistant acts as a service account — users don't need to individually authorize the app.

### Authentication Flow

```
Server startup → acquire token from Azure AD
    │
    ├── ClientSecretCredential(tenant_id, client_id, client_secret)
    ├── Token cached and auto-refreshed by azure-identity SDK
    └── All MS Graph calls use this service token
```

### Azure AD App Registration

| Setting | Value |
|---------|-------|
| App name | Mezzofy AI Assistant |
| Supported account types | Single tenant (Mezzofy only) |
| Authentication | Client credentials (no redirect URI needed) |
| API permissions | Application permissions (admin-consented) |

### Required API Permissions

| Permission | Type | Purpose |
|-----------|------|---------|
| `Mail.Send` | Application | Send emails via Outlook |
| `Mail.Read` | Application | Read inbox for email tools |
| `Mail.ReadWrite` | Application | Move/categorize emails |
| `Calendars.ReadWrite` | Application | Create/read calendar events |
| `Team.ReadBasic.All` | Application | Read Teams/channel info |
| `ChannelMessage.Send` | Application | Post to Teams channels |
| `Chat.ReadWrite` | Application | Send/read DMs in Teams |
| `Files.ReadWrite.All` | Application | Upload file attachments to Teams |
| `User.Read.All` | Application | Look up user info (for calendar/email tools) |

### Security Considerations

- Client secret stored in `.env` or AWS Secrets Manager (never in code)
- Secret rotation: rotate every 6 months (set reminder in Azure AD)
- Minimum-privilege: only the permissions listed above
- All MS Graph calls logged in audit_log

---

## 3. Webhook Security

### HMAC Signature Verification

Incoming webhooks are verified using HMAC-SHA256 signatures:

```python
import hmac, hashlib

def verify_webhook(payload_bytes, signature, secret):
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### Verification by Source

| Source | Verification Method |
|--------|-------------------|
| Mezzofy product | HMAC-SHA256 signature in `X-Mezzofy-Signature` header |
| MS Teams | Microsoft Bot Framework token validation |
| Custom webhooks | HMAC-SHA256 signature in `X-Webhook-Signature` header |

### Webhook Security Rules

- All webhook endpoints require valid signature — unsigned requests are rejected with 401
- Webhook payloads are validated against expected schema before processing
- Webhooks are processed asynchronously (Celery) — POST returns 200 immediately
- Rate limiting: max 100 webhook events per minute per source
- IP allowlisting (optional): restrict webhook sources by IP range

---

## 4. Role-Based Access Control (RBAC)

### Roles & Permissions

Defined in `/config/roles.yaml`:

```yaml
# config/roles.yaml

departments:
  - finance
  - sales
  - marketing
  - support
  - management

roles:
  # Finance Department
  finance_viewer:
    department: finance
    permissions:
      - finance_read

  finance_manager:
    department: finance
    permissions:
      - finance_read
      - finance_write
      - email_send
      - calendar_access
      - scheduler_manage         # Can create scheduled finance reports

  # Sales Department
  sales_rep:
    department: sales
    permissions:
      - sales_read
      - sales_write
      - email_send
      - linkedin_access
      - calendar_access

  sales_manager:
    department: sales
    permissions:
      - sales_read
      - sales_write
      - email_send
      - linkedin_access
      - calendar_access
      - sales_admin
      - scheduler_manage

  # Marketing Department
  marketing_creator:
    department: marketing
    permissions:
      - marketing_read
      - marketing_write
      - email_send

  marketing_manager:
    department: marketing
    permissions:
      - marketing_read
      - marketing_write
      - email_send
      - marketing_admin
      - scheduler_manage

  # Support Department
  support_agent:
    department: support
    permissions:
      - support_read
      - support_write
      - email_send

  support_manager:
    department: support
    permissions:
      - support_read
      - support_write
      - email_send
      - support_admin
      - scheduler_manage

  # Management
  executive:
    department: management
    permissions:
      - management_read
      - management_admin
      - finance_read
      - sales_read
      - marketing_read
      - support_read
      - audit_read
      - email_send
      - calendar_access
      - scheduler_manage
      - teams_post                # Can post to any Teams channel

  admin:
    department: management
    permissions:
      - "*"                      # All permissions
```

### Permission → Tool Mapping

| Permission | Tools Accessible |
|-----------|------------------|
| `finance_read` | `query_financial`, `financial_query`, `financial_format` |
| `finance_write` | (future: create invoices, update records) |
| `sales_read` | `search_leads`, `get_lead`, `get_pipeline`, `export_leads` |
| `sales_write` | `create_lead`, `update_lead` |
| `linkedin_access` | `linkedin_search`, `linkedin_extract` |
| `email_send` | `outlook_send_email`, `outlook_batch_send`, `outlook_reply_email` |
| `calendar_access` | `outlook_create_event`, `outlook_get_events`, `outlook_find_free_slots` |
| `teams_post` | `teams_post_message` (any channel) |
| `scheduler_manage` | Create/delete scheduled jobs for own department |
| `marketing_read` | `get_products`, `search_knowledge`, `get_brand_guidelines` |
| `marketing_write` | `generate_content`, `create_pdf`, `create_docx` |
| `support_read` | `query_tickets` |
| `support_write` | (future: update tickets, add notes) |
| `management_read` | All read queries across departments |
| `audit_read` | `query_audit_log` |

---

## 5. Data Scoping

Users only see data relevant to their department and role:

| Department | Can See |
|-----------|---------|
| Finance | Financial data, company-wide financial reports |
| Sales | Own leads (reps), all leads (managers), CRM data |
| Marketing | Product data, brand assets, marketing analytics |
| Support | Support tickets, knowledge base |
| Management | All department data (read-only), audit logs, KPIs |

---

## 6. Rate Limiting

### Per-User Limits

```yaml
security:
  rate_limiting:
    requests_per_minute: 30
    email_sends_per_hour: 30
    linkedin_searches_per_hour: 20
    file_generations_per_hour: 50
    webhook_events_per_minute: 100
```

- Tracked in Redis per user_id (or per webhook source)
- Returns HTTP 429 when exceeded
- Management/admin roles have higher limits

---

## 7. API Security

### HTTPS / TLS

All traffic encrypted via Nginx with SSL certificate (Let's Encrypt or ACM).

### Input Validation

- Max request body: 10 MB (text)
- Max media upload: 100 MB (video), 50 MB (audio), 20 MB (image/file)
- Message length: max 5,000 characters
- Image uploads: resized server-side to max 2048px before Vision API
- Video uploads: max 5 minutes duration
- Live speech: audio chunks validated for format (PCM/WAV)
- Live camera: frames validated as JPEG, rate limited to 1 fps
- URL inputs: validated against blocklist (no internal IPs, no localhost)
- Webhook payloads: validated against schema + signature

---

## 8. Audit Logging

Every significant action is logged to the `audit_log` table:

```sql
CREATE TABLE audit_log (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,           -- "system" for scheduler/webhook actions
    department  TEXT NOT NULL,
    action      TEXT NOT NULL,
    source      TEXT DEFAULT 'mobile',   -- mobile | webhook | scheduler | teams
    details     JSONB,
    ip_address  TEXT,
    user_agent  TEXT,
    timestamp   TIMESTAMPTZ DEFAULT NOW()
);
```

### What Gets Logged

- Every chat message sent (mobile, Teams, scheduled)
- Every Outlook email sent (recipient, subject)
- Every calendar event created
- Every Teams message posted
- Every lead created/updated
- Every file generated (type, name)
- Every login/logout
- Every webhook event received + processed
- Every scheduled job execution (start, result, duration)
- Permission denials
- Rate limit hits
- MS Graph API errors

---

## 9. Secrets Management

### Storage

All secrets in `.env` file on EC2, never in Git:

```bash
# .env
JWT_SECRET=<random-256-bit-key>
ANTHROPIC_API_KEY=sk-ant-...
KIMI_API_KEY=sk-...
DATABASE_URL=postgresql://user:pass@localhost:5432/mezzofy_ai
MS365_TENANT_ID=<azure-ad-tenant-id>
MS365_CLIENT_ID=<app-client-id>
MS365_CLIENT_SECRET=<app-client-secret>
MS_TEAMS_TEAM_ID=<teams-team-id>
LINKEDIN_COOKIE=...
WEBHOOK_SECRET=<hmac-secret>
```

### AWS Integration (Recommended for Production)

- Use **AWS Secrets Manager** or **AWS Parameter Store** instead of .env
- Rotate MS365 client secret every 6 months
- Access via IAM roles (no hardcoded credentials)

---

## Security Checklist

- [ ] JWT_SECRET is a strong random key (256-bit minimum)
- [ ] `.env` is gitignored, not committed
- [ ] MS365 app registered in Azure AD with minimum permissions
- [ ] MS365 client secret rotated every 6 months
- [ ] Admin consent granted for MS Graph API permissions
- [ ] Webhook HMAC secret configured and verified
- [ ] PostgreSQL password is strong, connection uses SSL
- [ ] Nginx configured with TLS 1.3, valid SSL cert
- [ ] CORS restricted to app domain
- [ ] All roles defined in `roles.yaml` with least-privilege permissions
- [ ] Rate limiting configured and tested (including webhooks)
- [ ] Audit logging enabled for all sensitive actions
- [ ] LinkedIn scraping respects rate limits
- [ ] Database queries parameterized (no SQL injection)
- [ ] File uploads validated (type + size)
- [ ] Celery workers isolated (no shell access)
- [ ] Redis password-protected in production
- [ ] AWS security groups restrict EC2 access (SSH from office IP only, HTTPS public)
