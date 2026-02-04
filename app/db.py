import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "bot.db"))

def ensure_dirs():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_db():
    ensure_dirs()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'ro',
            timezone TEXT DEFAULT 'Europe/Chisinau',
            uni_notify TEXT DEFAULT '30m',
            event_notify TEXT DEFAULT '30m',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS job_anchor (
            user_id INTEGER PRIMARY KEY,
            anchor_date TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS uni_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            dow TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            subject TEXT NOT NULL,
            room TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            start_dt TEXT NOT NULL,
            location TEXT,
            reminders TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        """)
        conn.commit()

@contextmanager
def get_conn():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    finally:
        conn.close()

def ensure_user(user_id: int, tz: str = "Europe/Chisinau"):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO users(user_id, timezone) VALUES(?, ?)", (user_id, tz))

def get_user_settings(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT timezone, uni_notify, event_notify FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row if row else ("Europe/Chisinau", "30m", "30m")

def set_user_uni_notify(user_id: int, val: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET uni_notify=? WHERE user_id=?", (val, user_id))

def set_user_event_notify(user_id: int, val: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET event_notify=? WHERE user_id=?", (val, user_id))

def set_job_anchor(user_id: int, anchor_date: str):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO job_anchor(user_id, anchor_date) VALUES(?, ?)", (user_id, anchor_date))

def get_job_anchor(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT anchor_date FROM job_anchor WHERE user_id=?", (user_id,)).fetchone()
        return row[0] if row else None

def add_pair(user_id: int, dow: str, start_time: str, end_time: str, subject: str, room: str | None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO uni_pairs(user_id, dow, start_time, end_time, subject, room) VALUES(?,?,?,?,?,?)",
            (user_id, dow, start_time, end_time, subject, room),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def list_pairs(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, dow, start_time, end_time, subject, COALESCE(room,'') FROM uni_pairs WHERE user_id=? ORDER BY dow, start_time",
            (user_id,),
        ).fetchall()

def delete_pair(user_id: int, pair_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM uni_pairs WHERE user_id=? AND id=?", (user_id, pair_id))
        return cur.rowcount > 0

def clear_pairs(user_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM uni_pairs WHERE user_id=?", (user_id,))
        return cur.rowcount

def update_pair(user_id: int, pair_id: int, dow: str, start_time: str, end_time: str, subject: str, room: str | None) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE uni_pairs SET dow=?, start_time=?, end_time=?, subject=?, room=? WHERE user_id=? AND id=?",
            (dow, start_time, end_time, subject, room, user_id, pair_id),
        )
        return cur.rowcount > 0

def add_event(user_id: int, title: str, start_iso: str, location: str | None, reminders: str | None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events(user_id, title, start_dt, location, reminders) VALUES(?,?,?,?,?)",
            (user_id, title, start_iso, location, reminders),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def list_events(user_id: int, from_iso: str | None = None, to_iso: str | None = None):
    q = "SELECT id, title, start_dt, COALESCE(location,''), COALESCE(reminders,'') FROM events WHERE user_id=?"
    params = [user_id]
    if from_iso:
        q += " AND start_dt>=?"
        params.append(from_iso)
    if to_iso:
        q += " AND start_dt<=?"
        params.append(to_iso)
    q += " ORDER BY start_dt"
    with get_conn() as conn:
        return conn.execute(q, tuple(params)).fetchall()

def get_event(user_id: int, event_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, title, start_dt, COALESCE(location,''), COALESCE(reminders,'') FROM events WHERE user_id=? AND id=?",
            (user_id, event_id),
        ).fetchone()

def delete_event(user_id: int, event_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM events WHERE user_id=? AND id=?", (user_id, event_id))
        return cur.rowcount > 0
