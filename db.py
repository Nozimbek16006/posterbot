import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "bot_data.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                schedule_hour INTEGER,
                schedule_minute INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_admins (
                channel_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (channel_id, user_id),
                FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS channel_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                topic_name TEXT NOT NULL,
                official_link TEXT,
                FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE
            )
        """)


def add_channel(channel_id: str, owner_user_id: int) -> bool:
    """Yangi kanal qo'shadi, egasini birinchi admin qilib belgilaydi.
    Kanal allaqachon mavjud bo'lsa False qaytaradi."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO channels (channel_id, owner_user_id) VALUES (?, ?)",
            (channel_id, owner_user_id),
        )
        conn.execute(
            "INSERT INTO channel_admins (channel_id, user_id) VALUES (?, ?)",
            (channel_id, owner_user_id),
        )
        return True


def get_channels_for_user(user_id: int) -> list[dict]:
    """Foydalanuvchi admin bo'lgan barcha kanallarni qaytaradi."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT c.channel_id, c.schedule_hour, c.schedule_minute, c.owner_user_id
            FROM channels c
            JOIN channel_admins a ON a.channel_id = c.channel_id
            WHERE a.user_id = ?
            ORDER BY c.created_at
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]


def is_channel_admin(channel_id: str, user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM channel_admins WHERE channel_id = ? AND user_id = ?",
            (channel_id, user_id),
        ).fetchone()
        return row is not None


def add_channel_admin(channel_id: str, user_id: int) -> bool:
    """Kanalga yangi admin qo'shadi. Allaqachon admin bo'lsa False qaytaradi."""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM channel_admins WHERE channel_id = ? AND user_id = ?",
            (channel_id, user_id),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO channel_admins (channel_id, user_id) VALUES (?, ?)",
            (channel_id, user_id),
        )
        return True


def remove_channel_admin(channel_id: str, user_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM channel_admins WHERE channel_id = ? AND user_id = ?",
            (channel_id, user_id),
        )
        return cur.rowcount > 0


def set_schedule(channel_id: str, hour: int, minute: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE channels SET schedule_hour = ?, schedule_minute = ? WHERE channel_id = ?",
            (hour, minute, channel_id),
        )


def clear_schedule(channel_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE channels SET schedule_hour = NULL, schedule_minute = NULL WHERE channel_id = ?",
            (channel_id,),
        )


def get_all_scheduled_channels() -> list[dict]:
    """Jadval belgilangan barcha kanallarni qaytaradi (kunlik post uchun)."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT channel_id, schedule_hour, schedule_minute
            FROM channels
            WHERE schedule_hour IS NOT NULL AND schedule_minute IS NOT NULL
        """).fetchall()
        return [dict(r) for r in rows]


def add_topic(channel_id: str, topic_name: str, official_link: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO channel_topics (channel_id, topic_name, official_link) VALUES (?, ?, ?)",
            (channel_id, topic_name, official_link),
        )


def get_topics(channel_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT topic_name, official_link FROM channel_topics WHERE channel_id = ?",
            (channel_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def channel_exists(channel_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        return row is not None