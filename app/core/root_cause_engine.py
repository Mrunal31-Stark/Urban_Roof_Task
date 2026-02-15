from __future__ import annotations

from typing import List

from app.schemas.observation import Observation

CAUSE_HINTS = ["likely due to", "possible cause", "caused by", "because", "root cause", "source"]


def derive_root_causes(observations: List[Observation]) -> List[str]:
    causes = [obs.raw_text for obs in observations if any(h in obs.raw_text.lower() for h in CAUSE_HINTS)]
    if not causes:
        return ["Not Available"]
    return list(dict.fromkeys(causes))
