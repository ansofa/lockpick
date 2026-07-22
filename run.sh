#!/bin/bash
# ─────────────────────────────────────────────────────────────
# run.sh — Jalankan Lockpick Server secara manual (tanpa systemd)
# Gunakan ini untuk development / debugging
# ─────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQ_FILE="$SCRIPT_DIR/requirements.txt"

echo "🔒 Menjalankan Lockpick Simulator..."
echo "   Dir : $SCRIPT_DIR/server"
echo "   URL : http://$(hostname -I | awk '{print $1}'):5000"
echo ""

# ── Cek group gpio (perlu untuk akses /dev/gpiomem) ─────────
if ! groups | grep -qw gpio; then
    echo "   ⚠️  User bukan anggota group 'gpio'."
    echo "      Jalankan: sudo usermod -aG gpio,audio \$USER && newgrp gpio"
    echo "      lalu re-login atau jalankan ulang script ini."
fi

# ── Buat virtualenv jika belum ada ───────────────────────────
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "[SETUP] Membuat virtual environment di $VENV_DIR ..."
    # --system-site-packages: venv bisa 'lihat' package sistem RPi (lgpio, RPi.GPIO, dll)
    python3 -m venv --system-site-packages "$VENV_DIR"
    echo "[SETUP] Menginstall dependensi..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -q -r "$REQ_FILE"
    # Simpan checksum requirements untuk deteksi perubahan
    md5sum "$REQ_FILE" > "$VENV_DIR/.req_checksum" 2>/dev/null || true
    echo "[SETUP] Selesai."
else
    # Auto-update venv jika requirements.txt berubah
    CURRENT_HASH=$(md5sum "$REQ_FILE" 2>/dev/null | awk '{print $1}')
    SAVED_HASH=$(cat "$VENV_DIR/.req_checksum" 2>/dev/null | awk '{print $1}')
    if [ "$CURRENT_HASH" != "$SAVED_HASH" ]; then
        echo "[SETUP] requirements.txt berubah — memperbarui dependensi..."
        "$VENV_DIR/bin/pip" install -q -r "$REQ_FILE"
        md5sum "$REQ_FILE" > "$VENV_DIR/.req_checksum" 2>/dev/null || true
        echo "[SETUP] Update selesai."
    fi
fi

# ── Aktifkan virtualenv ──────────────────────────────────────
source "$VENV_DIR/bin/activate"

# Verifikasi dependensi kritis
if python3 -c "import sounddevice" 2>/dev/null; then
    echo "   🎙️  sounddevice : OK"
else
    echo "   ⚠️  sounddevice : tidak tersedia — mic dalam simulation mode"
fi

if python3 -c "import lgpio" 2>/dev/null; then
    echo "   🔌 lgpio        : OK"
else
    echo "   ⚠️  lgpio        : tidak tersedia"
    echo "      Jalankan: sudo apt install liblgpio-dev"
fi

cd "$SCRIPT_DIR/server"

# Jalankan dalam mode development (mengaktifkan auto-reload)
export LOCKPICK_DEV=1
python3 server.py
