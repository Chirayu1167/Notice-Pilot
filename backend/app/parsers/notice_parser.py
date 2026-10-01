import re
from datetime import datetime

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z][Z][0-9A-Z]\b")

NOTICE_NUMBER_RES = [
    re.compile(r"Notice\s*(?:No|Number|#)\s*[.\s:\-]*\s*([A-Z0-9][A-Z0-9/\-]{3,})", re.I),
    re.compile(r"Reference\s*(?:No|Number)\s*[.\s:\-]*\s*([A-Z0-9][A-Z0-9/\-]{3,})", re.I),
    re.compile(r"Memo\s*(?:No|Number)\s*[.\s:\-]*\s*([A-Z0-9][A-Z0-9/\-]{3,})", re.I),
    re.compile(r"\bDIN\s*[.\s:\-]*\s*(\d{4,20})", re.I),
]

FY_RE = re.compile(r"\bFY\s*(\d{4})\s*[-–]\s*(\d{2,4})\b", re.I)
MONTH_NAME_RE = re.compile(
    r"(?:month\s+of\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s*,?\s*(\d{4})",
    re.I,
)
ISO_MONTH_RE = re.compile(r"\b(\d{4})-(0[1-9]|1[0-2])\b")
MY_RE = re.compile(r"\b(0[1-9]|1[0-2])[\/\-.](\d{4})\b")
QUARTER_RE = re.compile(r"\bQ([1-4])\s*(?:FY)?\s*(\d{4})\s*[-–]?\s*(\d{2,4})?", re.I)

DATE_NUMERIC_RES = [
    (re.compile(r"\b(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})\b"), "ymd"),
]
DATE_NAME_RES = [
    (re.compile(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s*,?\s*(\d{4})\b", re.I), "dmy"),
    (re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s*,?\s*(\d{4})\b", re.I), "mdy"),
]

ISSUE_DATE_RE = re.compile(
    r"(?:issue\s+date|date\s+of\s+issue|dated)\s*[.:-]?\s*", re.I
)
DUE_DATE_RE = re.compile(
    r"(?:due\s+date|reply\s+by|respond\s+by|on\s+or\s+before|within\s+\d+\s+days)\s*[.:-]?\s*",
    re.I,
)

AMOUNT_RE = re.compile(r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
AMOUNT_KEYWORD_RE = re.compile(r"difference|demand|tax|amount|penalty|interest", re.I)

ACTION_KEYWORDS = [
    "show cause", "submit", "furnish", "reply", "explain", "provide",
    "clarif", "respond", "produce", "attend",
]


def parse_notice_type(text: str) -> str:
    upper = text.upper()
    if "DRC-01B" in upper or "DRC01B" in upper:
        return "DRC-01B"
    if "DRC-01C" in upper or "DRC01C" in upper:
        return "DRC-01C"
    return "UNKNOWN"


def parse_notice_number(text: str) -> str | None:
    for pattern in NOTICE_NUMBER_RES:
        m = pattern.search(text)
        if m:
            value = m.group(1).strip().upper().rstrip(".,;")
            if any(ch.isdigit() for ch in value):
                return value
    return None


def parse_gstin(text: str) -> str | None:
    m = GSTIN_RE.search(text)
    return m.group(0) if m else None


def _normalize_fy(y1: str, y2: str) -> str:
    if len(y2) == 4:
        y2 = y2[2:]
    return f"{y1}-{y2}"


def parse_tax_period(text: str) -> str | None:
    m = FY_RE.search(text)
    if m:
        return _normalize_fy(m.group(1), m.group(2))
    m = MONTH_NAME_RE.search(text)
    if m:
        return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"
    m = QUARTER_RE.search(text)
    if m:
        y1 = m.group(2)
        y2 = m.group(3) or str(int(y1) + 1)
        return f"{y1}-{y2[2:] if len(y2) == 4 else y2}"
    m = ISO_MONTH_RE.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = MY_RE.search(text)
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    return None


def _valid_date(day: int, month: int, year: int) -> bool:
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def _to_iso(day: int, month: int, year: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def _match_date(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    a, b, c = m.group(1), m.group(2), m.group(3)
    if b.lower() in MONTHS:
        day, month, year = int(a), MONTHS[b.lower()], int(c)
    elif a.lower() in MONTHS:
        month, day, year = MONTHS[a.lower()], int(b), int(c)
    elif len(a) == 4:
        year, month, day = int(a), int(b), int(c)
    else:
        day, month, year = int(a), int(b), int(c)
    if not _valid_date(day, month, year):
        return None
    return _to_iso(day, month, year)


def _find_dates(text: str) -> list[str]:
    dates = []
    for pattern, _ in DATE_NUMERIC_RES:
        for m in pattern.finditer(text):
            a, b, c = m.group(1), m.group(2), m.group(3)
            if len(a) == 4:
                year, month, day = int(a), int(b), int(c)
            else:
                day, month, year = int(a), int(b), int(c)
            if _valid_date(day, month, year):
                dates.append((_to_iso(day, month, year), m.start()))
    for pattern, _ in DATE_NAME_RES:
        for m in pattern.finditer(text):
            iso = _match_date(pattern, text[m.start():m.end()])
            if iso:
                dates.append((iso, m.start()))
    dates.sort(key=lambda item: item[1])
    return [d for d, _ in dates]


def parse_dates(text: str) -> tuple[str | None, str | None]:
    issue = None
    m = ISSUE_DATE_RE.search(text)
    if m:
        window = text[m.end():m.end() + 60]
        issue = _match_date_numeric(window) or _match_date_name(window)
    due = None
    m = DUE_DATE_RE.search(text)
    if m:
        window = text[m.end():m.end() + 60]
        due = _match_date_numeric(window) or _match_date_name(window)
    if issue is None or due is None:
        all_dates = _find_dates(text)
        if issue is None and all_dates:
            issue = all_dates[0]
        if due is None and all_dates:
            due = all_dates[-1]
    return issue, due


def _match_date_numeric(window: str) -> str | None:
    for pattern, _ in DATE_NUMERIC_RES:
        m = pattern.search(window)
        if not m:
            continue
        a, b, c = m.group(1), m.group(2), m.group(3)
        if len(a) == 4:
            year, month, day = int(a), int(b), int(c)
        else:
            day, month, year = int(a), int(b), int(c)
        if _valid_date(day, month, year):
            return _to_iso(day, month, year)
    return None


def _match_date_name(window: str) -> str | None:
    for pattern in DATE_NAME_RES:
        m = pattern.search(window)
        if m:
            iso = _match_date(pattern, window[m.start():m.end()])
            if iso:
                return iso
    return None


def _parse_amount(raw: str) -> float:
    return float(raw.replace(",", ""))


def parse_difference_amount(text: str) -> float | None:
    for line in text.splitlines():
        if "difference" in line.lower():
            m = AMOUNT_RE.search(line)
            if m:
                try:
                    return _parse_amount(m.group(1))
                except ValueError:
                    continue
    for m in AMOUNT_RE.finditer(text):
        window = text[max(0, m.start() - 120):m.end() + 120]
        if AMOUNT_KEYWORD_RE.search(window):
            try:
                return _parse_amount(m.group(1))
            except ValueError:
                continue
    m = AMOUNT_RE.search(text)
    if m:
        try:
            return _parse_amount(m.group(1))
        except ValueError:
            return None
    return None


def parse_requested_action(text: str) -> str | None:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        stripped = sentence.strip()
        if not stripped or len(stripped) > 400:
            continue
        lower = stripped.lower()
        if any(keyword in lower for keyword in ACTION_KEYWORDS):
            return stripped[:300]
    return None


def parse_notice(text: str) -> dict:
    issue_date, due_date = parse_dates(text)
    return {
        "notice_number": parse_notice_number(text),
        "notice_type": parse_notice_type(text),
        "gstin": parse_gstin(text),
        "tax_period": parse_tax_period(text),
        "issue_date": issue_date,
        "due_date": due_date,
        "difference_amount": parse_difference_amount(text),
        "requested_action": parse_requested_action(text),
    }
