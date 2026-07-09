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
from datetime import datetime

from flask import Flask, render_template, request, jsonify
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


# ─── Timer Thread ────────────────────────────────────────────────
def _timer_loop():
    """Background thread: emit timer_update setiap 50ms selama running."""
    while True:
        with _state_lock:
            if _state['mode'] == 'running':
                ms = _elapsed_ms()
                socketio.emit('timer_update', {
                    'elapsed_ms': ms,
                    'display':    format_ms(ms),
                })
        time.sleep(0.05)


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


@socketio.on('start_session')
def ws_start(data):
    player_name = ((data or {}).get('player_name') or 'Anonymous').strip() or 'Anonymous'
    with _state_lock:
        if _state['mode'] == 'running':
            return
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

    # Init sensor
    sensor = ProximitySwitch(
        pin=config.GPIO_PIN,
        on_lock=_on_door_locked,
        on_unlock=_on_door_unlocked,
    )
    sensor.start()

    # Timer thread
    threading.Thread(target=_timer_loop, daemon=True, name="timer").start()

    print("=" * 50)
    print(f"  🔒 LOCKPICK SIMULATOR v{config.VERSION}")
    print(f"  📡 Unit : {config.UNIT_NAME} ({config.UNIT_ID})")
    print(f"  🌐 URL  : http://{config.HOST}:{config.PORT}")
    print(f"  🔌 GPIO : Pin {config.GPIO_PIN}")
    print("=" * 50)

    # Aktifkan auto-reload (debug=True) jika ada env var LOCKPICK_DEV=1
    is_dev = os.environ.get('LOCKPICK_DEV') == '1'
    if is_dev:
        print("  🛠️  DEV MODE AKTIF (Auto-reload enabled)")
        print("=" * 50)
        
    socketio.run(app, host=config.HOST, port=config.PORT, debug=is_dev, allow_unsafe_werkzeug=True)
