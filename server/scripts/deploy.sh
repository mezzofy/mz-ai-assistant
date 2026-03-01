#!/bin/bash
# ============================================================
# Mezzofy AI Assistant — Deployment Script
# Pulls latest code and restarts all services
# Usage: ./scripts/deploy.sh
# ============================================================

set -e

echo "🚀 Deploying Mezzofy AI Assistant..."
echo "====================================="

# Pull latest code
echo "[1/5] Pulling latest code..."
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "[2/5] Updating dependencies..."
pip install -r requirements.txt --quiet

# Run migrations (safe — only applies new tables/indexes)
echo "[3/5] Running database migrations..."
python scripts/migrate.py

# Re-install service files if they changed
echo "[4/5] Syncing service files..."
sudo cp config/mezzofy-*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Restart all services
echo "[5/5] Restarting services..."
./scripts/stop.sh
sleep 2
./scripts/start.sh

# Verify
sleep 3
echo ""
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✅ Deployment successful — API is healthy"
else
    echo "❌ API health check failed — check logs: sudo journalctl -u mezzofy-api -n 50"
    exit 1
fi
