#!/bin/bash
# ============================================================
# Mezzofy AI Assistant — Stop All Services
# Usage: ./scripts/stop.sh
# ============================================================

echo "🛑 Stopping Mezzofy AI Assistant..."
sudo systemctl stop mezzofy-beat  2>/dev/null || true
sudo systemctl stop mezzofy-celery 2>/dev/null || true
sudo systemctl stop mezzofy-api   2>/dev/null || true
echo "✅ All services stopped"
