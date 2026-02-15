from __future__ import annotations

from typing import Dict, List

from app.db.models import get_report_run, list_report_runs


def get_report(report_id: str) -> Dict[str, object] | None:
    return get_report_run(report_id)


def get_history(limit: int = 20) -> List[Dict[str, object]]:
    return list_report_runs(limit=limit)
