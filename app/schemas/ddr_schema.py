from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass
class DDRSchema:
    property_issue_summary: List[str]
    area_wise_observations: Dict[str, List[str]]
    probable_root_cause: List[str]
    severity_assessment: Dict[str, str]
    recommended_actions: List[str]
    additional_notes: List[str]
    missing_or_unclear_information: List[str]
    conflicts: List[str]
    confidence_scores: Dict[str, float]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
