from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Observation:
    source: str
    area: str
    issue: str
    raw_text: str
    temperatures_c: List[float] = field(default_factory=list)
    confidence: float = 1.0
