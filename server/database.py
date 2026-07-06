"""
Lockpick Simulator — SQLite Database Handler
Menyimpan semua sesi permainan (player name, waktu mulai, durasi).
"""
import sqlite3
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
    """Buat tabel jika belum ada. Dipanggil sekali saat server start."""
    os.makedirs(os.path.dirname(os.path.abspath(config.DATABASE_PATH)), exist_ok=True)
    with _get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT    NOT NULL,
                start_time  TEXT    NOT NULL,
                end_time    TEXT,
                duration_ms INTEGER,
                completed   INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    print(f"[DB] Database siap: {config.DATABASE_PATH}")


def create_session(player_name: str, start_time: datetime) -> int:
    """Buat sesi baru. Return session ID."""
    with _get_conn() as conn:
        cursor = conn.execute(
            'INSERT INTO sessions (player_name, start_time) VALUES (?, ?)',
            (player_name, start_time.isoformat())
        )
        conn.commit()
        return cursor.lastrowid


def complete_session(session_id: int, end_time: datetime, duration_ms: int) -> None:
    """Tandai sesi sebagai selesai dengan durasi final."""
    with _get_conn() as conn:
        conn.execute(
            '''UPDATE sessions
               SET end_time = ?, duration_ms = ?, completed = 1
               WHERE id = ?''',
            (end_time.isoformat(), duration_ms, session_id)
        )
        conn.commit()


def cancel_session(session_id: int) -> None:
    """Hapus sesi yang di-reset sebelum selesai."""
    with _get_conn() as conn:
        conn.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
        conn.commit()


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
    """Ambil top N sesi dengan waktu tercepat."""
    with _get_conn() as conn:
        rows = conn.execute(
            '''SELECT * FROM sessions
               WHERE completed = 1
               ORDER BY duration_ms ASC
               LIMIT ?''',
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def format_ms(ms: Optional[int]) -> str:
    """Format milliseconds → MM:SS.mmm string."""
    if ms is None:
        return '--:---.---'
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    millis  = ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
