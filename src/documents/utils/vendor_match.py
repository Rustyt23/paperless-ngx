import re
from functools import lru_cache
from pathlib import Path

import yaml
from rapidfuzz import fuzz

VENDOR_MAP_PATH = Path(__file__).resolve().parents[1] / "data" / "vendor_map.yaml"


@lru_cache
def _load_vendor_map() -> dict[str, list[str]]:
    with VENDOR_MAP_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def match_vendor(text: str) -> str | None:
    if not text:
        return None

    vendor_map = _load_vendor_map()
    # Direct regex match over aliases first
    for canonical, aliases in vendor_map.items():
        for alias in aliases:
            if re.search(re.escape(alias), text, re.IGNORECASE):
                return canonical
        if re.search(re.escape(canonical), text, re.IGNORECASE):
            return canonical

    lowered = text.lower()
    best_score = 0
    best_name: str | None = None

    for canonical, aliases in vendor_map.items():
        candidates = [*aliases, canonical]
        for candidate in candidates:
            score = fuzz.partial_ratio(candidate.lower(), lowered)
            if score > best_score:
                best_score = score
                best_name = canonical

    if best_score >= 80:
        return best_name
    return None
