"""Score submission and ranking queries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .db import get_conn


@dataclass
class ScoreEntry:
    rank: int
    user_id: int
    display_name: str
    score: int
    max_combo: int
    accuracy: float
    grade: str
    played_at: str


def submit_score(user_id: int, song_id: str, mode: str, difficulty: str,
                 score: int, max_combo: int, accuracy: float, grade: str,
                 perfects: int, greats: int, goods: int, misses: int) -> int:
    """Persist a play result and return the new row id."""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO scores (user_id, song_id, mode, difficulty, score, max_combo, "
        "accuracy, grade, perfects, greats, goods, misses) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, song_id, mode, difficulty, score, max_combo, accuracy, grade,
         perfects, greats, goods, misses),
    )
    conn.commit()
    return cur.lastrowid


def top_scores(song_id: str, mode: str, difficulty: str,
               limit: int = 20) -> List[ScoreEntry]:
    """Best score per user for a specific chart, ranked descending."""
    rows = get_conn().execute(
        """
        SELECT u.id AS user_id, u.display_name,
               MAX(s.score) AS score, s.max_combo, s.accuracy, s.grade, s.played_at
        FROM scores s
        JOIN users u ON u.id = s.user_id
        WHERE s.song_id = ? AND s.mode = ? AND s.difficulty = ?
        GROUP BY s.user_id
        ORDER BY score DESC, s.accuracy DESC
        LIMIT ?
        """,
        (song_id, mode, difficulty, limit),
    ).fetchall()
    return [
        ScoreEntry(
            rank=i + 1, user_id=r["user_id"], display_name=r["display_name"],
            score=r["score"], max_combo=r["max_combo"], accuracy=r["accuracy"],
            grade=r["grade"], played_at=r["played_at"],
        )
        for i, r in enumerate(rows)
    ]


def global_ranking(limit: int = 50) -> List[ScoreEntry]:
    """Players ranked by total of their best score on each chart played."""
    rows = get_conn().execute(
        """
        SELECT user_id, display_name, SUM(best) AS total, MAX(acc) AS acc
        FROM (
            SELECT s.user_id, u.display_name,
                   MAX(s.score) AS best, AVG(s.accuracy) AS acc
            FROM scores s JOIN users u ON u.id = s.user_id
            GROUP BY s.user_id, s.song_id, s.mode, s.difficulty
        )
        GROUP BY user_id
        ORDER BY total DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [
        ScoreEntry(
            rank=i + 1, user_id=r["user_id"], display_name=r["display_name"],
            score=int(r["total"]), max_combo=0, accuracy=r["acc"] or 0.0,
            grade="", played_at="",
        )
        for i, r in enumerate(rows)
    ]


def personal_best(user_id: int, song_id: str, mode: str,
                  difficulty: str) -> Optional[int]:
    row = get_conn().execute(
        "SELECT MAX(score) AS best FROM scores "
        "WHERE user_id = ? AND song_id = ? AND mode = ? AND difficulty = ?",
        (user_id, song_id, mode, difficulty),
    ).fetchone()
    return row["best"] if row and row["best"] is not None else None
