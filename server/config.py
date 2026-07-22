"""
Lockpick Simulator — Konfigurasi Unit
Semua nilai bisa di-override via environment variable.
"""
import os

# Identitas unit (tampil di header dashboard)
UNIT_NAME = os.environ.get('LOCKPICK_UNIT_NAME', 'Lockpick Unit 1')
UNIT_ID   = os.environ.get('LOCKPICK_UNIT_ID',   'lockpick-unit-01')

# GPIO
# NPN NO proximity switch, pull_up=True
# Metal detected (deadbolt keluar) → pin LOW → is_pressed = True  → LOCKED
# Metal away   (deadbolt masuk)    → pin HIGH → is_pressed = False → UNLOCKED
GPIO_PIN  = int(os.environ.get('LOCKPICK_GPIO_PIN', '24'))

# Web server
HOST = os.environ.get('LOCKPICK_HOST', '0.0.0.0')
PORT = int(os.environ.get('LOCKPICK_PORT', '5000'))

# Database (file path SQLite)
DATABASE_PATH = os.environ.get(
    'LOCKPICK_DB',
    os.path.join(os.path.dirname(__file__), '..', 'lockpick.db')
)

# Versi aplikasi
VERSION = '1.1.0'

# Admin Password
ADMIN_PASSWORD = os.environ.get('LOCKPICK_ADMIN_PASS', 'admin123')

# ─── Mic / Microphone Config ──────────────────────────────────────
# Index device audio. None = auto-detect default input device.
MIC_DEVICE_INDEX      = None if os.environ.get('LOCKPICK_MIC_DEVICE') is None \
                        else int(os.environ.get('LOCKPICK_MIC_DEVICE'))

# Threshold desibel relatif di atas baseline yang dianggap pelanggaran (dB)
MIC_THRESHOLD_DB      = float(os.environ.get('LOCKPICK_MIC_THRESHOLD', '15.0'))

# Durasi kalibrasi baseline noise ruangan (detik)
MIC_CALIBRATION_SEC   = float(os.environ.get('LOCKPICK_MIC_CALIB_SEC', '2.0'))

# ─── Challenge Default Config ────────────────────────────────────
# Batas waktu default per challenge (detik). 0 = unlimited.
CHALLENGE_TIME_LIMIT = {
    'speed_run':       120,   # 2 menit
    'silent_operator': 180,   # 3 menit
    'blind_exam':      180,   # 3 menit, indikator dB disembunyikan
    'endurance':       300,   # 5 menit, multi-attempt
    'free_practice':     0,   # unlimited
}

# Threshold dB per challenge (override global MIC_THRESHOLD_DB)
CHALLENGE_DB_THRESHOLD = {
    'speed_run':       999,   # tidak ada batasan suara
    'silent_operator':  15,   # 15 dB di atas baseline
    'blind_exam':       15,   # sama, tapi tidak ditampilkan
    'endurance':        20,   # sedikit lebih toleran
    'free_practice':   999,
}

# Penalti skor per pelanggaran desibel
SCORE_PENALTY_PER_VIOLATION = int(os.environ.get('LOCKPICK_SCORE_PENALTY', '50'))

# Base skor awal (dikurangi per detik)
SCORE_BASE = int(os.environ.get('LOCKPICK_SCORE_BASE', '1000'))

# ─── Mortise Daftar Default ──────────────────────────────────────
# Format: (id, nama, difficulty 1-5)
MORTISE_LIST = [
    ('basic_3pin',    'Basic 3-Pin',           1),
    ('medium_4pin',   'Medium 4-Pin',          2),
    ('medium_5pin',   'Medium 5-Pin',          3),
    ('security_spool','Security Spool Pin',    4),
    ('advanced',      'Advanced Multi-Security',5),
]
