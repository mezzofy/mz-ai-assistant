# INFRASTRUCTURE.md — AWS Deployment, Project Structure & React Native App

**AWS EC2/EBS setup, Celery/Redis task queue, systemd services, database migrations, and React Native mobile app structure.**

---

## AWS Architecture

```
┌──────────────────────────────────────────────────────────┐
│  AWS Region: ap-southeast-1 (Singapore)                   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐     │
│  │  EC2 Instance (t3.xlarge)                        │     │
│  │  Ubuntu 22.04 LTS                                │     │
│  │                                                   │     │
│  │  ┌──────────┐  ┌───────────────┐                │     │
│  │  │  Nginx   │→ │ FastAPI       │                │     │
│  │  │  (SSL)   │  │ (Uvicorn x4) │                │     │
│  │  └──────────┘  └───────────────┘                │     │
│  │                                                   │     │
│  │  ┌──────────┐  ┌───────────────┐                │     │
│  │  │PostgreSQL│  │ Redis 7       │                │     │
│  │  │  15      │  │ • Celery      │                │     │
│  │  │          │  │   broker      │                │     │
│  │  │          │  │ • Rate limit  │                │     │
│  │  │          │  │ • WS pub/sub  │                │     │
│  │  └──────────┘  └───────────────┘                │     │
│  │                                                   │     │
│  │  ┌──────────────────────────────────────────┐   │     │
│  │  │ Celery Workers × 4 │ Celery Beat         │   │     │
│  │  │ • Background tasks  │ • Cron scheduler    │   │     │
│  │  │ • LinkedIn scraping │ • Weekly reports    │   │     │
│  │  │ • Video processing  │ • Lead follow-ups   │   │     │
│  │  │ • Webhook handling  │ • Monthly summaries │   │     │
│  │  └──────────────────────────────────────────┘   │     │
│  │                                                   │     │
│  │  EBS Volume (100 GB gp3)                         │     │
│  │  └── /data (artifacts, knowledge)                │     │
│  └─────────────────────────────────────────────────┘     │
│                                                           │
│  ┌─────────────────────────────────────────────────┐     │
│  │  Security Group                                  │     │
│  │  • 443 (HTTPS) — public                         │     │
│  │  • 22 (SSH) — office IP only                    │     │
│  │  • 5432 (PostgreSQL) — localhost only            │     │
│  │  • 6379 (Redis) — localhost only                 │     │
│  └─────────────────────────────────────────────────┘     │
│                                                           │
│  External Connections:                                    │
│  • Microsoft Graph API (Outlook email/calendar, Teams)   │
│  • Anthropic API (Claude)                                │
│  • Moonshot API (Kimi)                                   │
│  • LinkedIn (web scraping)                               │
│  • Mezzofy product API (webhooks inbound)                │
└──────────────────────────────────────────────────────────┘
```

### Production Scaling (Future)

When load increases, consider:
- **RDS PostgreSQL** instead of local PostgreSQL (automated backups, scaling)
- **S3** for artifact storage instead of EBS
- **ElastiCache Redis** for rate limiting and caching
- **ALB + multiple EC2** for horizontal scaling
- **CloudWatch** for monitoring and alerts

---

## Server Folder Structure

```
mezzofy-ai-assistant/
│
├── /server
│   ├── /app                          # Core FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI entry + startup
│   │   ├── gateway.py               # Request processing
│   │   ├── router.py                # Intent → agent routing
│   │   │
│   │   ├── /api                     # REST endpoints
│   │   │   ├── __init__.py
│   │   │   ├── auth.py              # JWT login/refresh/logout
│   │   │   ├── chat.py              # Chat send/send-media/send-url/history/WS
│   │   │   ├── files.py             # File download/upload
│   │   │   └── admin.py             # User CRUD, roles
│   │   │
│   │   ├── /input                   # Multi-modal input processors
│   │   │   ├── __init__.py
│   │   │   ├── input_router.py      # Detect type → dispatch to handler
│   │   │   ├── text_handler.py      # Plain text passthrough
│   │   │   ├── image_handler.py     # Vision analysis, OCR (Tesseract, Claude Vision)
│   │   │   ├── video_handler.py     # Frame extraction, audio transcription
│   │   │   ├── camera_handler.py    # Live camera frames via WebSocket
│   │   │   ├── speech_handler.py    # Live STT via WebSocket (Whisper)
│   │   │   ├── audio_handler.py     # Audio file → transcription (Whisper)
│   │   │   ├── file_handler.py      # PDF/DOCX/PPTX/CSV text extraction
│   │   │   └── url_handler.py       # Playwright fetch + BeautifulSoup scrape
│   │   │
│   │   ├── /llm                     # LLM clients
│   │   │   ├── __init__.py
│   │   │   ├── llm_manager.py       # Claude + Kimi orchestrator
│   │   │   ├── anthropic_client.py
│   │   │   └── kimi_client.py
│   │   │
│   │   ├── /output                  # Output generators
│   │   │   ├── __init__.py
│   │   │   ├── pdf_output.py           # Financial statements, reports, playbooks
│   │   │   ├── pptx_output.py          # Sales pitch decks
│   │   │   ├── email_output.py         # Outlook email via MS Graph API
│   │   │   ├── calendar_output.py      # Outlook calendar events via MS Graph
│   │   │   ├── teams_output.py         # MS Teams channel messages via MS Graph
│   │   │   └── document_output.py      # DOCX, MD, CSV exports
│   │   │
│   │   └── /context                 # Session + artifact management
│   │       ├── __init__.py
│   │       ├── processor.py
│   │       ├── session_manager.py
│   │       └── artifact_manager.py
│   │
│   ├── /scheduler                   # Task queue + scheduled jobs
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery config + Redis broker
│   │   ├── tasks.py                 # Background task definitions
│   │   ├── beat_schedule.py         # Recurring cron job schedules
│   │   └── webhook_tasks.py         # Webhook-triggered async tasks
│   │
│   ├── /agents
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── finance_agent.py
│   │   ├── sales_agent.py
│   │   ├── marketing_agent.py
│   │   ├── support_agent.py
│   │   └── management_agent.py
│   │
│   ├── /skills
│   │   ├── __init__.py
│   │   ├── skill_loader.py
│   │   ├── skill_registry.py
│   │   └── /available
│   │       ├── linkedin_prospecting.yaml + .py
│   │       ├── financial_reporting.yaml + .py
│   │       ├── pitch_deck_generation.yaml + .py
│   │       ├── email_outreach.yaml + .py
│   │       ├── content_generation.yaml + .py
│   │       ├── web_research.yaml + .py
│   │       └── data_analysis.yaml + .py
│   │
│   ├── /tools
│   │   ├── __init__.py
│   │   ├── base_tool.py
│   │   ├── tool_executor.py
│   │   ├── /communication
│   │   │   ├── outlook_ops.py         # Outlook email + calendar via MS Graph API
│   │   │   ├── teams_ops.py           # MS Teams messages via MS Graph API
│   │   │   └── push_ops.py            # Mobile push notifications (FCM/APNs)
│   │   ├── /document
│   │   │   ├── pdf_ops.py
│   │   │   ├── pptx_ops.py
│   │   │   ├── docx_ops.py
│   │   │   └── csv_ops.py
│   │   ├── /media
│   │   │   ├── image_ops.py          # OCR, Vision analysis, resize
│   │   │   ├── video_ops.py          # Frame extraction, audio separation
│   │   │   ├── audio_ops.py          # Whisper STT, format conversion
│   │   │   └── speech_ops.py         # Live STT streaming
│   │   ├── /web
│   │   │   ├── browser_ops.py
│   │   │   ├── scraping_ops.py
│   │   │   └── linkedin_ops.py
│   │   ├── /database
│   │   │   ├── db_ops.py
│   │   │   └── crm_ops.py
│   │   └── /mezzofy
│   │       ├── data_ops.py
│   │       └── knowledge_ops.py
│   │
│   ├── /knowledge                   # Mezzofy internal data
│   │   ├── /product_data
│   │   │   ├── products.json
│   │   │   ├── pricing.yaml
│   │   │   └── features.yaml
│   │   ├── /templates
│   │   │   ├── /emails              # intro.html, followup.html, proposal.html
│   │   │   ├── /pdf                 # financial_statement.html, report.html
│   │   │   └── /pptx               # sales_deck.pptx, overview.pptx
│   │   ├── /brand
│   │   │   ├── brand_guidelines.md
│   │   │   ├── color_palette.yaml
│   │   │   └── /logos
│   │   └── /playbooks
│   │
│   ├── /config
│   │   ├── config.yaml
│   │   ├── config.example.yaml
│   │   ├── roles.yaml
│   │   └── .env
│   │
│   ├── /scripts
│   │   ├── setup.sh                 # First-time server setup
│   │   ├── deploy.sh                # Deployment script
│   │   ├── start.sh                 # Start server
│   │   ├── stop.sh                  # Stop server
│   │   ├── migrate.py               # Database migrations
│   │   └── seed.py                  # Seed initial users + roles
│   │
│   ├── /logs
│   │   ├── app.log
│   │   ├── error.log
│   │   └── access.log
│   │
│   ├── /data                        # Generated artifacts (EBS mounted)
│   │   ├── /documents
│   │   ├── /presentations
│   │   ├── /exports
│   │   └── /uploads
│   │
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
│
├── /mobile                           # React Native app
│   └── (see Mobile App section below)
│
└── README.md
```

---

## Setup Script (`scripts/setup.sh`)

First-time server setup on a fresh EC2 instance:

```bash
#!/bin/bash
echo "🚀 Setting up Mezzofy AI Assistant Server..."

# 1. System packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip \
    postgresql-15 redis-server nginx certbot python3-certbot-nginx \
    ffmpeg tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-msa

# 2. Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Playwright browser
playwright install chromium

# 4. PostgreSQL setup
sudo -u postgres createuser mezzofy_ai
sudo -u postgres createdb mezzofy_ai -O mezzofy_ai
sudo -u postgres psql -c "ALTER USER mezzofy_ai PASSWORD 'your_password';"

# 5. Run database migrations
python scripts/migrate.py

# 6. Seed initial admin user
python scripts/seed.py

# 7. Create data directories
mkdir -p data/{documents,presentations,exports,uploads}
mkdir -p logs

# 8. Copy config templates
cp config/config.example.yaml config/config.yaml
cp .env.example .env

# 9. Nginx + SSL
sudo cp nginx.conf /etc/nginx/sites-available/mezzofy-ai
sudo ln -s /etc/nginx/sites-available/mezzofy-ai /etc/nginx/sites-enabled/
sudo certbot --nginx -d api.mezzofy.com

echo "✅ Setup complete. Edit config.yaml and .env, then run ./scripts/start.sh"
```

---

## Database Migration (`scripts/migrate.py`)

Creates all required PostgreSQL tables:

```sql
-- Users
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name        TEXT NOT NULL,
    department  TEXT NOT NULL,
    role        TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),
    session_id  UUID NOT NULL,
    role        TEXT NOT NULL,          -- 'user' | 'assistant'
    content     TEXT NOT NULL,
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Sales Leads / CRM
CREATE TABLE sales_leads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name    TEXT NOT NULL,
    contact_name    TEXT,
    contact_email   TEXT,
    contact_phone   TEXT,
    industry        TEXT,
    location        TEXT,
    source          TEXT,              -- linkedin, website, referral, event
    status          TEXT DEFAULT 'new', -- new, contacted, qualified, proposal, closed_won, closed_lost
    assigned_to     UUID REFERENCES users(id),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_contacted  TIMESTAMPTZ,
    follow_up_date  TIMESTAMPTZ
);

-- Generated Artifacts
CREATE TABLE artifacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),
    session_id  UUID,
    type        TEXT NOT NULL,          -- pdf, pptx, docx, csv, image
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    size_bytes  BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Audit Log
CREATE TABLE audit_log (
    id          SERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id),  -- NULL for system/scheduler actions
    department  TEXT,
    action      TEXT NOT NULL,
    source      TEXT DEFAULT 'mobile',      -- mobile | webhook | scheduler | teams
    details     JSONB,
    ip_address  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- LLM Usage Tracking
CREATE TABLE llm_usage (
    id              SERIAL PRIMARY KEY,
    model           TEXT NOT NULL,
    department      TEXT,
    user_id         UUID REFERENCES users(id),
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Email Log
CREATE TABLE email_log (
    id          SERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id),
    to_address  TEXT NOT NULL,
    subject     TEXT,
    status      TEXT,                  -- sent, failed, bounced
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Scheduled Jobs (user-created recurring tasks)
CREATE TABLE scheduled_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),
    name        TEXT NOT NULL,
    agent       TEXT NOT NULL,          -- finance, sales, marketing, support, management
    message     TEXT NOT NULL,          -- Natural language task description
    schedule    TEXT NOT NULL,          -- Cron expression (e.g. "0 9 * * 1" = Monday 9AM)
    deliver_to  JSONB NOT NULL,        -- {"teams_channel": "sales", "email": ["ceo@mezzofy.com"]}
    is_active   BOOLEAN DEFAULT true,
    last_run    TIMESTAMPTZ,
    next_run    TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Webhook Events (incoming external events log)
CREATE TABLE webhook_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT NOT NULL,          -- mezzofy, teams, custom
    event_type  TEXT NOT NULL,          -- customer_signed_up, support_ticket_created, etc.
    payload     JSONB NOT NULL,
    status      TEXT DEFAULT 'received', -- received, processing, completed, failed
    task_id     TEXT,                   -- Celery task ID for tracking
    result      JSONB,                 -- Agent processing result
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_conversations_session ON conversations(session_id, created_at);
CREATE INDEX idx_conversations_user ON conversations(user_id, created_at DESC);
CREATE INDEX idx_leads_status ON sales_leads(status, assigned_to);
CREATE INDEX idx_leads_company ON sales_leads(company_name);
CREATE INDEX idx_leads_followup ON sales_leads(follow_up_date) WHERE follow_up_date IS NOT NULL;
CREATE INDEX idx_artifacts_user ON artifacts(user_id, created_at DESC);
CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_log(action, created_at DESC);
CREATE INDEX idx_scheduled_active ON scheduled_jobs(is_active, next_run);
CREATE INDEX idx_webhook_events_source ON webhook_events(source, created_at DESC);
CREATE INDEX idx_webhook_events_status ON webhook_events(status) WHERE status != 'completed';
```

---

## Deployment Script (`scripts/deploy.sh`)

```bash
#!/bin/bash
echo "🚀 Deploying Mezzofy AI Assistant..."

# Pull latest code
git pull origin main

# Activate venv
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run migrations
python scripts/migrate.py

# Restart all services
./scripts/stop.sh
./scripts/start.sh

# Verify
sleep 3
curl -s http://localhost:8000/health | python3 -m json.tool

echo "✅ Deployment complete"
```

---

## Nginx Configuration (`nginx.conf`)

```nginx
server {
    listen 443 ssl http2;
    server_name api.mezzofy.com;

    ssl_certificate /etc/letsencrypt/live/api.mezzofy.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.mezzofy.com/privkey.pem;

    client_max_body_size 100M;     # Support video uploads up to 100MB

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /chat/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
    }
}
```

---

## Systemd Services

All server processes are managed by systemd for automatic restart and startup on boot.

### FastAPI (`/etc/systemd/system/mezzofy-api.service`)

```ini
[Unit]
Description=Mezzofy AI Assistant API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mezzofy-ai-assistant/server
Environment=PATH=/home/ubuntu/mezzofy-ai-assistant/server/venv/bin
ExecStart=/home/ubuntu/mezzofy-ai-assistant/server/venv/bin/uvicorn \
    app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Celery Workers (`/etc/systemd/system/mezzofy-celery.service`)

```ini
[Unit]
Description=Mezzofy AI Celery Workers
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mezzofy-ai-assistant/server
Environment=PATH=/home/ubuntu/mezzofy-ai-assistant/server/venv/bin
ExecStart=/home/ubuntu/mezzofy-ai-assistant/server/venv/bin/celery \
    -A scheduler.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Celery Beat Scheduler (`/etc/systemd/system/mezzofy-beat.service`)

```ini
[Unit]
Description=Mezzofy AI Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mezzofy-ai-assistant/server
Environment=PATH=/home/ubuntu/mezzofy-ai-assistant/server/venv/bin
ExecStart=/home/ubuntu/mezzofy-ai-assistant/server/venv/bin/celery \
    -A scheduler.celery_app beat --loglevel=info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable All Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable mezzofy-api mezzofy-celery mezzofy-beat
sudo systemctl start mezzofy-api mezzofy-celery mezzofy-beat
```

---

## Start / Stop Scripts

### `scripts/start.sh`

```bash
#!/bin/bash
echo "🚀 Starting Mezzofy AI Assistant..."

# Check Redis
redis-cli ping > /dev/null 2>&1 || { echo "❌ Redis not running"; exit 1; }

# Check PostgreSQL
pg_isready -q || { echo "❌ PostgreSQL not running"; exit 1; }

# Start all services
sudo systemctl start mezzofy-api
sudo systemctl start mezzofy-celery
sudo systemctl start mezzofy-beat

sleep 2

# Verify
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✅ API running"
else
    echo "❌ API failed to start"
fi

echo "📊 Service status:"
sudo systemctl is-active mezzofy-api mezzofy-celery mezzofy-beat
```

### `scripts/stop.sh`

```bash
#!/bin/bash
echo "🛑 Stopping Mezzofy AI Assistant..."
sudo systemctl stop mezzofy-beat
sudo systemctl stop mezzofy-celery
sudo systemctl stop mezzofy-api
echo "✅ All services stopped"
```

---

## Docker Compose (Alternative Deployment)

For containerized deployment:

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: ./server
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://mezzofy_ai:password@postgres:5432/mezzofy_ai
      - REDIS_URL=redis://redis:6379/0
    env_file: ./server/config/.env
    depends_on:
      - postgres
      - redis
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    volumes:
      - artifacts:/data
      - ./server/knowledge:/app/knowledge:ro
    restart: always

  celery-worker:
    build: ./server
    environment:
      - DATABASE_URL=postgresql://mezzofy_ai:password@postgres:5432/mezzofy_ai
      - REDIS_URL=redis://redis:6379/0
    env_file: ./server/config/.env
    depends_on:
      - postgres
      - redis
    command: celery -A scheduler.celery_app worker --loglevel=info --concurrency=4
    volumes:
      - artifacts:/data
      - ./server/knowledge:/app/knowledge:ro
    restart: always

  celery-beat:
    build: ./server
    environment:
      - DATABASE_URL=postgresql://mezzofy_ai:password@postgres:5432/mezzofy_ai
      - REDIS_URL=redis://redis:6379/0
    env_file: ./server/config/.env
    depends_on:
      - postgres
      - redis
    command: celery -A scheduler.celery_app beat --loglevel=info
    restart: always

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: mezzofy_ai
      POSTGRES_PASSWORD: password
      POSTGRES_DB: mezzofy_ai
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: always

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass "${REDIS_PASSWORD:-}"
    ports:
      - "6379:6379"
    restart: always

  nginx:
    image: nginx:latest
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./server/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - api
    restart: always

volumes:
  pgdata:
  artifacts:
```

Start with Docker:
```bash
docker-compose up -d
docker-compose logs -f api celery-worker
```

---

## React Native Mobile App

```
/mobile
├── /src
│   ├── /screens
│   │   ├── LoginScreen.tsx              # Email + password login
│   │   ├── ChatScreen.tsx               # Main AI chat (multi-modal composer)
│   │   ├── ChatHistoryScreen.tsx        # Past conversations
│   │   ├── CameraScreen.tsx             # Live camera capture + analysis
│   │   ├── WebViewScreen.tsx            # In-app browser for URL input
│   │   ├── FilesScreen.tsx              # Generated files list + preview
│   │   └── SettingsScreen.tsx           # Profile, preferences, language
│   │
│   ├── /components
│   │   ├── /chat
│   │   │   ├── ChatBubble.tsx           # Message bubble (user + AI)
│   │   │   ├── MessageComposer.tsx      # Multi-modal input bar
│   │   │   ├── InputModeSelector.tsx    # Toggle: text/voice/camera/file/URL
│   │   │   └── StatusIndicator.tsx      # "Analyzing image..." progress
│   │   │
│   │   ├── /media
│   │   │   ├── ImagePicker.tsx          # Photo library + camera capture
│   │   │   ├── VideoPicker.tsx          # Video selection + recording
│   │   │   ├── AudioRecorder.tsx        # Record audio clip
│   │   │   ├── VoiceButton.tsx          # Push-to-talk live speech
│   │   │   ├── LiveCameraView.tsx       # Real-time camera feed + overlay
│   │   │   ├── FilePicker.tsx           # Document picker (PDF, DOCX, etc.)
│   │   │   ├── URLInput.tsx             # URL entry + preview
│   │   │   └── MediaPreview.tsx         # Thumbnail preview before send
│   │   │
│   │   ├── /output
│   │   │   ├── FilePreview.tsx          # PDF/PPTX inline preview
│   │   │   ├── ArtifactCard.tsx         # Downloadable file card
│   │   │   └── TranscriptBubble.tsx     # Live speech transcript display
│   │   │
│   │   └── /shared
│   │       ├── DepartmentBadge.tsx      # Department label
│   │       └── PermissionGate.tsx       # Hide UI based on user permissions
│   │
│   ├── /services
│   │   ├── api.ts                       # HTTP client (axios) — REST calls
│   │   ├── auth.ts                      # JWT storage + refresh logic
│   │   ├── websocket.ts                # WebSocket — streaming, live speech, camera
│   │   ├── media.ts                    # Image/video/audio compression + upload
│   │   ├── speech.ts                   # Live speech recording + streaming
│   │   ├── camera.ts                   # Camera frame capture + streaming
│   │   └── push.ts                      # Push notification handler
│   │
│   ├── /stores
│   │   ├── authStore.ts                 # Auth state
│   │   ├── chatStore.ts                 # Chat sessions + messages
│   │   ├── fileStore.ts                 # Generated files
│   │   └── inputModeStore.ts            # Current input mode state
│   │
│   ├── /utils
│   │   ├── constants.ts                 # API base URL, input limits
│   │   ├── formatters.ts               # Date, file size, duration formatting
│   │   ├── mediaUtils.ts               # Image resize, video compress, format check
│   │   └── permissions.ts              # Request camera/mic/storage permissions
│   │
│   └── App.tsx                          # Root navigation
│
├── package.json
├── app.json
├── tsconfig.json
├── ios/
├── android/
└── README.md
```

### Input Modes — Mobile UX

The chat screen has a **MessageComposer** bar at the bottom with an **InputModeSelector** that lets users switch between input modes:

```
┌─────────────────────────────────────────┐
│  Chat messages...                        │
│                                          │
│  [User]: 📷 <image of receipt>           │
│  [AI]: This receipt shows $142.50 from   │
│        ABC Restaurant. Want me to log    │
│        this as an expense?               │
│                                          │
│  [User]: 🎤 "Yes, add it to this month" │
│  [AI]: ✅ Expense logged: $142.50        │
│                                          │
├─────────────────────────────────────────┤
│  [💬] [📷] [🎥] [📹] [🎤] [🔊] [📎] [🌐] │
│  ┌─────────────────────────────┐ [Send] │
│  │ Type a message...           │        │
│  └─────────────────────────────┘        │
└─────────────────────────────────────────┘

Input mode icons:
💬 Text      — Default keyboard input
📷 Image     — Photo from gallery or camera snapshot
🎥 Video     — Video from gallery or record new
📹 Camera    — Live camera feed with real-time AI analysis
🎤 Speech    — Push-to-talk live speech-to-text
🔊 Audio     — Record or upload audio file
📎 File      — Pick PDF, DOCX, PPTX, CSV, XLSX
🌐 URL       — Enter URL to scrape and analyze
```

### Input Mode Details

#### 💬 Text (Chat)
- Standard keyboard text input
- Supports multi-line messages
- Default mode when app opens

#### 📷 Image
- **Camera snapshot:** Opens native camera, user takes photo
- **Gallery pick:** Select from photo library
- **Preview:** Shows thumbnail before sending with optional text message
- **Compression:** Images resized to max 2048px, JPEG quality 85% before upload
- Library: `react-native-image-picker`

#### 🎥 Video
- **Record:** Record video via native camera (max 5 minutes)
- **Gallery pick:** Select existing video
- **Preview:** Shows first frame + duration before sending
- **Compression:** Videos compressed to 720p before upload
- Library: `react-native-image-picker` (video mode)

#### 📹 Live Camera
- Opens full-screen camera view with AI overlay
- Streams frames to server via WebSocket (1 fps)
- Server returns real-time descriptions overlaid on camera feed
- User taps "Capture" to freeze frame and send for full analysis
- Library: `react-native-camera` or `expo-camera`

#### 🎤 Live Speech
- Push-to-talk button: hold to speak, release to send
- Audio streamed to server via WebSocket in real-time
- Partial transcripts shown as user speaks
- Final transcript becomes the chat message
- Supports: English, Chinese (Mandarin), Malay
- Library: `react-native-audio-recorder-player` + custom WS streaming

#### 🔊 Audio File
- Record a voice memo (press to record, press to stop)
- Or pick an existing audio file from device
- Uploaded as file, server transcribes via Whisper
- Transcript returned as the processed message
- Library: `react-native-audio-recorder-player`, `react-native-document-picker`

#### 📎 File Upload
- Opens document picker for:
  - PDF, DOCX, PPTX, CSV, XLSX, TXT
- Shows file name + size preview before sending
- Server extracts text content and processes
- Library: `react-native-document-picker`

#### 🌐 URL / Web View
- Text field to paste or type a URL
- Optional: In-app WebView preview before sending
- Sends URL to server for Playwright scraping + analysis
- Returns extracted content, screenshot, contact info
- Library: `react-native-webview`

### Device Permissions

The app requests permissions on first use of each input mode:

| Permission | iOS | Android | Required For |
|-----------|-----|---------|-------------|
| Camera | `NSCameraUsageDescription` | `CAMERA` | Image, Video, Live Camera |
| Microphone | `NSMicrophoneUsageDescription` | `RECORD_AUDIO` | Speech, Audio, Video |
| Photo Library | `NSPhotoLibraryUsageDescription` | `READ_EXTERNAL_STORAGE` | Image, Video |
| File Access | Automatic via picker | `READ_EXTERNAL_STORAGE` | File upload |

### Media Upload Service (`services/media.ts`)

Handles compression and multipart upload for all media types:

```typescript
class MediaService {
    async uploadImage(uri: string, message?: string): Promise<ChatResponse>
    async uploadVideo(uri: string, message?: string): Promise<ChatResponse>
    async uploadAudio(uri: string, message?: string): Promise<ChatResponse>
    async uploadFile(uri: string, message?: string): Promise<ChatResponse>
    async sendUrl(url: string, message?: string): Promise<ChatResponse>

    // Internal helpers
    private compressImage(uri: string): Promise<string>   // → max 2048px, JPEG 85%
    private compressVideo(uri: string): Promise<string>   // → 720p
    private buildMultipart(file: File, inputType: string, message?: string): FormData
}
```

### WebSocket Streaming Service (`services/websocket.ts`)

Handles live speech and camera streaming:

```typescript
class WebSocketService {
    connect(token: string): void
    disconnect(): void

    // Live speech
    startSpeech(): void
    sendAudioChunk(base64Audio: string): void
    stopSpeech(): void
    onTranscript(callback: (text: string, isFinal: boolean) => void): void

    // Live camera
    sendCameraFrame(base64Jpeg: string): void
    onCameraAnalysis(callback: (description: string) => void): void

    // General
    onStatus(callback: (message: string) => void): void
    onComplete(callback: (response: ChatResponse) => void): void
}
```

### Key Mobile Features

1. **Multi-Modal Chat** — Send text, images, video, audio, files, URLs, or use live camera/speech
2. **Live Speech** — Push-to-talk with real-time transcript feedback
3. **Live Camera** — Point camera at anything, get instant AI analysis
4. **Smart Composer** — One-tap input mode switching with previews before send
5. **File Preview** — View generated PDFs, download PPTX/CSV
6. **Push Notifications** — Alert when long-running tasks complete
7. **Offline Indicators** — Show connection status, queue text messages when offline

### Recommended Libraries

| Library | Purpose |
|---------|---------|
| `react-native-keychain` | Secure JWT storage |
| `react-native-image-picker` | Image/video capture + gallery |
| `react-native-camera` or `expo-camera` | Live camera feed |
| `react-native-audio-recorder-player` | Audio recording + playback |
| `react-native-document-picker` | File selection (PDF, DOCX, etc.) |
| `react-native-webview` | In-app URL preview |
| `react-native-pdf` | PDF viewing |
| `react-native-push-notification` | Push notifications |
| `react-native-share` | Share files to other apps |
| `react-native-permissions` | Camera/mic/storage permission requests |
| `react-native-image-resizer` | Image compression before upload |
| `react-native-video` | Video playback |
| `zustand` or `redux-toolkit` | State management |
| `react-navigation` | Screen navigation |
