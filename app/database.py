import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, Optional

from .config import DATABASE_PATH


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def initialize():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'dungeon_master', 'adventurer')),
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                max_seats INTEGER NOT NULL,
                created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                is_finalized INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS game_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status TEXT NOT NULL CHECK(status IN ('invited', 'joined', 'confirmed')),
                is_default INTEGER NOT NULL DEFAULT 0,
                UNIQUE(game_id, user_id)
            )
            """
        )
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        if total_users == 0:
            from .auth import PasswordHasher

            password_hash = PasswordHasher.hash_password("admin123")
            cur.execute(
                """
                INSERT INTO users (email, password_hash, display_name, role, created_at)
                VALUES (?, ?, ?, 'admin', ?)
                """,
                ("admin@example.com", password_hash, "Administrator", now_iso()),
            )
        conn.commit()


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def create_user(email: str, password_hash: str, display_name: str, role: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (email, password_hash, display_name, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (email, password_hash, display_name, role, now_iso()),
        )
        conn.commit()
        return cur.lastrowid


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        return cur.fetchone()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cur.fetchone()


def list_users_by_role(role: str) -> Iterable[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE role = ? ORDER BY display_name", (role,))
        return cur.fetchall()


def create_character(owner_id: int, name: str, class_name: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO characters (owner_id, name, class_name, created_at) VALUES (?, ?, ?, ?)",
            (owner_id, name, class_name, now_iso()),
        )
        conn.commit()
        return cur.lastrowid


def list_characters(owner_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM characters WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        )
        return cur.fetchall()


def get_character(character_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        return cur.fetchone()


def create_game(name: str, start_time: str, duration_minutes: int, max_seats: int, created_by: int) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO games (name, start_time, duration_minutes, max_seats, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, start_time, duration_minutes, max_seats, created_by, now_iso()),
        )
        conn.commit()
        return cur.lastrowid


def update_game(game_id: int, name: str, start_time: str, duration_minutes: int, max_seats: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE games
            SET name = ?, start_time = ?, duration_minutes = ?, max_seats = ?
            WHERE id = ?
            """,
            (name, start_time, duration_minutes, max_seats, game_id),
        )
        conn.commit()


def set_game_finalized(game_id: int, finalized: bool):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE games SET is_finalized = ? WHERE id = ?",
            (1 if finalized else 0, game_id),
        )
        conn.commit()


def get_game(game_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        return cur.fetchone()


def list_games_between(start_iso: str, end_iso: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM games WHERE start_time BETWEEN ? AND ? ORDER BY start_time",
            (start_iso, end_iso),
        )
        return cur.fetchall()


def list_all_games():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM games ORDER BY start_time")
        return cur.fetchall()


def set_default_attendees(game_id: int, user_ids: Iterable[int]):
    selected = list(dict.fromkeys(user_ids))
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE game_memberships SET is_default = 0 WHERE game_id = ?", (game_id,))
        for user_id in selected:
            cur.execute(
                "SELECT id FROM game_memberships WHERE game_id = ? AND user_id = ?",
                (game_id, user_id),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE game_memberships SET is_default = 1 WHERE game_id = ? AND user_id = ?",
                    (game_id, user_id),
                )
            else:
                cur.execute(
                    "INSERT INTO game_memberships (game_id, user_id, status, is_default) VALUES (?, ?, 'invited', 1)",
                    (game_id, user_id),
                )
        conn.commit()


def add_membership(game_id: int, user_id: int, status: str, is_default: bool = False):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO game_memberships (game_id, user_id, status, is_default) VALUES (?, ?, ?, ?)",
            (game_id, user_id, status, 1 if is_default else 0),
        )
        conn.commit()


def get_membership(game_id: int, user_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM game_memberships WHERE game_id = ? AND user_id = ?",
            (game_id, user_id),
        )
        return cur.fetchone()


def list_memberships(game_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT gm.*, u.display_name, u.email
            FROM game_memberships gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.game_id = ?
            ORDER BY u.display_name
            """,
            (game_id,),
        )
        return cur.fetchall()


def clone_game(game_id: int, creator_id: int) -> Optional[int]:
    game = get_game(game_id)
    if not game:
        return None
    new_game_id = create_game(
        name=f"Copy of {game['name']}",
        start_time=game["start_time"],
        duration_minutes=game["duration_minutes"],
        max_seats=game["max_seats"],
        created_by=creator_id,
    )
    members = list_memberships(game_id)
    set_default_attendees(new_game_id, [m["user_id"] for m in members if m["is_default"]])
    return new_game_id


def list_upcoming_games(limit: int = 20):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM games WHERE start_time >= ? ORDER BY start_time LIMIT ?",
            (datetime.utcnow().isoformat(), limit),
        )
        return cur.fetchall()
