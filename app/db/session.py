from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("output/ddr_audit.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                inspection_hash TEXT NOT NULL,
                thermal_hash TEXT NOT NULL,
                extraction_count INTEGER NOT NULL,
                conflicts_count INTEGER NOT NULL,
                severity TEXT NOT NULL,
                report_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
