#!/bin/bash
# Script untuk mengonfigurasi Raspberry Pi agar membuka Chromium Kiosk Mode saat boot

echo "Mengonfigurasi Chromium Kiosk Autostart..."

# Membuat direktori autostart jika belum ada
mkdir -p ~/.config/autostart

# Membuat file desktop entry untuk autostart Chromium
cat <<EOF > ~/.config/autostart/lockpick-kiosk.desktop
[Desktop Entry]
Type=Application
Name=Lockpick Kiosk
Exec=chromium-browser --noerrdialogs --disable-infobars --kiosk http://127.0.0.1:5000/kiosk
X-GNOME-Autostart-enabled=true
EOF

echo "Selesai! Raspberry Pi sekarang akan otomatis membuka layar Kiosk (Full Screen) saat dinyalakan."
echo "Catatan: Pastikan server Lockpick juga sudah berjalan secara otomatis (misal menggunakan systemd) agar browser dapat memuat halaman."
