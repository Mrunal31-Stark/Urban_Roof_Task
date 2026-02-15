from __future__ import annotations

from typing import List, Tuple


def ocr_notes_for_ingestion(notes: List[str]) -> Tuple[float, List[str]]:
    """Returns confidence multiplier and normalized OCR notes."""
    if not notes:
        return 1.0, []

    normalized = list(notes)
    lowered = " ".join(note.lower() for note in notes)
    if "fallback mode" in lowered or "unavailable" in lowered:
        return 0.6, normalized
    if "ocr" in lowered:
        return 0.8, normalized
    return 0.9, normalized
