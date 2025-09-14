import re

import dateparser

KEYWORDS = [
    "invoice date",
    "date of service",
    "date",
    "issued",
    "statement date",
]

DATE_PATTERN = re.compile(
    r"""
    (
        \b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|
        \b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|
        \b\d{1,2}\.\d{1,2}\.\d{2,4}\b|
        \b\d{4}\.\d{1,2}\.\d{1,2}\b|
        \b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b|
        \b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _parse_candidate(candidate: str) -> str | None:
    for order in ("DMY", "MDY", "YMD"):
        dt = dateparser.parse(
            candidate,
            settings={
                "PREFER_DAY_OF_MONTH": "first",
                "DATE_ORDER": order,
                "STRICT_PARSING": True,
            },
        )
        if dt:
            return dt.date().isoformat()
    return None


def extract_date(text: str) -> str | None:
    if not text:
        return None

    lines = text.splitlines()
    for idx, line in enumerate(lines):
        lower = line.lower()
        if any(k in lower for k in KEYWORDS):
            start = max(0, idx - 2)
            end = min(len(lines), idx + 3)
            context = "\n".join(lines[start:end])
            for match in DATE_PATTERN.finditer(context):
                iso = _parse_candidate(match.group(0))
                if iso:
                    return iso
    return None
