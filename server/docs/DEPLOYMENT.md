# Mezzofy AI Assistant — Deployment Guide
**Version:** 1.0
**Target:** AWS EC2 — Ubuntu 22.04 LTS
**Estimated setup time:** 30–45 minutes

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| EC2 instance | t3.medium or larger | 2 vCPU, 4 GB RAM minimum |
| OS | Ubuntu 22.04 LTS | x86_64 |
| Disk | 30 GB+ EBS | `/data/artifacts` needs space for uploads |
| Security group | Inbound 80, 443, 22 | 80/443 for HTTPS; 22 for SSH |
| Elastic IP | Recommended | Stable IP for DNS |
| Domain | Required for SSL | e.g. `api.mezzofy.com` |

**API keys required before setup:**

- Anthropic API key (`sk-ant-...`)
- Kimi / Moonshot API key (`sk-...`)
- Microsoft 365: Tenant ID, Client ID, Client Secret
- Microsoft Teams: Team ID, Sender User ID

---

## Step 1 — Clone the Repository

```bash
ssh ubuntu@<your-ec2-ip>
git clone https://github.com/mezzofy/mz-ai-assistant.git
cd mz-ai-assistant/server
```

---

## Step 2 — Run the Setup Script

The setup script installs all system dependencies and configures services in a single pass.

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

**What setup.sh does (10 steps):**

1. Installs system packages: Python 3.11, PostgreSQL 15, Redis, Nginx, Certbot, FFmpeg, Tesseract OCR (EN + zh-CN + zh-TW + Malay)
2. Creates a Python 3.11 virtual environment and installs all pip dependencies
3. Installs Playwright Chromium (for URL scraping)
4. Creates the `mezzofy_ai` PostgreSQL user and database
5. Starts and enables Redis
6. Runs `scripts/migrate.py` — creates all 9 database tables
7. Runs `scripts/seed.py` — creates initial admin account
8. Creates `/data/artifacts/` directories
9. Copies `config/config.example.yaml` → `config/config.yaml` and creates `config/.env` with placeholder values
10. Installs Nginx config and three systemd services: `mezzofy-api`, `mezzofy-celery`, `mezzofy-beat`

---

## Step 3 — Configure Environment Variables

Edit `config/.env` — this file is sourced by all three systemd services:

```bash
nano config/.env
```

Required values (replace all `CHANGE_ME` placeholders):

```dotenv
# Security — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=<256-bit-random-hex>

# LLM providers
ANTHROPIC_API_KEY=sk-ant-<your-key>
KIMI_API_KEY=sk-<your-moonshot-key>

# PostgreSQL (created by setup.sh — change the password)
DATABASE_URL=postgresql+asyncpg://mezzofy_ai:<db-password>@localhost:5432/mezzofy_ai

# Redis
REDIS_URL=redis://localhost:6379/0

# Microsoft 365
MS365_TENANT_ID=<azure-tenant-id>
MS365_CLIENT_ID=<azure-app-client-id>
MS365_CLIENT_SECRET=<azure-app-secret>

# Microsoft Teams (Azure AD object ID of the bot sender user)
MS_TEAMS_TEAM_ID=<teams-team-id>
MS_TEAMS_SENDER_USER_ID=<azure-ad-user-object-id>

# LinkedIn (session cookie for scraping)
LINKEDIN_COOKIE=<li_at-cookie-value>

# Webhooks (generate with: python3 -c "import secrets; print(secrets.token_hex(32))")
WEBHOOK_SECRET=<random-secret>

# Logging
LOG_LEVEL=INFO
```

> **Security:** `config/.env` must never be committed to git. It is already in `.gitignore`.

---

## Step 4 — Update PostgreSQL Password

The setup script creates the `mezzofy_ai` database user with a placeholder password. Update it:

```bash
sudo -u postgres psql
ALTER USER mezzofy_ai WITH PASSWORD '<your-secure-password>';
\q
```

Then update `DATABASE_URL` in `config/.env` to match.

---

## Step 5 — Configure the Application

Edit `config/config.yaml` to match your environment. Key sections to review:

```bash
nano config/config.yaml
```

Important settings:

```yaml
server:
  workers: 4          # Match EC2 vCPU count × 2

cors:
  allowed_origins:
    - "https://your-mobile-app-domain.com"
    - "http://localhost:8081"  # Keep for development

storage:
  type: "local"                     # Use "s3" for production scaling
  local_path: "/data/artifacts"

celery:
  worker_concurrency: 4             # Match EC2 vCPU count
```

---

## Step 6 — Configure SSL with Let's Encrypt

Nginx is already configured as an SSL termination proxy. Obtain a certificate:

```bash
# Point your domain's A record to the EC2 Elastic IP first
sudo certbot --nginx -d api.mezzofy.com
```

Certbot auto-renews via a systemd timer. Verify:

```bash
sudo certbot renew --dry-run
```

---

## Step 7 — Start the Server

```bash
./scripts/start.sh
```

This script:
1. Verifies Redis and PostgreSQL are running
2. Starts `mezzofy-api` (FastAPI + Uvicorn, 4 workers, port 8000)
3. Starts `mezzofy-celery` (Celery workers, 4 concurrency)
4. Starts `mezzofy-beat` (Celery Beat scheduler)
5. Checks `http://localhost:8000/health` and reports status

**Verify all services are running:**

```bash
sudo systemctl status mezzofy-api mezzofy-celery mezzofy-beat
```

**Test the API:**

```bash
curl https://api.mezzofy.com/health
# Expected: {"status": "ok", "database": "connected", "redis": "connected"}
```

---

## Step 8 — Verify the Admin Account

The seed script creates a default admin. Log in and change the password immediately:

```bash
# Default admin credentials (from scripts/seed.py)
# Email: admin@mezzofy.com
# Password: ChangeMe123!  ← Change this immediately

curl -X POST https://api.mezzofy.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@mezzofy.com","password":"ChangeMe123!"}'
```

Use the returned `access_token` to create real user accounts via `POST /admin/users`.

---

## Service Management

### Start all services
```bash
./scripts/start.sh
```

### Stop all services
```bash
./scripts/stop.sh
```

### Restart after config change
```bash
sudo systemctl restart mezzofy-api
# Celery workers require a full restart to pick up code changes:
sudo systemctl restart mezzofy-celery mezzofy-beat
```

### View logs
```bash
# API logs (real-time)
sudo journalctl -u mezzofy-api -f

# Celery logs
sudo journalctl -u mezzofy-celery -f

# Application log file
tail -f logs/app.log

# Nginx access log
sudo tail -f /var/log/nginx/access.log
```

---

## Database Operations

### Run migrations (first time or after schema update)
```bash
source venv/bin/activate
python scripts/migrate.py
```

### Seed initial users
```bash
source venv/bin/activate
python scripts/seed.py
```

### Connect to the database
```bash
psql -U mezzofy_ai -d mezzofy_ai -h localhost
```

### Backup the database
```bash
pg_dump -U mezzofy_ai mezzofy_ai > backup_$(date +%Y%m%d).sql
```

---

## Environment Variable Checklist

Before going live, verify every variable is set:

| Variable | Required | Description |
|----------|:--------:|-------------|
| `JWT_SECRET` | ✅ | 256-bit random key for JWT signing |
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `KIMI_API_KEY` | ✅ | Moonshot / Kimi API key |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `MS365_TENANT_ID` | ✅ | Azure AD tenant |
| `MS365_CLIENT_ID` | ✅ | Azure app registration |
| `MS365_CLIENT_SECRET` | ✅ | Azure app secret |
| `MS_TEAMS_TEAM_ID` | ✅ | Teams team ID |
| `MS_TEAMS_SENDER_USER_ID` | ✅ | Azure AD object ID of Teams bot sender |
| `LINKEDIN_COOKIE` | ✅ | LinkedIn `li_at` session cookie |
| `WEBHOOK_SECRET` | ✅ | HMAC secret for webhook verification |
| `LOG_LEVEL` | Optional | Default: `INFO` |

---

## Architecture Overview

```
Internet → Nginx (443) → Uvicorn (8000) → FastAPI app
                                            ├── /auth/*      JWT authentication
                                            ├── /chat/*      AI assistant
                                            ├── /files/*     Artifact management
                                            ├── /admin/*     User management
                                            ├── /webhooks/*  Inbound events
                                            └── /scheduler/* Cron job management

FastAPI → Redis → Celery workers (async processing)
                → Celery Beat (scheduled jobs)

FastAPI → PostgreSQL (9 tables)
FastAPI → Anthropic API (Claude) / Moonshot API (Kimi)
FastAPI → Microsoft Graph API (Outlook + Teams)
```

**Ports:**
- `443` — HTTPS (Nginx, public)
- `8000` — FastAPI (localhost only, Nginx proxies to this)
- `5432` — PostgreSQL (localhost only)
- `6379` — Redis (localhost only)

---

## Scaling Considerations

| Component | Current | Scale To |
|-----------|---------|----------|
| FastAPI workers | 4 | Add vCPUs; or add load balancer + multiple EC2s |
| Celery workers | 4 | Increase `worker_concurrency`; or add Celery worker nodes |
| PostgreSQL | Local | Migrate to RDS for managed backups + replicas |
| Redis | Local | Migrate to ElastiCache for HA |
| Artifacts | Local EBS | Change `storage.type = "s3"` in config.yaml |

---

## Troubleshooting

### API fails to start
```bash
sudo journalctl -u mezzofy-api -n 50
# Common: missing config/config.yaml · wrong DATABASE_URL · port 8000 already in use
```

### Database connection errors
```bash
# Test connection manually:
source venv/bin/activate
python scripts/test.py
```

### Celery tasks not running
```bash
# Check worker status:
sudo journalctl -u mezzofy-celery -n 50
# Common: wrong REDIS_URL · tasks module import errors
```

### Rate limit errors (429)
```bash
# Flush Redis rate limit keys (use with caution):
redis-cli FLUSHDB
```

### SSL certificate issues
```bash
sudo certbot renew --force-renewal
sudo systemctl restart nginx
```

---

*Generated: 2026-02-28 · mz-ai-assistant v1.0*
