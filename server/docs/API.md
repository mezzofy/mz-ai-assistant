# Mezzofy AI Assistant — API Reference
**Version:** 1.0
**Base URL:** `https://api.mezzofy.com` (production) · `http://localhost:8000` (development)
**Interactive Docs:** `GET /docs` (Swagger UI) · `GET /redoc` (ReDoc)
**Auth:** Bearer JWT — obtain from `POST /auth/login`

---

## Authentication

All endpoints (except `/auth/login`, `/auth/refresh`, `/health`) require:
```
Authorization: Bearer <access_token>
```

Access tokens expire after **60 minutes**. Use `POST /auth/refresh` to renew.

---

## Auth Endpoints

### POST /auth/login

Authenticate with email and password. Returns access + refresh tokens and full user info.

**Rate limit:** 10 requests/minute per IP

**Request**
```json
{
  "email": "user@mezzofy.com",
  "password": "yourpassword"
}
```

**Response 200**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_info": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "user@mezzofy.com",
    "name": "Jane Smith",
    "department": "sales",
    "role": "sales_rep",
    "permissions": ["chat", "files.read", "files.write", "leads.read", "leads.write"]
  }
}
```

**Errors:** `401` invalid credentials · `401` account inactive

---

### POST /auth/refresh

Exchange a valid refresh token for a new access token. Refresh tokens are **not rotated** — keep the original.

**Request**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response 200**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Errors:** `401` invalid/expired/revoked refresh token

---

### POST /auth/logout

Revoke the refresh token. Requires a valid Bearer access token in the header.

**Request**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `204 No Content`

**Notes:** Idempotent — succeeds silently if the token is already invalid.

---

### GET /auth/me

Return the current user's profile from the JWT payload (no DB call).

**Response 200**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@mezzofy.com",
  "name": "Jane Smith",
  "department": "sales",
  "role": "sales_rep",
  "permissions": ["chat", "files.read", "files.write", "leads.read", "leads.write"]
}
```

---

## Chat Endpoints

All chat endpoints read the authenticated user from the JWT set by `ChatGatewayMiddleware`.

### POST /chat/send

Send a plain text message to the AI assistant. The server routes to the appropriate agent based on department and message intent.

**Request**
```json
{
  "message": "Summarise last month's sales pipeline for Singapore",
  "session_id": "a1b2c3d4-optional-to-continue-a-conversation"
}
```

**Response 200**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Here is last month's Singapore pipeline summary...",
  "agent_used": "sales_agent",
  "artifacts": [],
  "tokens_used": 842,
  "input_summary": ""
}
```

**Notes:** `session_id` in the response is the canonical ID for this conversation. Omit it on first message; include it on subsequent messages to continue the same session.

---

### POST /chat/send-media

Send a file (image, video, audio, document) with an optional text message.

**Content-Type:** `multipart/form-data`

**Fields:**

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `media_file` | file | ✅ | The file to upload |
| `input_type` | string | ✅ | `image` / `video` / `audio` / `file` |
| `message` | string | | Optional text context |
| `session_id` | string | | Existing session to continue |

**Response 200** — same shape as `/chat/send`

**Errors:** `400` unsupported `input_type`

---

### POST /chat/send-url

Fetch a URL, scrape its content, and send to the AI for analysis.

**Request**
```json
{
  "url": "https://example.com/article",
  "message": "Summarise this for me",
  "session_id": null
}
```

**Response 200** — same shape as `/chat/send`

**Security:** Blocks localhost, RFC 1918 ranges, and AWS metadata endpoint (SSRF protection).

---

### GET /chat/sessions

List all conversation sessions for the current user.

**Query Params:** `limit` (default 20) · `offset` (default 0)

**Response 200**
```json
{
  "sessions": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "department": "sales",
      "created_at": "2026-02-28T08:00:00Z",
      "updated_at": "2026-02-28T09:15:00Z",
      "message_count": 12
    }
  ],
  "total": 1
}
```

---

### GET /chat/history/{session_id}

Retrieve the full message history for a session. Only accessible by the session owner.

**Response 200**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "messages": [
    {
      "role": "user",
      "content": "Summarise last month's pipeline",
      "created_at": "2026-02-28T08:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Here is the summary...",
      "agent_used": "sales_agent",
      "created_at": "2026-02-28T08:00:05Z"
    }
  ]
}
```

---

### DELETE /chat/session/{session_id}

Clear all messages from a session (soft reset — session record is kept).

**Response 200**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "cleared": true
}
```

**Errors:** `404` session not found or not owned by current user

---

### WS /chat/ws

Real-time WebSocket for speech input, live camera frames, and streaming text responses.

**Auth:** JWT passed as query parameter — `wss://api.mezzofy.com/chat/ws?token=<access_token>`

**Client → Server messages:**

| Type | Fields | Description |
|------|--------|-------------|
| `text` | `message`, `session_id` | Send a text message |
| `speech_start` | — | Begin a speech recording session |
| `speech_audio` | `data` (base64 chunk) | Stream an audio chunk |
| `speech_end` | — | End recording; trigger transcription |
| `camera_frame` | `data` (base64 JPEG) | Send a live camera frame for analysis |

**Server → Client messages:**

| Type | Fields | Description |
|------|--------|-------------|
| `transcript` | `text`, `is_final` | Real-time speech transcript |
| `camera_analysis` | `description` | Analysis of received camera frame |
| `status` | `message` | Processing status update |
| `complete` | `response` (object) | Final AI response |
| `error` | `detail` | Error message |

---

## Files Endpoints

### POST /files/upload

Upload a file to the artifact store. Returns an `artifact_id` for use in `/chat/send-media`.

**Content-Type:** `multipart/form-data`

**Accepted MIME types:** `image/*`, `video/*`, `audio/*`, `application/pdf`, `application/vnd.openxmlformats-officedocument.*`, `text/plain`, `text/csv`

**Response 200**
```json
{
  "artifact_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "quarterly-report.pdf",
  "file_type": "pdf",
  "size_bytes": 204800,
  "download_url": "/files/3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

**Errors:** `415` unsupported MIME type

---

### GET /files/

List all artifacts (uploads + AI-generated files) for the current user.

**Query Params:** `limit` (default 50) · `offset` (default 0)

**Response 200**
```json
{
  "artifacts": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "filename": "Q1-2026-Sales-Report.pdf",
      "file_type": "pdf",
      "download_url": "/files/3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "created_at": "2026-02-28T10:00:00Z"
    }
  ],
  "count": 1
}
```

---

### GET /files/{file_id}

Download an artifact by ID. Only accessible by the owning user.

**Response:** File stream with appropriate `Content-Type` header

**Errors:** `404` file not found or access denied

---

### DELETE /files/{file_id}

Delete the artifact record from the database. The underlying file is retained on disk for audit purposes.

**Response 200**
```json
{
  "deleted": true,
  "artifact_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

**Errors:** `404` file not found or not owned by current user

---

## Admin Endpoints

All admin endpoints require `role=admin` or `role=executive`. Marked with `[admin-only]` if restricted to `admin` only.

### GET /admin/users

List all users, optionally filtered by department.

**Query Params:** `limit` · `offset` · `department`

**Response 200**
```json
{
  "users": [
    {
      "id": "3fa85f64-...",
      "email": "user@mezzofy.com",
      "name": "Jane Smith",
      "department": "sales",
      "role": "sales_rep",
      "is_active": true,
      "created_at": "2026-01-15T00:00:00Z"
    }
  ],
  "total": 1
}
```

---

### POST /admin/users `[admin-only]`

Create a new user account.

**Request**
```json
{
  "email": "newuser@mezzofy.com",
  "name": "John Doe",
  "password": "SecurePassword123!",
  "department": "marketing",
  "role": "marketing_rep",
  "permissions": []
}
```

**Response 201**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "newuser@mezzofy.com",
  "name": "John Doe",
  "department": "marketing",
  "role": "marketing_rep"
}
```

**Errors:** `409` email already registered

---

### PUT /admin/users/{id} `[admin-only]`

Update a user's role, department, permissions, or active status.

**Request** (all fields optional)
```json
{
  "role": "marketing_manager",
  "department": "marketing",
  "permissions": ["chat", "files.read", "files.write", "campaigns.manage"],
  "is_active": true
}
```

**Response 200** — updated user object

---

### GET /admin/audit

Retrieve the audit log. Admin and executive roles only.

**Query Params:** `limit` · `offset` · `user_id` · `action`

**Response 200**
```json
{
  "entries": [
    {
      "id": "...",
      "user_id": "...",
      "action": "login",
      "resource": "auth",
      "success": true,
      "ip_address": "1.2.3.4",
      "created_at": "2026-02-28T08:00:00Z"
    }
  ]
}
```

---

### GET /admin/health `[admin-only]`

System health dashboard — DB, Redis, Celery, and disk status.

**Response 200**
```json
{
  "status": "healthy",
  "database": "ok",
  "redis": "ok",
  "celery_workers": 4,
  "disk_usage_pct": 42
}
```

---

## Scheduler Endpoints

### GET /scheduler/jobs

List the current user's scheduled jobs.

**Response 200**
```json
{
  "jobs": [
    {
      "id": "3fa85f64-...",
      "name": "Weekly Sales Report",
      "cron_expression": "0 9 * * 1",
      "task_type": "agent_task",
      "is_active": true,
      "last_run": "2026-02-24T09:00:00Z",
      "next_run": "2026-03-03T09:00:00Z"
    }
  ],
  "count": 1
}
```

---

### POST /scheduler/jobs

Create a new scheduled job.

**Constraints:** Max 10 active jobs per user · Minimum 15-minute interval

**Request**
```json
{
  "name": "Weekly Sales Report",
  "description": "Generate and email the weekly sales pipeline report",
  "schedule": {
    "type": "cron",
    "cron": "0 9 * * 1"
  },
  "task_type": "agent_task",
  "task_params": {
    "agent": "sales",
    "message": "Generate the weekly sales pipeline report"
  }
}
```

**Response 201** — created job object

**Errors:** `400` schedule validation · `429` max jobs limit reached

---

### GET /scheduler/jobs/{id}

Get details for a specific scheduled job.

---

### PUT /scheduler/jobs/{id}

Update a scheduled job. Owner or admin only.

---

### DELETE /scheduler/jobs/{id}

Delete a scheduled job. Owner or admin only.

---

### POST /scheduler/jobs/{id}/run

Trigger a job to run immediately (does not wait for the next cron time).

**Response 200**
```json
{
  "job_id": "3fa85f64-...",
  "task_id": "celery-task-uuid",
  "status": "queued"
}
```

---

## Webhook Endpoints

All webhook endpoints return `200` immediately and process events asynchronously via Celery.

### POST /webhooks/mezzofy

Receive events from the Mezzofy platform (customer signup, churn, orders, support tickets).

**Security:** `X-Webhook-Signature` header — HMAC-SHA256 of request body with `WEBHOOK_SECRET`

**Supported events:** `customer_signed_up` · `customer_churned` · `order_completed` · `support_ticket_created` · `feature_released`

**Response 200**
```json
{ "received": true, "event_id": "webhook-event-uuid" }
```

---

### POST /webhooks/teams

Receive adaptive card actions and @mentions from the Microsoft Teams bot.

**Security:** `TEAMS_BOT_SECRET` bearer token in `Authorization` header

---

### POST /webhooks/custom/{source}

Generic webhook receiver for Zapier, GitHub, Stripe, and other external tools.

**Path Param:** `source` — must be one of `zapier`, `github`, `stripe`

**Security:** `X-Webhook-Signature` header — HMAC-SHA256 signature

---

## Health Endpoint

### GET /health

Unauthenticated health check.

**Response 200**
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected"
}
```

---

## Error Format

All errors follow RFC 7807 Problem Details:

```json
{
  "detail": "Invalid email or password"
}
```

**Common status codes:**

| Code | Meaning |
|------|---------|
| `400` | Bad request / validation error |
| `401` | Missing or invalid JWT / credentials |
| `403` | Insufficient role/permissions |
| `404` | Resource not found or access denied |
| `415` | Unsupported media type |
| `422` | Request body schema validation error |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

---

## Rate Limits

| Endpoint group | Limit |
|----------------|-------|
| Auth (`/auth/*`) | 10 req/min per IP |
| Chat (`/chat/*`) | 30 req/min per user |
| Email sends | 30/hour per user |
| LinkedIn searches | 20/hour per user |
| File generations | 50/hour per user |
| Webhook events | 100/min |

---

*Generated: 2026-02-28 · mz-ai-assistant v1.0*
