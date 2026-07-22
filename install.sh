#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Lockpick Simulator — Installer Script
#  Terinspirasi dari RotorHazard install.sh
#
#  Usage:
#    wget https://raw.githubusercontent.com/[USERNAME]/lockpick/main/install.sh
#    bash install.sh
#
#  Atau one-liner:
#    bash <(wget -qO- https://raw.githubusercontent.com/[USERNAME]/lockpick/main/install.sh)
# ═══════════════════════════════════════════════════════════════════

set -e

# ─── Warna terminal ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; exit 1; }

# ─── Konfigurasi ──────────────────────────────────────────────────
REPO_URL="https://github.com/ansofa/lockpick"   # ← Ganti username GitHub Anda
INSTALL_DIR="/home/pi/lockpick"
VENV_DIR="$INSTALL_DIR/.venv"
SERVICE_NAME="lockpick"
PYTHON="python3"

# ─── Banner ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║     🔒  LOCKPICK SIMULATOR INSTALLER     ║${RESET}"
echo -e "${BOLD}${CYAN}║           Fase 1 — Standalone Unit        ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ─── Cek OS ───────────────────────────────────────────────────────
if ! grep -q "Raspberry Pi\|raspbian\|debian" /etc/os-release 2>/dev/null; then
    warn "Script ini dioptimalkan untuk Raspberry Pi OS."
    warn "Lanjutkan dengan risiko Anda sendiri."
    read -p "Tetap lanjutkan? (y/N): " confirm
    [[ "$confirm" == "y" || "$confirm" == "Y" ]] || error "Instalasi dibatalkan."
fi

# ─── Update sistem ────────────────────────────────────────────────
info "Memperbarui daftar paket..."
sudo apt-get update -qq

info "Menginstall dependensi sistem..."
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv \
    python3-dev \
    liblgpio-dev \
    libportaudio2 portaudio19-dev \
    git \
    chromium-browser \
    xdotool \
    unclutter

success "Dependensi sistem terinstall."

# ─── Tambah user ke group gpio (agar gpiozero/lgpio bisa akses /dev/gpiomem) ──
info "Menambahkan user ke group gpio dan dialout..."
sudo usermod -aG gpio,dialout,audio pi
success "User pi ditambahkan ke group gpio, dialout, audio."


# ─── Clone atau update repo ───────────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    info "Direktori $INSTALL_DIR sudah ada — memperbarui..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    info "Mengclone repository ke $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

success "Kode project tersedia di $INSTALL_DIR"

# ─── Buat virtualenv & install Python dependencies ────────────
info "Membuat/memperbarui virtual environment di $VENV_DIR ..."
$PYTHON -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q

info "Menginstall Python dependencies ke virtualenv..."
"$VENV_DIR/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"
success "Python dependencies terinstall di virtualenv."

# ─── Setup systemd service ────────────────────────────────────────
info "Menginstall systemd service..."
sudo cp "$INSTALL_DIR/lockpick.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# Cek status
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    success "Service '$SERVICE_NAME' berjalan!"
else
    warn "Service mungkin gagal start. Cek dengan: sudo journalctl -u $SERVICE_NAME -n 30"
fi

# ─── Setup Chromium Kiosk (LCD Touchscreen) ───────────────────────
info "Mengkonfigurasi Chromium kiosk mode..."

AUTOSTART_DIR="/home/pi/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/lockpick-kiosk.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Lockpick Kiosk
Exec=bash -c "sleep 8 && chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run --disable-session-crashed-bubble --disable-component-update http://localhost:5000"
EOF

# Sembunyikan cursor di layar kiosk
cat > "$AUTOSTART_DIR/unclutter.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=Unclutter (hide cursor)
Exec=unclutter -idle 0.5 -root
EOF

success "Chromium kiosk dikonfigurasi — akan aktif setelah reboot."

# ─── Dapatkan IP RPi ──────────────────────────────────────────────
DEVICE_IP=$(hostname -I | awk '{print $1}')

# ─── Selesai ──────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║      ✅  INSTALASI BERHASIL!              ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  📡 Dashboard  : ${BOLD}http://${DEVICE_IP}:5000${RESET}"
echo -e "  📋 API Status : ${BOLD}http://${DEVICE_IP}:5000/api/v1/status${RESET}"
echo ""
echo -e "  Perintah berguna:"
echo -e "  • Cek service  : ${CYAN}sudo systemctl status $SERVICE_NAME${RESET}"
echo -e "  • Lihat log    : ${CYAN}sudo journalctl -u $SERVICE_NAME -f${RESET}"
echo -e "  • Restart      : ${CYAN}sudo systemctl restart $SERVICE_NAME${RESET}"
echo -e "  • Jalankan dev : ${CYAN}bash $INSTALL_DIR/run.sh${RESET}"
echo ""
echo -e "  ${YELLOW}Reboot direkomendasikan agar kiosk mode aktif:${RESET}"
echo -e "  ${CYAN}sudo reboot${RESET}"
echo ""
