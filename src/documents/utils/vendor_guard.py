import re

from dateutil import parser
from .vendor_match import _load_vendor_map

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
    value = re.sub(r"[_.\-,:]+", " ", value)
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
    vendor_map = _load_vendor_map()
    mapping: dict[str, list] = {}
    for corr in correspondents:
        names = [corr.name]
        if corr.name in vendor_map:
            names.extend(vendor_map[corr.name])
        for n in names:
            key = normalize_name(n)
            mapping.setdefault(key, []).append(corr)
    return mapping.get(norm, [])
