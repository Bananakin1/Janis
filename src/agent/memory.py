"""SQLite-backed persistent conversation memory."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class MemoryMessage:
    """One persisted conversation message."""

    role: str
    author: str
    content: str


class MemoryStore:
    """Persistent memory store backed by SQLite."""

    def __init__(self, db_path: Path | str, summary_interval: int = 10) -> None:
        self._db_path = Path(db_path)
        if self._db_path.parent != Path("."):
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._summary_interval = summary_interval
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    covers_up_to INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_conversations_user
                    ON conversations(user_id, id);

                CREATE INDEX IF NOT EXISTS idx_summaries_user
                    ON summaries(user_id, id);
                """
            )

    def add_message(self, user_id: str, user_name: str, role: str, message: str) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO conversations (user_id, user_name, message, role)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, user_name, message, role),
        )
        return int(cursor.lastrowid)

    def add_exchange(self, user_id: str, user_name: str, user_msg: str, assistant_msg: str) -> None:
        """Add a user + assistant message pair in a single transaction."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO conversations (user_id, user_name, message, role) VALUES (?, ?, ?, ?)",
                (user_id, user_name, user_msg, "user"),
            )
            self._conn.execute(
                "INSERT INTO conversations (user_id, user_name, message, role) VALUES (?, ?, ?, ?)",
                (user_id, "Janis", assistant_msg, "assistant"),
            )

    def get_recent_messages(self, user_id: str, limit: int = 4) -> list[MemoryMessage]:
        rows = self._conn.execute(
            """
            SELECT role, user_name, message
            FROM conversations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [
            MemoryMessage(role=row["role"], author=row["user_name"], content=row["message"])
            for row in reversed(rows)
        ]

    def get_latest_summary(self, user_id: str) -> str | None:
        row = self._conn.execute(
            """
            SELECT summary
            FROM summaries
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return str(row["summary"])

    def _get_covers_up_to(self, user_id: str) -> int:
        """Return the conversation id covered by the latest summary, or 0."""
        row = self._conn.execute(
            """
            SELECT covers_up_to
            FROM summaries
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return int(row["covers_up_to"]) if row else 0

    def count_messages_since_summary(self, user_id: str) -> int:
        covers_up_to = self._get_covers_up_to(user_id)
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM conversations
            WHERE user_id = ? AND id > ?
            """,
            (user_id, covers_up_to),
        ).fetchone()
        return int(row["count"])

    def build_transcript_since_summary(self, user_id: str, covers_up_to: int | None = None) -> tuple[str, int]:
        if covers_up_to is None:
            covers_up_to = self._get_covers_up_to(user_id)
        rows = self._conn.execute(
            """
            SELECT id, role, user_name, message
            FROM conversations
            WHERE user_id = ? AND id > ?
            ORDER BY id ASC
            """,
            (user_id, covers_up_to),
        ).fetchall()
        lines = [f"{row['role']} ({row['user_name']}): {row['message']}" for row in rows]
        max_id = max((int(row["id"]) for row in rows), default=covers_up_to)
        return "\n".join(lines), max_id

    def save_summary(self, user_id: str, summary: str, covers_up_to: int) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO summaries (user_id, summary, covers_up_to)
                VALUES (?, ?, ?)
                """,
                (user_id, summary, covers_up_to),
            )

    async def maybe_summarize(self, user_id: str, provider: object | None) -> str | None:
        if provider is None:
            return None
        covers_up_to = self._get_covers_up_to(user_id)
        row = self._conn.execute(
            "SELECT COUNT(*) AS count FROM conversations WHERE user_id = ? AND id > ?",
            (user_id, covers_up_to),
        ).fetchone()
        if int(row["count"]) < self._summary_interval:
            return None
        transcript, max_id = self.build_transcript_since_summary(user_id, covers_up_to)
        if not transcript or max_id == 0:
            return None
        summarize = getattr(provider, "summarize", None)
        if summarize is None:
            return None
        summary = await summarize(transcript)
        if summary:
            self.save_summary(user_id, summary, max_id)
        return summary
