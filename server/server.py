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

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from flask_socketio import SocketIO, emit


import config
import database
from sensor import ProximitySwitch
from sensor_mic import MicMonitor, list_audio_inputs
from sensor_stubs import ReedSwitchStub, AccelerometerStub
from database import format_ms, calculate_score

# ─── App Init ────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lockpick-s3cr3t-k3y-2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─── Global State ────────────────────────────────────────────
# mode: 'idle' | 'ready' | 'running' | 'stopped'
_state: dict = {
    'mode':           'idle',
    'player_name':    None,
    'session_id':     None,
    'start_mono':     None,     # time.monotonic() saat start
    'duration_ms':    None,
    'door_locked':    True,
    # Challenge info
    'challenge_type': 'free_practice',
    'mortise_id':     'basic_3pin',
    'time_limit_ms':  0,        # 0 = unlimited
    'show_db_meter':  True,
    # Mic / skor
    'violations':     0,
    'max_db':         0.0,
    'current_db':     0.0,
    'score':          None,
}
_state_lock = threading.Lock()

# ─── Helpers ─────────────────────────────────────────────────
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


# ─── Auth Decorator ──────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ─── Sensor Callbacks ────────────────────────────────────────
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


def _on_db_update(relative_db: float):
    """Callback dari MicMonitor setiap ~100ms. Emit ke semua client."""
    with _state_lock:
        if _state['mode'] != 'running':
            return
        _state['current_db'] = relative_db
        if relative_db > _state['max_db']:
            _state['max_db'] = relative_db
        show_meter = _state['show_db_meter']
        threshold  = config.CHALLENGE_DB_THRESHOLD.get(
            _state['challenge_type'], config.MIC_THRESHOLD_DB
        )

    socketio.emit('decibel_update', {
        'db':        round(relative_db, 1),
        'threshold': threshold,
        'show':      show_meter,
    })


def _on_violation(relative_db: float):
    """Callback dari MicMonitor saat threshold terlampaui."""
    with _state_lock:
        if _state['mode'] != 'running':
            return
        _state['violations'] += 1
        violations = _state['violations']
        session_id = _state['session_id']
        max_db     = _state['max_db']

    # Update DB violation counter (non-blocking)
    if session_id:
        database.update_violations(session_id, violations, max_db)

    socketio.emit('violation_alert', {
        'violations': violations,
        'db':         round(relative_db, 1),
    })
    print(f"[SERVER] 🔊 Violation #{violations} — {relative_db:.1f} dB")


def _stop_session(status: str = 'completed'):
    """Hentikan sesi berjalan & simpan ke DB. Thread-safe."""
    with _state_lock:
        if _state['mode'] != 'running':
            return
        ms             = _elapsed_ms()
        session_id     = _state['session_id']
        player         = _state['player_name']
        violations     = _state['violations']
        max_db         = _state['max_db']
        challenge_type = _state['challenge_type']
        time_limit_ms  = _state['time_limit_ms']
        end_time       = datetime.now()

        # Tentukan status pass/fail
        if time_limit_ms > 0 and ms >= time_limit_ms:
            status = 'timeout'
        else:
            status = 'completed'

        # Kalkulasi skor
        cfg   = database.get_challenge_config(challenge_type) or {}
        score = calculate_score(
            duration_ms=ms,
            violations=violations,
            time_limit_s=cfg.get('time_limit_sec', 0),
        )

        _state['mode']        = 'stopped'
        _state['duration_ms'] = ms
        _state['score']       = score

    # Operasi DB di luar lock
    database.complete_session(
        session_id=session_id,
        end_time=end_time,
        duration_ms=ms,
        violations=violations,
        max_db=max_db,
        score=score,
        status=status,
    )

    socketio.emit('session_complete', {
        'player_name':   player,
        'duration_ms':   ms,
        'display_time':  format_ms(ms),
        'score':         score,
        'violations':    violations,
        'max_db':        round(max_db, 1),
        'status':        status,
    })
    print(f"[SERVER] Sesi selesai: {player} → {format_ms(ms)} skor={score} violations={violations}")


def _check_timeout():
    """Background thread: cek time limit challenge, stop jika timeout."""
    while True:
        time.sleep(0.5)
        with _state_lock:
            if _state['mode'] != 'running':
                continue
            limit_ms = _state['time_limit_ms']
            if limit_ms <= 0:
                continue
            elapsed = _elapsed_ms()
            remaining = limit_ms - elapsed
            if remaining <= 0:
                pass  # akan di-stop di luar lock
            else:
                # Emit remaining time setiap 500ms untuk countdown di UI
                socketio.emit('time_remaining', {'remaining_ms': remaining})
                continue
        # Di sini kita sudah di luar with block, bisa stop session
        _stop_session('timeout')


# ─── Flask Routes ────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html',
                           unit_name=config.UNIT_NAME,
                           version=config.VERSION)


@app.route('/kiosk')
def kiosk():
    challenges = database.get_challenge_configs()
    mortises   = database.get_mortise_list()
    return render_template('kiosk.html',
                           unit_name=config.UNIT_NAME,
                           version=config.VERSION,
                           challenges=challenges,
                           mortises=mortises)


@app.route('/history')
def history():
    sessions    = database.get_all_sessions()
    leaderboard = database.get_leaderboard()
    for s in sessions:
        s['duration_display'] = format_ms(s.get('duration_ms'))
    for s in leaderboard:
        s['duration_display'] = format_ms(s.get('duration_ms'))
    return render_template('history.html',
                           unit_name=config.UNIT_NAME,
                           sessions=sessions,
                           leaderboard=leaderboard)


# ─── Admin Routes ────────────────────────────────────────────
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
    sessions   = database.get_all_sessions()
    challenges = database.get_challenge_configs()
    mortises   = database.get_mortise_list()
    audio_devs = list_audio_inputs()
    for s in sessions:
        s['duration_display'] = format_ms(s.get('duration_ms'))
    return render_template('admin.html',
                           sessions=sessions,
                           challenges=challenges,
                           mortises=mortises,
                           audio_devices=audio_devs)


@app.route('/admin/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(config.DATABASE_PATH)
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/export_csv')
@login_required
def export_csv():
    sessions = database.get_all_sessions(limit=10000)
    csv_data = database.sessions_to_csv(sessions)
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment; filename=lpst_sessions.csv"}
    )


@app.route('/admin/api/sysinfo')
@login_required
def api_sysinfo():
    """Mengembalikan metrik hardware Raspberry Pi sebagai JSON"""
    return jsonify(get_sys_info())


# ─── REST API ────────────────────────────────────────────────
@app.route('/api/v1/status')
def api_status():
    with _state_lock:
        ms = _elapsed_ms() if _state['mode'] == 'running' else 0
        return jsonify({
            'unit_name':      config.UNIT_NAME,
            'unit_id':        config.UNIT_ID,
            'version':        config.VERSION,
            'mode':           _state['mode'],
            'player_name':    _state['player_name'],
            'elapsed_ms':     ms,
            'door_locked':    _state['door_locked'],
            'challenge_type': _state['challenge_type'],
            'mortise_id':     _state['mortise_id'],
            'violations':     _state['violations'],
            'current_db':     round(_state['current_db'], 1),
        })


@app.route('/api/v1/info')
def api_info():
    return jsonify({
        'unit_name':  config.UNIT_NAME,
        'unit_id':    config.UNIT_ID,
        'version':    config.VERSION,
        'gpio_pin':   config.GPIO_PIN,
        'challenges': database.get_challenge_configs(),
        'mortises':   database.get_mortise_list(),
    })


@app.route('/api/v1/start', methods=['POST'])
def api_start():
    data           = request.get_json(silent=True) or {}
    player_name    = (data.get('player_name') or 'Anonymous').strip() or 'Anonymous'
    challenge_type = data.get('challenge_type', 'free_practice')
    mortise_id     = data.get('mortise_id', 'basic_3pin')

    with _state_lock:
        if _state['mode'] == 'running':
            return jsonify({'error': 'Sesi sedang berjalan'}), 409

        cfg        = database.get_challenge_config(challenge_type) or {}
        start_dt   = datetime.now()
        session_id = database.create_session(player_name, start_dt, challenge_type, mortise_id)

        _state.update({
            'mode':           'running',
            'player_name':    player_name,
            'session_id':     session_id,
            'start_mono':     time.monotonic(),
            'duration_ms':    None,
            'challenge_type': challenge_type,
            'mortise_id':     mortise_id,
            'time_limit_ms':  cfg.get('time_limit_sec', 0) * 1000,
            'show_db_meter':  bool(cfg.get('show_db_meter', 1)),
            'violations':     0,
            'max_db':         0.0,
            'current_db':     0.0,
            'score':          None,
        })

    # Kalibrasi mic untuk sesi baru
    if mic:
        threading.Thread(target=mic.calibrate, daemon=True).start()

    socketio.emit('session_start', {
        'player_name':    player_name,
        'challenge_type': challenge_type,
        'mortise_id':     mortise_id,
        'time_limit_ms':  _state['time_limit_ms'],
        'show_db_meter':  _state['show_db_meter'],
    })
    print(f"[SERVER] Sesi dimulai: {player_name} ({challenge_type}, {mortise_id})")
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
        _state.update({
            'mode': 'idle', 'player_name': None,
            'session_id': None, 'start_mono': None, 'duration_ms': None,
            'challenge_type': 'free_practice', 'mortise_id': 'basic_3pin',
            'violations': 0, 'max_db': 0.0, 'current_db': 0.0, 'score': None,
        })

    socketio.emit('session_reset')
    print("[SERVER] Reset.")
    return jsonify({'success': True})


@app.route('/api/v1/sessions')
def api_sessions():
    return jsonify(database.get_all_sessions())


@app.route('/api/v1/sessions/best')
def api_best():
    return jsonify(database.get_leaderboard())


@app.route('/api/v1/challenges')
def api_challenges():
    return jsonify(database.get_challenge_configs())


@app.route('/api/v1/mortises')
def api_mortises():
    return jsonify(database.get_mortise_list())


# ─── Simulation Endpoints ────────────────────────────────────
@app.route('/api/v1/simulate/lock', methods=['POST'])
def sim_lock():
    sensor.simulate_lock()
    return jsonify({'success': True, 'simulated': 'lock'})


@app.route('/api/v1/simulate/unlock', methods=['POST'])
def sim_unlock():
    sensor.simulate_unlock()
    return jsonify({'success': True, 'simulated': 'unlock'})


@app.route('/api/v1/simulate/noise', methods=['POST'])
def sim_noise():
    """Simulasikan event kebisingan tinggi (untuk testing mic tanpa hardware)."""
    data  = request.get_json(silent=True) or {}
    db_val = float(data.get('db', 20.0))
    if mic:
        mic.simulate_noise(db_val)
    return jsonify({'success': True, 'simulated': 'noise', 'db': db_val})


# ─── SocketIO Events ─────────────────────────────────────────
@socketio.on('connect')
def ws_connect():
    """Kirim state saat ini ke client yang baru connect."""
    with _state_lock:
        ms = _elapsed_ms() if _state['mode'] == 'running' else (_state['duration_ms'] or 0)
        emit('state_sync', {
            'mode':           _state['mode'],
            'player_name':    _state['player_name'],
            'elapsed_ms':     ms,
            'duration_ms':    _state['duration_ms'],
            'door_locked':    _state['door_locked'],
            'display':        format_ms(ms),
            'challenge_type': _state['challenge_type'],
            'mortise_id':     _state['mortise_id'],
            'time_limit_ms':  _state['time_limit_ms'],
            'show_db_meter':  _state['show_db_meter'],
            'violations':     _state['violations'],
            'score':          _state['score'],
        })
    print(f"[WS] Client connect")


@socketio.on('prepare_session')
def ws_prepare(data):
    player_name    = ((data or {}).get('player_name') or 'Anonymous').strip() or 'Anonymous'
    challenge_type = (data or {}).get('challenge_type', 'free_practice')
    mortise_id     = (data or {}).get('mortise_id', 'basic_3pin')

    cfg = database.get_challenge_config(challenge_type) or {}

    with _state_lock:
        if _state['mode'] == 'running':
            return
        _state.update({
            'mode':           'ready',
            'player_name':    player_name,
            'challenge_type': challenge_type,
            'mortise_id':     mortise_id,
            'time_limit_ms':  cfg.get('time_limit_sec', 0) * 1000,
            'show_db_meter':  bool(cfg.get('show_db_meter', 1)),
        })

    socketio.emit('session_ready', {
        'player_name':    player_name,
        'challenge_type': challenge_type,
        'mortise_id':     mortise_id,
        'time_limit_ms':  cfg.get('time_limit_sec', 0) * 1000,
        'show_db_meter':  bool(cfg.get('show_db_meter', 1)),
        'challenge_label': cfg.get('label', challenge_type),
    })
    print(f"[WS] Sesi disiapkan: {player_name} ({challenge_type}, {mortise_id})")


@socketio.on('start_session')
def ws_start(data):
    with _state_lock:
        if _state['mode'] == 'running':
            return

        player_name    = _state['player_name'] or \
                         ((data or {}).get('player_name') or 'Anonymous').strip() or 'Anonymous'
        challenge_type = _state['challenge_type']
        mortise_id     = _state['mortise_id']
        time_limit_ms  = _state['time_limit_ms']
        show_db_meter  = _state['show_db_meter']

        start_dt   = datetime.now()
        session_id = database.create_session(player_name, start_dt, challenge_type, mortise_id)
        _state.update({
            'mode':        'running',
            'player_name': player_name,
            'session_id':  session_id,
            'start_mono':  time.monotonic(),
            'duration_ms': None,
            'violations':  0,
            'max_db':      0.0,
            'current_db':  0.0,
            'score':       None,
        })

    # Kalibrasi mic di background (non-blocking)
    if mic:
        threading.Thread(target=mic.calibrate, daemon=True).start()

    socketio.emit('session_start', {
        'player_name':    player_name,
        'challenge_type': challenge_type,
        'mortise_id':     mortise_id,
        'time_limit_ms':  time_limit_ms,
        'show_db_meter':  show_db_meter,
    })
    print(f"[WS] Sesi dimulai: {player_name} ({challenge_type})")


@socketio.on('reset_session')
def ws_reset(data=None):
    with _state_lock:
        if _state['session_id'] and _state['mode'] == 'running':
            database.cancel_session(_state['session_id'])
        _state.update({
            'mode': 'idle', 'player_name': None,
            'session_id': None, 'start_mono': None, 'duration_ms': None,
            'challenge_type': 'free_practice', 'mortise_id': 'basic_3pin',
            'violations': 0, 'max_db': 0.0, 'current_db': 0.0, 'score': None,
        })
    socketio.emit('session_reset')
    print("[WS] Reset.")


# ─── Main ────────────────────────────────────────────────────
sensor: ProximitySwitch = None
mic:    MicMonitor      = None


if __name__ == '__main__':
    # Init DB
    database.init_db()

    is_dev = os.environ.get('LOCKPICK_DEV') == '1'

    if not is_dev or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Init proximity sensor
        sensor = ProximitySwitch(
            pin=config.GPIO_PIN,
            on_lock=_on_door_locked,
            on_unlock=_on_door_unlocked,
        )
        sensor.start()

        # Init mic monitor (USB mic — auto-detect)
        mic = MicMonitor(
            device_index=config.MIC_DEVICE_INDEX,  # None = auto-detect USB mic
            threshold_db=config.MIC_THRESHOLD_DB,
            calibration_sec=config.MIC_CALIBRATION_SEC,
            on_db_update=_on_db_update,
            on_violation=_on_violation,
        )
        # Kalibrasi awal (blocking, sebelum server terima request)
        print("[SERVER] Kalibrasi mic awal …")
        mic.calibrate()
        mic.start()

        # Timeout checker thread
        threading.Thread(target=_check_timeout, daemon=True, name="timeout-check").start()

    print("=" * 50)
    print(f"  🔒 LOCKPICK SIMULATOR v{config.VERSION}")
    print(f"  📡 Unit : {config.UNIT_NAME} ({config.UNIT_ID})")
    print(f"  🌐 URL  : http://{config.HOST}:{config.PORT}")
    print(f"  🔌 GPIO : Pin {config.GPIO_PIN}")
    print(f"  🎙️  MIC  : threshold={config.MIC_THRESHOLD_DB} dB")
    print("=" * 50)

    if is_dev:
        print("  🛠️  DEV MODE AKTIF (Auto-reload enabled)")
        print("=" * 50)

    socketio.run(app, host=config.HOST, port=config.PORT, debug=is_dev, allow_unsafe_werkzeug=True)
