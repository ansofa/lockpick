#!/usr/bin/env python3
"""
Lockpick Simulator — Flask + SocketIO Web Server
Entry point utama. Jalankan dengan: python server.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import threading
import time
import shutil
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit


import config
import database
from sensor import ProximitySwitch
from database import format_ms

# ─── App Init ────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lockpick-s3cr3t-k3y-2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─── Global State ────────────────────────────────────────────────
# mode: 'idle' | 'running' | 'stopped'
_state: dict = {
    'mode':        'idle',
    'player_name': None,
    'session_id':  None,
    'start_mono':  None,   # time.monotonic() saat start
    'duration_ms': None,
    'door_locked': True,
}
_state_lock = threading.Lock()

# ─── Helpers ─────────────────────────────────────────────────────
def _elapsed_ms() -> int:
    """Hitung elapsed time dalam ms. Harus dipanggil dalam lock."""
    if _state['start_mono'] is None:
        return 0
    return int((time.monotonic() - _state['start_mono']) * 1000)


def get_sys_info():
    """Mengambil status hardware Raspberry Pi"""
    info = {'cpu_temp': '--', 'cpu_load': '--', 'mem_usage': '--'}
    
    # Suhu CPU
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp_c = int(f.read().strip()) / 1000.0
            info['cpu_temp'] = f"{temp_c:.1f}°C"
    except Exception:
        info['cpu_temp'] = "N/A"
        
    # CPU Load
    try:
        load1, load5, load15 = os.getloadavg()
        info['cpu_load'] = f"{load1:.2f} (1m)"
    except Exception:
        info['cpu_load'] = "N/A"
        
    # Memori (RAM)
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            mem_total = mem_available = 0
            for line in lines:
                if line.startswith('MemTotal:'):
                    mem_total = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    mem_available = int(line.split()[1])
            if mem_total > 0:
                mem_used = mem_total - mem_available
                percent = (mem_used / mem_total) * 100
                info['mem_usage'] = f"{percent:.1f}%"
    except Exception:
        info['mem_usage'] = "N/A"
        
    return info


# ─── Auth Decorator ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ─── Timer Thread ────────────────────────────────────────────────
def _timer_loop():
    """Background thread: tidak lagi digunakan (kalkulasi timer dipindah ke client)."""
    pass


# ─── Sensor Callbacks ────────────────────────────────────────────
def _on_door_locked():
    with _state_lock:
        _state['door_locked'] = True
    socketio.emit('door_status', {'locked': True, 'label': '🔒 DEADBOLT AKTIF'})
    print("[SERVER] Door → LOCKED")


def _on_door_unlocked():
    should_stop = False
    with _state_lock:
        _state['door_locked'] = False
        if _state['mode'] == 'running':
            should_stop = True

    socketio.emit('door_status', {'locked': False, 'label': '🔓 DEADBOLT TERBUKA'})
    print("[SERVER] Door → UNLOCKED")

    if should_stop:
        _stop_session()


def _stop_session():
    """Hentikan sesi berjalan & simpan ke DB. Thread-safe."""
    with _state_lock:
        if _state['mode'] != 'running':
            return
        ms         = _elapsed_ms()
        session_id = _state['session_id']
        player     = _state['player_name']
        end_time   = datetime.now()

        _state['mode']        = 'stopped'
        _state['duration_ms'] = ms

    # Operasi DB di luar lock
    database.complete_session(session_id, end_time, ms)

    socketio.emit('session_complete', {
        'player_name':  player,
        'duration_ms':  ms,
        'display_time': format_ms(ms),
    })
    print(f"[SERVER] Sesi selesai: {player} → {format_ms(ms)}")


# ─── Flask Routes ────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html',
                           unit_name=config.UNIT_NAME,
                           version=config.VERSION)


@app.route('/kiosk')
def kiosk():
    return render_template('kiosk.html',
                           unit_name=config.UNIT_NAME,
                           version=config.VERSION)


@app.route('/history')
def history():
    sessions    = database.get_all_sessions()
    leaderboard = database.get_leaderboard()
    # Format durasi sebelum render
    for s in sessions:
        s['duration_display'] = format_ms(s.get('duration_ms'))
    for s in leaderboard:
        s['duration_display'] = format_ms(s.get('duration_ms'))
    return render_template('history.html',
                           unit_name=config.UNIT_NAME,
                           sessions=sessions,
                           leaderboard=leaderboard)


# ─── Admin Routes ────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == config.ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Password salah.'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin_dashboard():
    sessions = database.get_all_sessions()
    for s in sessions:
        s['duration_display'] = format_ms(s.get('duration_ms'))
    return render_template('admin.html', sessions=sessions)


@app.route('/admin/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    # Untuk fitur hapus, kita gunakan query DELETE langsung
    import sqlite3
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/api/sysinfo')
@login_required
def api_sysinfo():
    """Mengembalikan metrik hardware Raspberry Pi sebagai JSON"""
    return jsonify(get_sys_info())


# ─── REST API (untuk Fase 2 Lockpick Manager) ────────────────────
@app.route('/api/v1/status')
def api_status():
    with _state_lock:
        ms = _elapsed_ms() if _state['mode'] == 'running' else 0
        return jsonify({
            'unit_name':   config.UNIT_NAME,
            'unit_id':     config.UNIT_ID,
            'version':     config.VERSION,
            'mode':        _state['mode'],
            'player_name': _state['player_name'],
            'elapsed_ms':  ms,
            'door_locked': _state['door_locked'],
        })


@app.route('/api/v1/info')
def api_info():
    return jsonify({
        'unit_name': config.UNIT_NAME,
        'unit_id':   config.UNIT_ID,
        'version':   config.VERSION,
        'gpio_pin':  config.GPIO_PIN,
    })


@app.route('/api/v1/start', methods=['POST'])
def api_start():
    data        = request.get_json(silent=True) or {}
    player_name = (data.get('player_name') or 'Anonymous').strip() or 'Anonymous'

    with _state_lock:
        if _state['mode'] == 'running':
            return jsonify({'error': 'Sesi sedang berjalan'}), 409

        start_dt   = datetime.now()
        session_id = database.create_session(player_name, start_dt)

        _state['mode']        = 'running'
        _state['player_name'] = player_name
        _state['session_id']  = session_id
        _state['start_mono']  = time.monotonic()
        _state['duration_ms'] = None

    socketio.emit('session_start', {'player_name': player_name})
    print(f"[SERVER] Sesi dimulai: {player_name}")
    return jsonify({'success': True, 'session_id': session_id})


@app.route('/api/v1/stop', methods=['POST'])
def api_stop():
    with _state_lock:
        if _state['mode'] != 'running':
            return jsonify({'error': 'Tidak ada sesi aktif'}), 409
    _stop_session()
    return jsonify({'success': True})


@app.route('/api/v1/reset', methods=['POST'])
def api_reset():
    with _state_lock:
        if _state['session_id'] and _state['mode'] == 'running':
            database.cancel_session(_state['session_id'])
        _state.update({'mode': 'idle', 'player_name': None,
                       'session_id': None, 'start_mono': None, 'duration_ms': None})

    socketio.emit('session_reset')
    print("[SERVER] Reset.")
    return jsonify({'success': True})


@app.route('/api/v1/sessions')
def api_sessions():
    return jsonify(database.get_all_sessions())


@app.route('/api/v1/sessions/best')
def api_best():
    return jsonify(database.get_leaderboard())


# ─── Simulation Endpoints (untuk development tanpa RPi) ──────────
@app.route('/api/v1/simulate/lock', methods=['POST'])
def sim_lock():
    sensor.simulate_lock()
    return jsonify({'success': True, 'simulated': 'lock'})


@app.route('/api/v1/simulate/unlock', methods=['POST'])
def sim_unlock():
    sensor.simulate_unlock()
    return jsonify({'success': True, 'simulated': 'unlock'})


# ─── SocketIO Events ─────────────────────────────────────────────
@socketio.on('connect')
def ws_connect():
    """Kirim state saat ini ke client yang baru connect."""
    with _state_lock:
        ms = _elapsed_ms() if _state['mode'] == 'running' else (_state['duration_ms'] or 0)
        emit('state_sync', {
            'mode':        _state['mode'],
            'player_name': _state['player_name'],
            'elapsed_ms':  ms,
            'duration_ms': _state['duration_ms'],
            'door_locked': _state['door_locked'],
            'display':     format_ms(ms),
        })
    print(f"[WS] Client connect")


@socketio.on('prepare_session')
def ws_prepare(data):
    player_name = ((data or {}).get('player_name') or 'Anonymous').strip() or 'Anonymous'
    with _state_lock:
        if _state['mode'] == 'running':
            return
        _state.update({
            'mode':        'ready',
            'player_name': player_name,
        })
    socketio.emit('session_ready', {'player_name': player_name})
    print(f"[WS] Sesi disiapkan: {player_name}")


@socketio.on('start_session')
def ws_start(data):
    with _state_lock:
        if _state['mode'] == 'running':
            return
        
        # Ambil nama pemain dari state 'ready', jika tidak ada fallback ke payload data
        player_name = _state['player_name']
        if not player_name or _state['mode'] == 'idle':
             player_name = ((data or {}).get('player_name') or 'Anonymous').strip() or 'Anonymous'

        start_dt   = datetime.now()
        session_id = database.create_session(player_name, start_dt)
        _state.update({
            'mode':        'running',
            'player_name': player_name,
            'session_id':  session_id,
            'start_mono':  time.monotonic(),
            'duration_ms': None,
        })
    socketio.emit('session_start', {'player_name': player_name})
    print(f"[WS] Sesi dimulai: {player_name}")


@socketio.on('reset_session')
def ws_reset(data=None):
    with _state_lock:
        if _state['session_id'] and _state['mode'] == 'running':
            database.cancel_session(_state['session_id'])
        _state.update({'mode': 'idle', 'player_name': None,
                       'session_id': None, 'start_mono': None, 'duration_ms': None})
    socketio.emit('session_reset')
    print("[WS] Reset.")


# ─── Main ────────────────────────────────────────────────────────
sensor: ProximitySwitch = None  # global agar bisa diakses endpoint simulate


if __name__ == '__main__':
    # Init DB
    database.init_db()

    # Aktifkan auto-reload (debug=True) jika ada env var LOCKPICK_DEV=1
    is_dev = os.environ.get('LOCKPICK_DEV') == '1'

    # Cegah inisialisasi sensor di parent process (watcher) saat debug mode
    if not is_dev or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Init sensor
        sensor = ProximitySwitch(
            pin=config.GPIO_PIN,
            on_lock=_on_door_locked,
            on_unlock=_on_door_unlocked,
        )
        sensor.start()

        # Timer thread (disabled to save CPU, UI handled client-side via rAF)
        # threading.Thread(target=_timer_loop, daemon=True, name="timer").start()

    print("=" * 50)
    print(f"  🔒 LOCKPICK SIMULATOR v{config.VERSION}")
    print(f"  📡 Unit : {config.UNIT_NAME} ({config.UNIT_ID})")
    print(f"  🌐 URL  : http://{config.HOST}:{config.PORT}")
    print(f"  🔌 GPIO : Pin {config.GPIO_PIN}")
    print("=" * 50)

    if is_dev:
        print("  🛠️  DEV MODE AKTIF (Auto-reload enabled)")
        print("=" * 50)
        
    socketio.run(app, host=config.HOST, port=config.PORT, debug=is_dev, allow_unsafe_werkzeug=True)
