#!/bin/bash
# ============================================================
# Mezzofy AI Assistant — Start All Services
# Usage: ./scripts/start.sh
# ============================================================

echo "🚀 Starting Mezzofy AI Assistant..."

# Verify Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis not running. Start with: sudo systemctl start redis-server"
    exit 1
fi

# Verify PostgreSQL is running
if ! pg_isready -q 2>/dev/null; then
    echo "❌ PostgreSQL not running. Start with: sudo systemctl start postgresql"
    exit 1
fi

# Start all services
sudo systemctl start mezzofy-api
sudo systemctl start mezzofy-celery
sudo systemctl start mezzofy-beat

sleep 2

# Verify API started
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "✅ API running (http://localhost:8000)"
else
    echo "❌ API failed to start — check: sudo journalctl -u mezzofy-api -n 50"
fi

echo ""
echo "📊 Service status:"
sudo systemctl is-active mezzofy-api mezzofy-celery mezzofy-beat
