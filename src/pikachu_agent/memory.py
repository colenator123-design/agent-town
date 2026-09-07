from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Action, ActionKind, ExecutionResult


class MemoryStore:
    def __init__(self, database: Path, *, retention_days: int = 7):
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self.retention_days = max(1, retention_days)
        self._initialize()
        self.prune()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    request TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    actions_json TEXT NOT NULL,
                    undone INTEGER NOT NULL DEFAULT 0
                )"""
            )

    def prune(self) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM runs WHERE created_at < ?", (cutoff,))
            return cursor.rowcount

    def record(self, request: str, result: ExecutionResult) -> None:
        actions = [
            {"kind": a.kind.value, "source": str(a.source), "destination": str(a.destination)}
            for a in result.completed
        ]
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runs(created_at, request, success, actions_json) VALUES (?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), request, int(result.success), json.dumps(actions)),
            )

    def last_undoable(self) -> tuple[int, list[Action]] | None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, actions_json FROM runs WHERE success = 1 AND undone = 0 "
                "AND actions_json != '[]' ORDER BY id DESC"
            ).fetchall()
        for row in rows:
            payload = json.loads(row[1])
            actions = [
                Action(ActionKind.MOVE_FILE, source=Path(item["destination"]), destination=Path(item["source"]))
                for item in reversed(payload)
                if item.get("kind", ActionKind.MOVE_FILE.value) == ActionKind.MOVE_FILE.value
            ]
            if actions:
                return int(row[0]), actions
        return None

    def mark_undone(self, run_id: int) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE runs SET undone = 1 WHERE id = ?", (run_id,))

    def recent_runs(self, limit: int = 5) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT created_at, request, success, actions_json, undone "
                "FROM runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "created_at": row[0],
                "request": row[1],
                "success": bool(row[2]),
                "action_count": len(json.loads(row[3])),
                "undone": bool(row[4]),
            }
            for row in rows
        ]
