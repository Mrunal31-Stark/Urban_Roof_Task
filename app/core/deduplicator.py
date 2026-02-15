from __future__ import annotations

from typing import List

from app.schemas.observation import Observation
from app.utils.similarity import jaccard_similarity


def deduplicate_observations(observations: List[Observation], threshold: float = 0.8) -> List[Observation]:
    merged: List[Observation] = []
    for obs in observations:
        matched = False
        for idx, existing in enumerate(merged):
            if existing.area != obs.area or existing.issue != obs.issue:
                continue
            if jaccard_similarity(existing.raw_text, obs.raw_text) >= threshold:
                merged[idx] = Observation(
                    source=f"{existing.source}, {obs.source}",
                    area=existing.area,
                    issue=existing.issue,
                    raw_text=f"{existing.raw_text} | {obs.raw_text}",
                    temperatures_c=existing.temperatures_c + obs.temperatures_c,
                    confidence=min(existing.confidence, obs.confidence),
                )
                matched = True
                break
        if not matched:
            merged.append(obs)
    return merged
