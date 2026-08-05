from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path


class HistoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    voice_id TEXT,
                    voice_name TEXT,
                    input_text TEXT,
                    params_json TEXT,
                    output_path TEXT NOT NULL,
                    duration REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add(
        self,
        kind: str,
        voice_name: str,
        output_path: str,
        duration: float,
        voice_id: str = "",
        input_text: str = "",
        params: dict | None = None,
    ) -> str:
        rec_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history
                (id, kind, voice_id, voice_name, input_text, params_json, output_path, duration, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec_id,
                    kind,
                    voice_id,
                    voice_name,
                    input_text,
                    json.dumps(params or {}, ensure_ascii=False),
                    output_path,
                    float(duration),
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        return rec_id

    def list(self, limit: int = 200) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM history ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["params"] = json.loads(d.pop("params_json"))
            except (json.JSONDecodeError, TypeError):
                d["params"] = {}
            out.append(d)
        return out

    def delete(self, rec_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM history WHERE id = ?", (rec_id,))

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM history")
