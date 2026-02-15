from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List

from app.db.session import get_connection


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def store_report_run(
    report_id: str,
    inspection_text: str,
    thermal_text: str,
    extraction_count: int,
    conflicts_count: int,
    severity: str,
    report_payload: Dict[str, object],
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO report_runs(id, created_at, inspection_hash, thermal_hash, extraction_count, conflicts_count, severity, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                datetime.now(timezone.utc).isoformat(),
                sha256_text(inspection_text),
                sha256_text(thermal_text),
                extraction_count,
                conflicts_count,
                severity,
                json.dumps(report_payload),
            ),
        )
        conn.commit()


def list_report_runs(limit: int = 20) -> List[Dict[str, object]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, created_at, extraction_count, conflicts_count, severity FROM report_runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_report_run(report_id: str) -> Dict[str, object] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM report_runs WHERE id = ?", (report_id,)).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["report_json"] = json.loads(out["report_json"])
    return out
