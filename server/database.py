"""
Lockpick Simulator — SQLite Database Handler
Menyimpan semua sesi permainan beserta data challenge, skor, dan pelanggaran.
"""
import sqlite3
import csv
import io
import os
from datetime import datetime
from typing import Optional

import config


def _get_conn() -> sqlite3.Connection:
    """Buat koneksi SQLite dengan row_factory agar hasil bisa diakses seperti dict."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Buat/migrasi tabel jika belum ada. Dipanggil sekali saat server start."""
    os.makedirs(os.path.dirname(os.path.abspath(config.DATABASE_PATH)), exist_ok=True)
    with _get_conn() as conn:
        # Tabel utama sesi
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name    TEXT    NOT NULL,
                challenge_type TEXT    DEFAULT 'free_practice',
                mortise_id     TEXT    DEFAULT 'basic_3pin',
                start_time     TEXT    NOT NULL,
                end_time       TEXT,
                duration_ms    INTEGER,
                score          INTEGER,
                violations     INTEGER DEFAULT 0,
                max_db         REAL    DEFAULT 0.0,
                status         TEXT    DEFAULT 'pending',
                completed      INTEGER DEFAULT 0,
                created_at     TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabel konfigurasi challenge (instruktur dapat override)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS challenge_configs (
                challenge_type TEXT PRIMARY KEY,
                label          TEXT    NOT NULL,
                time_limit_sec INTEGER DEFAULT 0,
                db_threshold   REAL    DEFAULT 15.0,
                show_db_meter  INTEGER DEFAULT 1,
                max_attempts   INTEGER DEFAULT 0,
                enabled        INTEGER DEFAULT 1
            )
        ''')

        # Tabel daftar mortise
        conn.execute('''
            CREATE TABLE IF NOT EXISTS mortises (
                id         TEXT PRIMARY KEY,
                label      TEXT    NOT NULL,
                difficulty INTEGER DEFAULT 1,
                enabled    INTEGER DEFAULT 1
            )
        ''')

        conn.commit()

    # Migrasi: tambah kolom baru ke tabel existing jika belum ada
    _migrate_columns()

    # Seed data default
    _seed_defaults()

    print(f"[DB] Database siap: {config.DATABASE_PATH}")


def _migrate_columns() -> None:
    """Tambah kolom baru ke tabel sessions jika upgrade dari versi lama."""
    new_columns = [
        ("challenge_type", "TEXT DEFAULT 'free_practice'"),
        ("mortise_id",     "TEXT DEFAULT 'basic_3pin'"),
        ("score",          "INTEGER"),
        ("violations",     "INTEGER DEFAULT 0"),
        ("max_db",         "REAL DEFAULT 0.0"),
        ("status",         "TEXT DEFAULT 'pending'"),
    ]
    with _get_conn() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        for col_name, col_def in new_columns:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_def}")
                print(f"[DB] Migrasi: kolom '{col_name}' ditambahkan ke tabel sessions.")
        conn.commit()


def _seed_defaults() -> None:
    """Insert data default challenge_configs dan mortises jika tabel kosong."""
    with _get_conn() as conn:
        # Challenge configs
        defaults_challenge = [
            ('free_practice',   'Free Practice',    0,   999, 1, 0, 1),
            ('speed_run',       'Speed Run',       120,  999, 1, 0, 1),
            ('silent_operator', 'Silent Operator', 180,   15, 1, 0, 1),
            ('blind_exam',      'Blind Exam',      180,   15, 0, 0, 1),
            ('endurance',       'Endurance',       300,   20, 1, 3, 1),
        ]
        for row in defaults_challenge:
            conn.execute('''
                INSERT OR IGNORE INTO challenge_configs
                (challenge_type, label, time_limit_sec, db_threshold, show_db_meter, max_attempts, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', row)

        # Mortise defaults
        defaults_mortise = list(config.MORTISE_LIST)
        for row in defaults_mortise:
            conn.execute('''
                INSERT OR IGNORE INTO mortises (id, label, difficulty)
                VALUES (?, ?, ?)
            ''', row)

        conn.commit()


# ─── Session CRUD ─────────────────────────────────────────────────

def create_session(
    player_name:    str,
    start_time:     datetime,
    challenge_type: str = 'free_practice',
    mortise_id:     str = 'basic_3pin',
) -> int:
    """Buat sesi baru. Return session ID."""
    with _get_conn() as conn:
        cursor = conn.execute(
            '''INSERT INTO sessions (player_name, challenge_type, mortise_id, start_time, status)
               VALUES (?, ?, ?, ?, 'running')''',
            (player_name, challenge_type, mortise_id, start_time.isoformat())
        )
        conn.commit()
        return cursor.lastrowid


def complete_session(
    session_id:  int,
    end_time:    datetime,
    duration_ms: int,
    violations:  int  = 0,
    max_db:      float = 0.0,
    score:       Optional[int] = None,
    status:      str  = 'completed',
) -> None:
    """Tandai sesi sebagai selesai dengan durasi final dan data skor."""
    with _get_conn() as conn:
        conn.execute(
            '''UPDATE sessions
               SET end_time = ?, duration_ms = ?, violations = ?, max_db = ?,
                   score = ?, status = ?, completed = 1
               WHERE id = ?''',
            (end_time.isoformat(), duration_ms, violations, max_db, score, status, session_id)
        )
        conn.commit()


def update_violations(session_id: int, violations: int, max_db: float) -> None:
    """Update jumlah violation dan max dB sesi yang sedang berjalan (live update)."""
    with _get_conn() as conn:
        conn.execute(
            'UPDATE sessions SET violations = ?, max_db = ? WHERE id = ?',
            (violations, max_db, session_id)
        )
        conn.commit()


def cancel_session(session_id: int) -> None:
    """Tandai sesi di-reset sebelum selesai."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET status = 'cancelled', completed = 0 WHERE id = ?",
            (session_id,)
        )
        conn.commit()


# ─── Query ────────────────────────────────────────────────────────

def get_all_sessions(limit: int = 100) -> list[dict]:
    """Ambil semua sesi selesai, terbaru dulu."""
    with _get_conn() as conn:
        rows = conn.execute(
            '''SELECT * FROM sessions
               WHERE completed = 1
               ORDER BY created_at DESC
               LIMIT ?''',
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_leaderboard(limit: int = 10) -> list[dict]:
    """Ambil top N sesi berdasarkan skor tertinggi, lalu waktu tercepat."""
    with _get_conn() as conn:
        rows = conn.execute(
            '''SELECT * FROM sessions
               WHERE completed = 1 AND status = 'completed'
               ORDER BY score DESC, duration_ms ASC
               LIMIT ?''',
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_player_stats(player_name: str) -> dict:
    """Ambil statistik agregat per player."""
    with _get_conn() as conn:
        row = conn.execute(
            '''SELECT
                COUNT(*) as total_sessions,
                COUNT(CASE WHEN status='completed' THEN 1 END) as total_completed,
                MIN(duration_ms) as best_time_ms,
                MAX(score) as best_score,
                AVG(duration_ms) as avg_time_ms,
                SUM(violations) as total_violations,
                AVG(violations) as avg_violations
               FROM sessions
               WHERE player_name = ? AND completed = 1''',
            (player_name,)
        ).fetchone()
        return dict(row) if row else {}


def get_challenge_configs() -> list[dict]:
    """Ambil semua konfigurasi challenge."""
    with _get_conn() as conn:
        rows = conn.execute(
            'SELECT * FROM challenge_configs WHERE enabled = 1 ORDER BY time_limit_sec'
        ).fetchall()
        return [dict(row) for row in rows]


def get_challenge_config(challenge_type: str) -> Optional[dict]:
    """Ambil konfigurasi satu challenge."""
    with _get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM challenge_configs WHERE challenge_type = ?',
            (challenge_type,)
        ).fetchone()
        return dict(row) if row else None


def get_mortise_list() -> list[dict]:
    """Ambil daftar mortise yang tersedia."""
    with _get_conn() as conn:
        rows = conn.execute(
            'SELECT * FROM mortises WHERE enabled = 1 ORDER BY difficulty'
        ).fetchall()
        return [dict(row) for row in rows]


def sessions_to_csv(sessions: list[dict]) -> str:
    """Konversi list sesi ke format CSV string."""
    if not sessions:
        return ""
    fields = ['id', 'player_name', 'challenge_type', 'mortise_id',
              'start_time', 'end_time', 'duration_ms', 'score',
              'violations', 'max_db', 'status']
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(sessions)
    return output.getvalue()


# ─── Utilities ────────────────────────────────────────────────────

def calculate_score(
    duration_ms:  int,
    violations:   int,
    time_limit_s: int   = 0,
    base_score:   int   = None,
    penalty_per:  int   = None,
) -> int:
    """
    Kalkulasi skor akhir sesi.

    Formula:
      base = SCORE_BASE - (duration_sec * 1.0)   ← makin cepat makin tinggi
      penalty = violations * PENALTY_PER_VIOLATION
      final = max(0, base - penalty)
    """
    if base_score is None:
        base_score = config.SCORE_BASE
    if penalty_per is None:
        penalty_per = config.SCORE_PENALTY_PER_VIOLATION

    duration_sec = duration_ms / 1000.0
    base         = max(0, base_score - int(duration_sec))
    penalty      = violations * penalty_per
    return max(0, base - penalty)


def format_ms(ms: Optional[int]) -> str:
    """Format milliseconds → MM:SS.mmm string."""
    if ms is None:
        return '--:---.---'
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    millis  = ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
