"""User registration, authentication and management.

Passwords are stored as PBKDF2-HMAC-SHA256 hashes with a per-user random salt;
plaintext passwords are never persisted.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from typing import List, Optional

from .db import get_conn

PBKDF2_ROUNDS = 200_000


@dataclass
class User:
    id: int
    username: str
    display_name: str
    is_admin: bool

    @classmethod
    def from_row(cls, row) -> "User":
        return cls(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            is_admin=bool(row["is_admin"]),
        )


class AuthError(Exception):
    """Raised on registration/login validation failures."""


# --- password hashing ------------------------------------------------------
def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ROUNDS
    )
    return dk.hex()


def _validate_username(username: str) -> str:
    username = username.strip()
    if not (3 <= len(username) <= 20):
        raise AuthError("用户名长度需在 3-20 个字符之间")
    if not all(c.isalnum() or c in "_-" for c in username):
        raise AuthError("用户名只能包含字母、数字、下划线和连字符")
    return username


# --- CRUD ------------------------------------------------------------------
def register(username: str, password: str, display_name: Optional[str] = None,
             is_admin: bool = False) -> User:
    username = _validate_username(username)
    if len(password) < 4:
        raise AuthError("密码至少需要 4 个字符")
    display_name = (display_name or username).strip()[:30]

    conn = get_conn()
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        raise AuthError(f"用户名 '{username}' 已被注册")

    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt)
    cur = conn.execute(
        "INSERT INTO users (username, display_name, password_hash, salt, is_admin) "
        "VALUES (?, ?, ?, ?, ?)",
        (username, display_name, pwd_hash, salt, int(is_admin)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return User.from_row(row)


def authenticate(username: str, password: str) -> User:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    if row is None:
        raise AuthError("用户名或密码错误")
    if _hash_password(password, row["salt"]) != row["password_hash"]:
        raise AuthError("用户名或密码错误")
    return User.from_row(row)


def get_by_id(user_id: int) -> Optional[User]:
    row = get_conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User.from_row(row) if row else None


def get_by_username(username: str) -> Optional[User]:
    row = get_conn().execute(
        "SELECT * FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    return User.from_row(row) if row else None


def list_users() -> List[User]:
    rows = get_conn().execute(
        "SELECT * FROM users ORDER BY username COLLATE NOCASE"
    ).fetchall()
    return [User.from_row(r) for r in rows]


def change_password(user_id: int, new_password: str) -> None:
    if len(new_password) < 4:
        raise AuthError("密码至少需要 4 个字符")
    salt = secrets.token_hex(16)
    get_conn().execute(
        "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
        (_hash_password(new_password, salt), salt, user_id),
    )
    get_conn().commit()


def set_display_name(user_id: int, display_name: str) -> None:
    get_conn().execute(
        "UPDATE users SET display_name = ? WHERE id = ?",
        (display_name.strip()[:30], user_id),
    )
    get_conn().commit()


def delete_user(user_id: int) -> None:
    get_conn().execute("DELETE FROM users WHERE id = ?", (user_id,))
    get_conn().commit()


def user_count() -> int:
    return get_conn().execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
