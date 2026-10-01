"""Shared normalization helpers for GST return parsers (deterministic, no LLM)."""

import math
import re
from datetime import datetime

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", re.I)

DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%m/%d/%Y",
)


def norm_header(name: object) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    s = re.sub(r"_+", "_", s)
    return s


def find_column(columns: list[str], aliases: set[str]) -> str | None:
    for col in columns:
        if norm_header(col) in aliases:
            return col
    return None


def parse_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return round(float(value), 2)
    s = str(value).strip()
    if s == "" or s.lower() in {"nan", "none", "null", "nil", "-", "--", "na", "n/a"}:
        return None
    # Strip currency symbols / spaces; keep digits, minus, dot, comma, parentheses negatives
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    s = s.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace("INR", "")
    s = s.replace(" ", "").replace("'", "")
    # Handle Indian grouping commas
    s = s.replace(",", "")
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "-", ".", "-."):
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    if negative:
        num = -abs(num)
    if math.isnan(num) or math.isinf(num):
        return None
    return round(num, 2)


def parse_date(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "strftime") and not isinstance(value, str):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            return None
    s = str(value).strip()
    if s == "" or s.lower() in {"nan", "none", "null", "na", "n/a", "-"}:
        return None
    # Excel serial dates sometimes arrive as float strings
    if re.fullmatch(r"\d{5}(\.\d+)?", s):
        try:
            serial = float(s)
            base = datetime(1899, 12, 30)
            from datetime import timedelta

            dt = base + timedelta(days=int(serial))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Last resort: pandas-style YYYY-MM-DD prefix
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def parse_gstin(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip().upper().replace(" ", "")
    if s == "" or s.lower() in {"nan", "none", "null", "na"}:
        return None
    if GSTIN_RE.match(s):
        return s
    return None


def parse_invoice_no(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    s = str(value).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return None
    # Keep invoice numbers verbatim (upper-cased, single-spaced)
    s = re.sub(r"\s+", " ", s).strip().upper()
    return s or None


def normalize_period(value: object) -> str | None:
    """Normalize a tax period to YYYY-MM. Returns None if not parseable."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    # YYYY-MM / YYYYMM
    m = re.fullmatch(r"(\d{4})[-/]?((0[1-9]|1[0-2]))", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # MM/YYYY or MM-YYYY
    m = re.fullmatch(r"(0[1-9]|1[0-2])[/\-.](\d{4})", s)
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    # Mon-YYYY / Month YYYY
    months = {
        "jan": "01", "january": "01", "feb": "02", "february": "02",
        "mar": "03", "march": "03", "apr": "04", "april": "04",
        "may": "05", "jun": "06", "june": "06", "jul": "07", "july": "07",
        "aug": "08", "august": "08", "sep": "09", "sept": "09", "september": "09",
        "oct": "10", "october": "10", "nov": "11", "november": "11",
        "dec": "12", "december": "12",
    }
    m = re.fullmatch(r"([A-Za-z]+)[\s\-/.,]*(\d{4})", s)
    if m and m.group(1).lower() in months:
        return f"{m.group(2)}-{months[m.group(1).lower()]}"
    # FY formats are NOT monthly periods — leave to caller (returns UNKNOWN)
    return None


def compare_period(notice_period: str | None, return_period: str | None) -> str:
    """Return MATCH | MISMATCH | UNKNOWN comparing notice vs return period."""
    if not notice_period or not return_period:
        return "UNKNOWN"
    np_norm = normalize_period(notice_period)
    rp_norm = normalize_period(return_period)
    if np_norm and rp_norm:
        return "MATCH" if np_norm == rp_norm else "MISMATCH"
    # FY-style notice periods (e.g. 2024-25) can't be exactly matched to a month
    if notice_period.strip() == return_period.strip():
        return "MATCH"
    return "UNKNOWN"
