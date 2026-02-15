from __future__ import annotations

from typing import List, Tuple

from app.schemas.observation import Observation


def score_severity(observations: List[Observation]) -> Tuple[str, str]:
    text = " ".join(obs.raw_text.lower() for obs in observations)
    max_temp = max((t for obs in observations for t in obs.temperatures_c), default=None)

    if max_temp is not None and max_temp >= 75:
        return "High", f"Elevated temperature ({max_temp:.1f}°C) exceeds risk threshold (>=75°C)."
    if "crack" in text and any(w in text for w in ["moisture", "damp", "leak"]):
        return "Medium", "Crack and moisture appear together, indicating potential structural deterioration."
    if any(w in text for w in ["moisture", "damp", "leak", "hotspot", "overheat"]):
        return "Medium", "Thermal/moisture anomalies are present in source documents."
    return "Low", "Only limited low-risk observations are explicitly present."
