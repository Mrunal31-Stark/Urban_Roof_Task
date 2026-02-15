from __future__ import annotations

from typing import List

from app.schemas.observation import Observation


def validate_observations(observations: List[Observation]) -> List[Observation]:
    valid: List[Observation] = []
    for obs in observations:
        if not obs.raw_text.strip():
            continue
        if len(obs.raw_text.strip()) < 6:
            continue
        valid.append(obs)
    return valid
