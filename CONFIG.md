# CONFIG.md — Configuration Reference

**All configuration files, environment variables, roles, and dependencies.**

---

## Configuration Files

```
/server/config
├── config.yaml             # Main configuration
├── config.example.yaml     # Template (committed to Git)
├── roles.yaml              # RBAC role + permission definitions
└── .env                    # Secrets (gitignored)
```

---

## Main Configuration (`config/config.yaml`)

### LLM

```yaml
llm:
  default_model: "claude"
  fallback_model: "kimi"

  claude:
    provider: "anthropic"
    model: "claude-sonnet-4-5-20250929"
    api_key: "${ANTHROPIC_API_KEY}"
    max_tokens: 4096
    temperature: 0.7

  kimi:
    provider: "moonshot"
    model: "moonshot-v1-128k"
    api_key: "${KIMI_API_KEY}"
    base_url: "https://api.moonshot.cn/v1"
    max_tokens: 4096
    temperature: 0.7

  routing:
    chinese_content: "kimi"
    apac_research: "kimi"
    default: "claude"
```

### API Server

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4                     # Uvicorn workers
  debug: false

  nginx:
    ssl_cert: "/etc/letsencrypt/live/api.mezzofy.com/fullchain.pem"
    ssl_key: "/etc/letsencrypt/live/api.mezzofy.com/privkey.pem"
```

### Database

```yaml
database:
  url: "${DATABASE_URL}"           # postgresql://user:pass@localhost:5432/mezzofy_ai
  pool_size: 10
  max_overflow: 20
```

### Microsoft 365 (Outlook Email + Calendar)

```yaml
ms365:
  enabled: true
  tenant_id: "${MS365_TENANT_ID}"
  client_id: "${MS365_CLIENT_ID}"
  client_secret: "${MS365_CLIENT_SECRET}"
  sender_email: "ai-assistant@mezzofy.com"       # Shared mailbox for AI-sent emails
  rate_limit_emails_per_hour: 30
  calendar_default_timezone: "Asia/Singapore"
  calendar_reminder_minutes: 15
```

### Microsoft Teams

```yaml
teams:
  enabled: true
  team_id: "${MS_TEAMS_TEAM_ID}"                 # Mezzofy main team ID
  bot_name: "MezzofyAI"
  channels:
    general: "19:general@thread.tacv2"            # General announcements
    sales: "19:sales@thread.tacv2"                # Sales notifications + reports
    finance: "19:finance@thread.tacv2"            # Financial reports
    marketing: "19:marketing@thread.tacv2"        # Marketing updates
    support: "19:support@thread.tacv2"            # Support ticket alerts
    management: "19:management@thread.tacv2"      # KPI dashboards, audit
```

### Task Queue (Celery + Redis)

```yaml
celery:
  broker_url: "redis://localhost:6379/0"
  result_backend: "redis://localhost:6379/1"
  timezone: "Asia/Singapore"
  worker_concurrency: 4
  task_time_limit: 600                            # 10 min hard limit
  task_soft_time_limit: 540                       # 9 min soft limit
```

### Webhooks

```yaml
webhooks:
  enabled: true
  secret_key: "${WEBHOOK_SECRET}"                 # HMAC verification for incoming webhooks

  sources:
    mezzofy:
      enabled: true
      events:
        - customer_signed_up
        - customer_churned
        - order_completed
        - support_ticket_created
        - feature_released

    teams:
      enabled: true                               # Receive @mentions from Teams

    custom:
      enabled: true                               # Accept custom webhooks
      allowed_sources: ["zapier", "github", "stripe"]
```

### Scheduler

```yaml
scheduler:
  enabled: true
  max_jobs_per_user: 10                           # Limit scheduled jobs per user
  min_interval_minutes: 15                        # Minimum interval between recurring jobs
  default_timezone: "Asia/Singapore"
```

### Tools

```yaml
tools:
  browser:
    enabled: true
    headless: true
    timeout_seconds: 30

  linkedin:
    enabled: true
    rate_limit_per_session: 50
    session_cookie: "${LINKEDIN_COOKIE}"

  database:
    enabled: true
    read_only: true

  knowledge_base:
    enabled: true
    directory: "knowledge"

  media_processing:
    enabled: true
    max_image_size_mb: 20
    max_video_size_mb: 100
    max_audio_size_mb: 50
    max_video_duration_seconds: 300      # 5 minutes
    image_max_dimension: 2048            # Resize before Vision API
    video_key_frame_interval: 5          # 1 frame per 5 seconds
    whisper_model: "base"                # tiny | base | small | medium | large
    supported_languages:
      - "en"
      - "zh"
      - "ms"
    vision_provider: "anthropic"         # Use Claude Vision API
```

### Agents

```yaml
agents:
  enabled: true
  auto_select: true

  available:
    - finance
    - sales
    - marketing
    - support
    - management
```

### Security

```yaml
security:
  jwt:
    secret: "${JWT_SECRET}"
    algorithm: "HS256"
    access_token_expiry_minutes: 60
    refresh_token_expiry_days: 7

  rate_limiting:
    requests_per_minute: 30
    email_sends_per_hour: 30
    linkedin_searches_per_hour: 20
    file_generations_per_hour: 50

  max_request_size_mb: 10
  max_upload_size_mb: 100              # Video uploads can be large
  allowed_upload_types:
    # Images
    - "image/jpeg"
    - "image/png"
    - "image/heic"
    - "image/webp"
    # Video
    - "video/mp4"
    - "video/quicktime"
    - "video/x-msvideo"
    # Audio
    - "audio/mpeg"
    - "audio/wav"
    - "audio/x-m4a"
    - "audio/ogg"
    # Documents
    - "application/pdf"
    - "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    - "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    - "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    - "text/csv"
    - "text/plain"
```

### File Storage

```yaml
storage:
  type: "local"                    # "local" (EBS) or "s3"
  local_path: "/data/artifacts"
  max_file_size_mb: 100

  # S3 config (for production scaling)
  s3:
    bucket: "mezzofy-ai-artifacts"
    region: "ap-southeast-1"
    access_key: "${AWS_ACCESS_KEY}"
    secret_key: "${AWS_SECRET_KEY}"
```

### Logging

```yaml
logging:
  level: "INFO"
  file: "logs/app.log"
  max_bytes: 10485760              # 10 MB
  backup_count: 10
  audit_retention_days: 90
```

---

## Roles Configuration (`config/roles.yaml`)

See [SECURITY.md](SECURITY.md) for the full roles.yaml with all departments, roles, and permissions.

Summary:

| Role | Department | Key Permissions |
|------|-----------|----------------|
| `finance_viewer` | Finance | finance_read |
| `finance_manager` | Finance | finance_read, finance_write, email_send, calendar_access |
| `sales_rep` | Sales | sales_read, sales_write, email_send, linkedin_access, calendar_access |
| `sales_manager` | Sales | All sales + sales_admin + scheduler_manage |
| `marketing_creator` | Marketing | marketing_read, marketing_write, email_send |
| `marketing_manager` | Marketing | All marketing + marketing_admin + scheduler_manage |
| `support_agent` | Support | support_read, support_write, email_send |
| `support_manager` | Support | All support + support_admin + scheduler_manage |
| `executive` | Management | Read across all departments + audit_read + scheduler_manage |
| `admin` | Management | All permissions |

---

## Environment Variables (`.env`)

```bash
# JWT
JWT_SECRET=your-256-bit-random-secret-here

# LLM APIs
ANTHROPIC_API_KEY=sk-ant-...
KIMI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql://mezzofy_ai:password@localhost:5432/mezzofy_ai

# Microsoft 365 (Azure AD App Registration)
MS365_TENANT_ID=your-azure-ad-tenant-id
MS365_CLIENT_ID=your-app-client-id
MS365_CLIENT_SECRET=your-app-client-secret

# Microsoft Teams
MS_TEAMS_TEAM_ID=your-teams-team-id

# LinkedIn (for Sales agent)
LINKEDIN_COOKIE=your-linkedin-session-cookie

# Webhooks
WEBHOOK_SECRET=your-webhook-hmac-secret

# Redis
REDIS_URL=redis://localhost:6379/0

# AWS (if using S3 storage)
AWS_ACCESS_KEY=AKIA...
AWS_SECRET_KEY=...
AWS_REGION=ap-southeast-1

# Logging
LOG_LEVEL=INFO
```

---

## Dependencies (`requirements.txt`)

### Core Server
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6
pydantic==2.5.3
python-dotenv==1.0.0
pyyaml==6.0.1
```

### Authentication
```
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

### LLM
```
anthropic==0.18.1
openai==1.12.0                     # Used for Kimi (OpenAI-compatible API)
tiktoken==0.6.0
```

### Microsoft 365 / Graph API
```
azure-identity==1.15.0
msgraph-sdk==1.2.0                 # Microsoft Graph SDK for Python
msal==1.26.0                       # Microsoft Authentication Library
```

### Task Queue & Scheduler
```
celery[redis]==5.3.6
redis==5.0.1
flower==2.0.1                      # Celery monitoring UI (optional)
```

### Database
```
asyncpg==0.29.0
sqlalchemy[asyncio]==2.0.25
alembic==1.13.1
```

### Document Generation
```
reportlab==4.0.7
weasyprint==61.0
python-pptx==0.6.23
python-docx==1.1.0
pandas==2.1.4
```

### Web / Scraping
```
playwright==1.40.0
beautifulsoup4==4.12.2
lxml==4.9.3
aiohttp==3.9.1
```

### Media Processing
```
Pillow==10.2.0
opencv-python-headless==4.9.0.80
moviepy==1.0.3
pydub==0.25.1
pytesseract==0.3.10
openai-whisper==20231117
```

### Email (legacy fallback — not primary)
```
aiosmtplib==2.0.2                  # Fallback if MS Graph unavailable
jinja2==3.1.3                      # Email HTML templates
```

### Utilities
```
python-magic==0.4.27
tqdm==4.66.1
httpx==0.26.0                      # Async HTTP client for webhooks
```

---

## System Requirements (AWS EC2)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| Instance | t3.large | t3.xlarge |
| vCPU | 2 | 4 |
| RAM | 8 GB | 16 GB |
| EBS | 50 GB gp3 | 100 GB gp3 |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| PostgreSQL | 15+ | 15+ (or RDS) |
| Redis | 7+ | 7+ |
| Python | 3.10+ | 3.11 |
| Nginx | Latest | Latest |
| FFmpeg | 6.0+ | 6.0+ (for audio/video processing) |
| Tesseract | 5.0+ | 5.0+ (for OCR) |
