from __future__ import annotations

from typing import Dict, List

from app.core.conflict_engine import detect_conflicts
from app.core.root_cause_engine import derive_root_causes
from app.core.severity_engine import score_severity
from app.schemas.ddr_schema import DDRSchema
from app.schemas.observation import Observation


def build_report(observations: List[Observation], ingestion_notes: List[str], ocr_confidence: float) -> DDRSchema:
    area_map: Dict[str, List[str]] = {}
    issue_summary: List[str] = []
    actions: List[str] = []

    for obs in observations:
        area_map.setdefault(obs.area, []).append(f"[{obs.source}] {obs.raw_text}")
        if obs.issue != "observation":
            issue_summary.append(obs.raw_text)
        if any(k in obs.raw_text.lower() for k in ["recommend", "repair", "replace", "seal", "monitor", "inspect"]):
            actions.append(obs.raw_text)

    conflicts = detect_conflicts(observations)
    severity_level, severity_reason = score_severity(observations)
    root_causes = derive_root_causes(observations)

    missing: List[str] = []
    if not any(obs.temperatures_c for obs in observations):
        missing.append("Temperature readings: Not Available")
    if not root_causes or root_causes == ["Not Available"]:
        missing.append("Probable root cause statements: Not Available")
    if not actions:
        missing.append("Recommended actions in source docs: Not Available")
    if not observations:
        missing.append("Area-level observations: Not Available")

    confidence_scores = {
        "extraction": round(ocr_confidence, 2),
        "completeness": round(max(0.2, 1 - (len(missing) * 0.2)), 2),
        "consistency": round(max(0.2, 1 - (len(conflicts) * 0.15)), 2),
    }

    return DDRSchema(
        property_issue_summary=list(dict.fromkeys(issue_summary)) or ["Not Available"],
        area_wise_observations={k: list(dict.fromkeys(v)) for k, v in sorted(area_map.items())} or {"General": ["Not Available"]},
        probable_root_cause=root_causes,
        severity_assessment={"level": severity_level, "reasoning": severity_reason},
        recommended_actions=list(dict.fromkeys(actions)) or ["Not Available"],
        additional_notes=list(dict.fromkeys(ingestion_notes + conflicts)) or ["Not Available"],
        missing_or_unclear_information=list(dict.fromkeys(missing)) or ["Not Available"],
        conflicts=conflicts or ["Not Available"],
        confidence_scores=confidence_scores,
    )
