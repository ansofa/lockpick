#!/bin/bash
# ─────────────────────────────────────────────────────────────
# run.sh — Jalankan Lockpick Server secara manual (tanpa systemd)
# Gunakan ini untuk development / debugging
# ─────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔒 Menjalankan Lockpick Simulator..."
echo "   Dir : $SCRIPT_DIR/server"
echo "   URL : http://$(hostname -I | awk '{print $1}'):5000"
echo ""

cd "$SCRIPT_DIR/server"

# Jalankan dalam mode development (mengaktifkan auto-reload)
export LOCKPICK_DEV=1
python3 server.py
