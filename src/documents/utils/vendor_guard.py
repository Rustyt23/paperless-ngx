import re

from dateutil import parser
from rapidfuzz import fuzz

BLOCKED_NAMES_RAW = {
    "private",
    "unknown",
    "n/a",
    "misc",
    "none",
    "oak",
    "oak wantana",
    "gourmet",
    "gourmet pie",
    "gourmet cafe",
    "gourmet pie cafe",
    "gourmet pie & cafe",
}


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    value = value.lower().strip()
    value = re.sub(r"[_\-,:]", " ", value)
    # remove periods not between letters or numbers
    value = re.sub(r"(?<![\w])\.(?![\w])", " ", value)
    value = re.sub(r"(?<=\s)\.(?=\w)|(?<=\w)\.(?=\s)|(?<=\w)\.(?=$)", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


BLOCKLIST = {normalize_name(n) for n in BLOCKED_NAMES_RAW}


def same_normalized(a: str | None, b: str | None) -> bool:
    return normalize_name(a) == normalize_name(b)


def normalize_invoice_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"\d{2}-\d{2}-\d{4}", value):
        return value
    try:
        dt = parser.parse(value, dayfirst=False, yearfirst=False, fuzzy=True)
    except Exception:
        return None
    if not re.search(r"\d{4}", value):
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2})(?!\d)", value)
        if m:
            year = int(m.group(3))
            if year <= 49:
                year += 2000
            else:
                year += 1900
            dt = dt.replace(year=year)
    return dt.strftime("%m-%d-%Y")


def match_correspondent_by_name(name: str, correspondents) -> list:
    norm = normalize_name(name)
    matches = []
    for corr in correspondents:
        corr_norm = normalize_name(corr.name)
        if norm == corr_norm:
            return [corr]
        score = fuzz.ratio(norm, corr_norm) / 100.0
        if score >= 0.86:
            matches.append(corr)
    return matches
