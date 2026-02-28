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
echo "[1/4] Pulling latest code..."
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "[2/4] Updating dependencies..."
pip install -r requirements.txt --quiet

# Run migrations (safe — only applies new tables/indexes)
echo "[3/4] Running database migrations..."
python scripts/migrate.py

# Restart all services
echo "[4/4] Restarting services..."
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
