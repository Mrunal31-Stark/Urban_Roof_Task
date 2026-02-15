from __future__ import annotations

from typing import List

from app.schemas.observation import Observation
from src.ddr_builder import Finding, parse_document


def extract_observations(inspection_text: str, thermal_text: str) -> List[Observation]:
    findings: List[Finding] = parse_document(inspection_text, "Inspection Report") + parse_document(
        thermal_text, "Thermal Report"
    )
    observations: List[Observation] = []
    for finding in findings:
        observations.append(
            Observation(
                source=finding.source,
                area=finding.area,
                issue=finding.issue,
                raw_text=finding.raw_line,
                temperatures_c=finding.temperatures_c,
                confidence=1.0,
            )
        )
    return observations
