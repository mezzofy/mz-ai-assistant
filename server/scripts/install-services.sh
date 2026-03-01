#!/bin/bash
# ============================================================
# Mezzofy AI Assistant — Install / Update Systemd Services
# Copies service files and enables auto-start on EC2 reboot.
# Safe to re-run on a live server (idempotent).
# Usage: chmod +x scripts/install-services.sh && ./scripts/install-services.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔧 Installing Mezzofy systemd service files..."
echo "================================================"
echo "   Source: ${SERVER_DIR}/config/"
echo "   Target: /etc/systemd/system/"
echo ""

# Copy service files
echo "[1/3] Copying service files..."
sudo cp "${SERVER_DIR}/config/mezzofy-api.service"    /etc/systemd/system/mezzofy-api.service
sudo cp "${SERVER_DIR}/config/mezzofy-celery.service" /etc/systemd/system/mezzofy-celery.service
sudo cp "${SERVER_DIR}/config/mezzofy-beat.service"   /etc/systemd/system/mezzofy-beat.service
echo "      ✅ mezzofy-api.service"
echo "      ✅ mezzofy-celery.service"
echo "      ✅ mezzofy-beat.service"

# Reload systemd so it picks up the new/updated unit files
echo "[2/3] Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "      ✅ daemon reloaded"

# Enable all three services so they start automatically on reboot
echo "[3/3] Enabling services for auto-start on reboot..."
sudo systemctl enable mezzofy-api mezzofy-celery mezzofy-beat
echo "      ✅ all services enabled"

# Print current status of all 3 services
echo ""
echo "================================================"
echo "📊 Service status:"
echo ""
for svc in mezzofy-api mezzofy-celery mezzofy-beat; do
    STATUS=$(sudo systemctl is-active "$svc" 2>/dev/null || true)
    ENABLED=$(sudo systemctl is-enabled "$svc" 2>/dev/null || true)
    echo "   ${svc}: active=${STATUS}  enabled=${ENABLED}"
done

echo ""
echo "✅ Service installation complete."
echo ""
echo "📌 Next steps (if services are not yet running):"
echo "   Start:   ./scripts/start.sh"
echo "   Logs:    sudo journalctl -u mezzofy-api -f"
