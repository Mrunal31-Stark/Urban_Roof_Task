from __future__ import annotations

import re
from typing import Dict, List

from app.schemas.observation import Observation


def detect_conflicts(observations: List[Observation]) -> List[str]:
    by_area: Dict[str, List[Observation]] = {}
    for obs in observations:
        by_area.setdefault(obs.area, []).append(obs)

    conflicts: List[str] = []
    for area, items in by_area.items():
        temps = [t for item in items for t in item.temperatures_c]
        if len(temps) >= 2 and max(temps) - min(temps) >= 15:
            conflicts.append(f"Temperature spread conflict in {area}: {min(temps):.1f}°C to {max(temps):.1f}°C.")

        has_moisture = any(any(w in item.raw_text.lower() for w in ["moisture", "damp", "leak"]) for item in items)
        has_normal_temp = any(0 <= t <= 40 for t in temps)
        if has_moisture and has_normal_temp:
            conflicts.append(f"Moisture detected in {area} while thermal reading includes normal range.")

        inspection_no_damage = any(
            item.source.startswith("Inspection")
            and re.search(r"\bno\b.{0,20}\b(damage|issue|overheat|crack)\b", item.raw_text.lower())
            for item in items
        )
        thermal_hotspot = any(item.source.startswith("Thermal") and any(t >= 75 for t in item.temperatures_c) for item in items)
        if inspection_no_damage and thermal_hotspot:
            conflicts.append(f"Conflict Identified in {area}: inspection states no damage but thermal hotspot >= 75°C detected.")

    return list(dict.fromkeys(conflicts))
