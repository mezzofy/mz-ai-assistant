#!/bin/bash
# ============================================================
# Mezzofy AI Assistant — First-Time Server Setup
# Run once on a fresh EC2 Ubuntu 22.04 instance
# Usage: chmod +x scripts/setup.sh && ./scripts/setup.sh
# ============================================================

set -e  # Exit on any error

echo "🚀 Setting up Mezzofy AI Assistant Server..."
echo "============================================="

# ── 1. System packages ────────────────────────────────────
echo ""
echo "📦 [1/10] Installing system packages..."
sudo apt update && sudo apt upgrade -y

# Add PostgreSQL 15 official APT repository (not in Ubuntu 22.04 default repos)
echo "   → Adding PostgreSQL PGDG repository..."
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    | sudo gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
    | sudo tee /etc/apt/sources.list.d/pgdg.list
sudo apt update

sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql-15 \
    postgresql-client-15 \
    redis-server \
    nginx \
    certbot \
    python3-certbot-nginx \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-msa \
    libreoffice-headless \
    libmagic1 \
    build-essential \
    libpq-dev \
    curl \
    git

echo "✅ System packages installed"

# ── 2. Python virtual environment ─────────────────────────
echo ""
echo "🐍 [2/10] Creating Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
echo "✅ Python environment ready"

# ── 3. Playwright browser ─────────────────────────────────
echo ""
echo "🌐 [3/10] Installing Playwright Chromium browser..."
playwright install chromium
playwright install-deps chromium
echo "✅ Playwright ready"

# ── 4. PostgreSQL setup ───────────────────────────────────
echo ""
echo "🗄️  [4/10] Configuring PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database user and database
sudo -u postgres psql << 'PSQL'
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'mezzofy_ai') THEN
        CREATE USER mezzofy_ai WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';
    END IF;
END $$;

SELECT 'CREATE DATABASE mezzofy_ai OWNER mezzofy_ai'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mezzofy_ai')\gexec

GRANT ALL PRIVILEGES ON DATABASE mezzofy_ai TO mezzofy_ai;
PSQL

echo "✅ PostgreSQL configured"

# ── 5. Redis setup ────────────────────────────────────────
echo ""
echo "📮 [5/10] Configuring Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server
# Test Redis
redis-cli ping > /dev/null 2>&1 && echo "✅ Redis running" || echo "⚠️  Redis may need manual configuration"

# ── 6. Database migrations ────────────────────────────────
echo ""
echo "📊 [6/10] Running database migrations..."
python scripts/migrate.py
echo "✅ Database schema created"

# ── 7. Seed initial users ─────────────────────────────────
echo ""
echo "👤 [7/10] Seeding initial admin user..."
python scripts/seed.py
echo "✅ Initial users seeded"

# ── 8. Create data directories ────────────────────────────
echo ""
echo "📁 [8/10] Creating data and log directories..."
sudo mkdir -p /data/artifacts/{documents,presentations,exports,uploads}
sudo chown -R ubuntu:ubuntu /data
mkdir -p logs
echo "✅ Directories created"

# ── 9. Config files ───────────────────────────────────────
echo ""
echo "⚙️  [9/10] Copying config templates..."
if [ ! -f config/config.yaml ]; then
    cp config/config.example.yaml config/config.yaml
    echo "   → config/config.yaml created (EDIT THIS FILE)"
fi
if [ ! -f config/.env ]; then
    cat > config/.env << 'EOF'
# Edit all values below before starting the server
JWT_SECRET=CHANGE_ME_GENERATE_256_BIT_RANDOM_KEY
ANTHROPIC_API_KEY=sk-ant-CHANGE_ME
KIMI_API_KEY=sk-CHANGE_ME
DATABASE_URL=postgresql+asyncpg://mezzofy_ai:CHANGE_ME@localhost:5432/mezzofy_ai
REDIS_URL=redis://localhost:6379/0
MS365_TENANT_ID=CHANGE_ME
MS365_CLIENT_ID=CHANGE_ME
MS365_CLIENT_SECRET=CHANGE_ME
MS_TEAMS_TEAM_ID=CHANGE_ME
LINKEDIN_COOKIE=CHANGE_ME
WEBHOOK_SECRET=CHANGE_ME_GENERATE_SECRET
LOG_LEVEL=INFO
EOF
    echo "   → config/.env created (EDIT THIS FILE)"
fi

# ── 10. Nginx + systemd services ──────────────────────────
echo ""
echo "🔧 [10/10] Configuring Nginx and systemd services..."
sudo cp config/nginx.conf /etc/nginx/sites-available/mezzofy-ai
sudo ln -sf /etc/nginx/sites-available/mezzofy-ai /etc/nginx/sites-enabled/mezzofy-ai
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# Install systemd services
INSTALL_DIR=$(pwd)

sudo bash -c "cat > /etc/systemd/system/mezzofy-api.service << 'SERVICE'
[Unit]
Description=Mezzofy AI Assistant API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/config/.env
Environment=PATH=${INSTALL_DIR}/venv/bin
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE"

sudo bash -c "cat > /etc/systemd/system/mezzofy-celery.service << 'SERVICE'
[Unit]
Description=Mezzofy AI Celery Workers
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/config/.env
Environment=PATH=${INSTALL_DIR}/venv/bin
ExecStart=${INSTALL_DIR}/venv/bin/celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE"

sudo bash -c "cat > /etc/systemd/system/mezzofy-beat.service << 'SERVICE'
[Unit]
Description=Mezzofy AI Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/config/.env
Environment=PATH=${INSTALL_DIR}/venv/bin
ExecStart=${INSTALL_DIR}/venv/bin/celery -A app.tasks.celery_app beat --loglevel=info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE"

sudo systemctl daemon-reload
sudo systemctl enable mezzofy-api mezzofy-celery mezzofy-beat
echo "✅ systemd services installed and enabled"

# ── Done ──────────────────────────────────────────────────
echo ""
echo "============================================="
echo "✅ Setup complete!"
echo ""
echo "⚠️  REQUIRED: Edit these files before starting:"
echo "   1. config/config.yaml  — server configuration"
echo "   2. config/.env         — API keys and secrets"
echo ""
echo "📌 Next steps:"
echo "   1. Edit config/config.yaml and config/.env"
echo "   2. Run SSL: sudo certbot --nginx -d api.mezzofy.com"
echo "   3. Start server: ./scripts/start.sh"
echo ""
