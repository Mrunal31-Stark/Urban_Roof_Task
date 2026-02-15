from __future__ import annotations

import re


def jaccard_similarity(a: str, b: str) -> float:
    a_words = {w for w in re.findall(r"[a-z0-9]+", a.lower()) if len(w) > 2}
    b_words = {w for w in re.findall(r"[a-z0-9]+", b.lower()) if len(w) > 2}
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / len(a_words | b_words)
