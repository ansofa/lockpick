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
VERSION = '1.0.0'
