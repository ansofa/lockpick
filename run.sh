#!/bin/bash
# ─────────────────────────────────────────────────────────────
# run.sh — Jalankan Lockpick Server secara manual (tanpa systemd)
# Gunakan ini untuk development / debugging
# ─────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "🔒 Menjalankan Lockpick Simulator..."
echo "   Dir : $SCRIPT_DIR/server"
echo "   URL : http://$(hostname -I | awk '{print $1}'):5000"
echo ""

# ── Buat virtualenv jika belum ada ──────────────────────────
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "[SETUP] Membuat virtual environment di $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
    echo "[SETUP] Menginstall dependensi..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
    echo "[SETUP] Selesai."
fi

# ── Aktifkan virtualenv ──────────────────────────────────────
source "$VENV_DIR/bin/activate"

# Verifikasi sounddevice tersedia (opsional, untuk debug)
if python3 -c "import sounddevice" 2>/dev/null; then
    echo "   🎙️  sounddevice: OK"
else
    echo "   ⚠️  sounddevice tidak tersedia — mode simulasi mic aktif"
fi

cd "$SCRIPT_DIR/server"

# Jalankan dalam mode development (mengaktifkan auto-reload)
export LOCKPICK_DEV=1
python3 server.py
