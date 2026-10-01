"""Return file ingestion: validation, deterministic source detection, parsing.

Accepts CSV and XLSX only. Detection uses sheet names + column headers +
structural markers — never an LLM. Uncertain files -> source UNKNOWN.
"""

import io
import os
import re

import pandas as pd

from app.parsers import normalize as n
from app.parsers.gstr1 import normalize as normalize_gstr1
from app.parsers.gstr2b import normalize as normalize_gstr2b
from app.parsers.gstr3b import normalize as normalize_gstr3b

KNOWN_SOURCES = ("GSTR-1", "GSTR-3B", "GSTR-2B")

# Deterministic marker sets (matched against normalized headers + sheet names)
GSTR1_MARKERS = {
    "gstin_uin_of_recipient", "recipient_gstin", "place_of_supply",
    "invoice_number", "invoice_date", "taxable_value", "b2b", "b2cl", "b2cs",
    "outward", "cdnr", "cdnur", "nil_rated", "hsn", "doc_issue",
}
GSTR3B_MARKERS = {
    "nature_of_supplies", "total_taxable_value", "eligible_itc", "net_itc",
    "exempt_supplies", "non_gst_supplies", "table_3_1", "3_1_a", "outward_taxable",
    "reverse_charge", "payment_of_tax", "values_exempt",
}
GSTR2B_MARKERS = {
    "itc_available", "itc_availability", "isd", "bill_of_entry", "gstr_2b",
    "supplier_gstin", "inward", "auto_drafted", "itc_reversal", "itc_claimed",
}

HEADER_HINTS = {
    "GSTR-1": ("gstr-1", "gstr1", "b2b", "outward supplies", "iff"),
    "GSTR-3B": ("gstr-3b", "gstr3b", "table 3.1", "eligible itc", "table 4", "payment of tax"),
    "GSTR-2B": ("gstr-2b", "gstr2b", "itc available", "auto-drafted", "bill of entry"),
}


class ReturnFileError(Exception):
    def __init__(self, message: str, code: str = "INVALID_RETURN_FILE"):
        super().__init__(message)
        self.code = code


def validate_extension(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in (".csv", ".xlsx"):
        raise ReturnFileError(
            f"Unsupported file type '{ext or '(none)'}'. Only CSV and XLSX return files are accepted.",
            code="UNSUPPORTED_EXTENSION",
        )
    return ext


def validate_magic(filename: str, content: bytes) -> None:
    ext = os.path.splitext(filename or "")[1].lower()
    if len(content) == 0:
        raise ReturnFileError("Return file is empty.", code="EMPTY_FILE")
    if ext == ".xlsx":
        if not content.startswith(b"PK\x03\x04"):
            raise ReturnFileError(
                "Invalid XLSX file (missing ZIP magic bytes).", code="INVALID_MAGIC"
            )
    else:
        if content.startswith((b"PK\x03\x04", b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"%PDF")):
            raise ReturnFileError(
                "Invalid CSV file (binary content detected).", code="INVALID_MAGIC"
            )
        sample = content[:8192]
        if b"\x00" in sample:
            raise ReturnFileError("Invalid CSV file (binary content detected).", code="INVALID_MAGIC")


def _read_csv(content: bytes) -> tuple[pd.DataFrame, list[str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except (UnicodeDecodeError, ValueError):
            continue
    else:
        raise ReturnFileError("Could not decode CSV file.", code="UNREADABLE")
    if not text.strip():
        raise ReturnFileError("Return file is empty.", code="EMPTY_FILE")
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=True)
    except Exception as e:
        raise ReturnFileError(f"Could not parse CSV file: {e}", code="UNREADABLE")
    df.columns = [str(c).strip() for c in df.columns]
    # Drop fully-empty rows/cols (portal exports often have them)
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if df.empty:
        raise ReturnFileError("Return file contains no data rows.", code="EMPTY_FILE")
    _dedupe_columns(df)
    return df, ["sheet1"]


def _read_xlsx(content: bytes) -> tuple[dict[str, pd.DataFrame], list[str]]:
    try:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=str, engine="openpyxl")
    except Exception as e:
        raise ReturnFileError(f"Could not parse XLSX file: {e}", code="UNREADABLE")
    cleaned: dict[str, pd.DataFrame] = {}
    for name, df in sheets.items():
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
        if df.empty:
            continue
        _dedupe_columns(df)
        cleaned[str(name)] = df
    if not cleaned:
        raise ReturnFileError("Return file contains no data rows.", code="EMPTY_FILE")
    return cleaned, list(cleaned.keys())


def _dedupe_columns(df: pd.DataFrame) -> None:
    seen: dict[str, int] = {}
    new_cols: list[str] = []
    for col in df.columns:
        key = str(col)
        if key in seen:
            seen[key] += 1
            new_cols.append(f"{key}__{seen[key]}")
        else:
            seen[key] = 0
            new_cols.append(key)
    df.columns = new_cols


def detect_source(
    headers: list[str],
    sheet_names: list[str] | None = None,
    filename: str = "",
    explicit_hint: str | None = None,
) -> tuple[str, dict]:
    """Deterministic detection. Returns (source, scores). UNKNOWN when uncertain."""
    if explicit_hint and explicit_hint.upper() in ("GSTR-1", "GSTR-3B", "GSTR-2B", "GSTR1", "GSTR3B", "GSTR2B", "UNKNOWN"):
        h = explicit_hint.upper().replace("GSTR1", "GSTR-1").replace("GSTR3B", "GSTR-3B").replace("GSTR2B", "GSTR-2B")
        if h in KNOWN_SOURCES:
            return h, {"hint": h}
        if h == "UNKNOWN":
            return "UNKNOWN", {"hint": "UNKNOWN"}

    norm_headers = {n.norm_header(h) for h in headers}
    blob = " ".join([str(h).lower() for h in headers])
    sheet_blob = " ".join([(s or "").lower() for s in (sheet_names or [])])
    fname_blob = (filename or "").lower()

    def header_text_score(hints: tuple[str, ...]) -> int:
        return sum(1 for hint in hints if hint in blob or hint in sheet_blob or hint in fname_blob)

    scores = {
        "GSTR-1": len(norm_headers & GSTR1_MARKERS) * 2 + header_text_score(HEADER_HINTS["GSTR-1"]),
        "GSTR-3B": len(norm_headers & GSTR3B_MARKERS) * 2 + header_text_score(HEADER_HINTS["GSTR-3B"]),
        "GSTR-2B": len(norm_headers & GSTR2B_MARKERS) * 2 + header_text_score(HEADER_HINTS["GSTR-2B"]),
    }

    # Structural disambiguation: invoice-level recipient+taxable+invoice markers
    has_recipient = bool(norm_headers & {"gstin_uin_of_recipient", "recipient_gstin"})
    has_supplier = bool(norm_headers & {"supplier_gstin", "gstin_of_supplier"})
    has_itc_avail = bool(norm_headers & {"itc_available", "available_itc", "itc_availability"})
    has_nature = bool(norm_headers & {"nature_of_supplies", "nature_of_supply"})
    if has_nature:
        scores["GSTR-3B"] += 3
    if has_itc_avail:
        scores["GSTR-2B"] += 3
    if has_recipient and not has_supplier:
        scores["GSTR-1"] += 2
    if has_supplier and not has_recipient:
        scores["GSTR-2B"] += 2

    best = max(scores, key=lambda k: scores[k])
    ordered = sorted(scores.values(), reverse=True)
    # Require a clear, non-trivial signal; never silently classify arbitrary CSVs
    if scores[best] < 3:
        return "UNKNOWN", scores
    if len(ordered) > 1 and ordered[0] - ordered[1] < 1:
        return "UNKNOWN", scores
    return best, scores


def _extract_period(
    df: pd.DataFrame,
    sheet_names: list[str],
    explicit: str | None,
    filename: str = "",
) -> str | None:
    if explicit:
        norm = n.normalize_period(explicit)
        if norm:
            return norm
        # Accept FY verbatim? No — monthly engine needs YYYY-MM; keep raw explicit
        # only if it looks like a period token, else None.
        if re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", explicit.strip()):
            return explicit.strip()[:7]
        return None
    # Look for a period-like column first
    for col in df.columns:
        key = n.norm_header(col)
        if key in {"tax_period", "return_period", "period", "month", "fp", "financial_period"}:
            for val in df[col].dropna().tolist()[:20]:
                norm = n.normalize_period(val)
                if norm:
                    return norm
    # Sheet-name hint e.g. "2024-04" / "Apr-2024"
    for sheet in sheet_names:
        m = re.search(r"(20\d{2}[-_](0[1-9]|1[0-2]))", sheet or "")
        if m:
            return m.group(1).replace("_", "-")
        norm = n.normalize_period(sheet)
        if norm:
            return norm
    # Filename hint e.g. "gstr1_matched_2024-04.csv" / "GSTR-1_Apr2024.xlsx"
    m = re.search(r"(20\d{2}[-_](0[1-9]|1[0-2]))", filename or "")
    if m:
        return m.group(1).replace("_", "-")
    m = re.search(r"((0[1-9]|1[0-2])[-_](20\d{2}))", filename or "")
    if m:
        return f"{m.group(3)}-{m.group(2)}"
    m = re.search(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[-_ ]?(20\d{2})",
        (filename or "").lower(),
    )
    if m:
        norm = n.normalize_period(f"{m.group(1)}-{m.group(2)}")
        if norm:
            return norm
    return None


NORMALIZERS = {
    "GSTR-1": normalize_gstr1,
    "GSTR-3B": normalize_gstr3b,
    "GSTR-2B": normalize_gstr2b,
}


def parse_return_file(
    filename: str,
    content: bytes,
    source_hint: str | None = None,
    period: str | None = None,
    max_rows: int = 50000,
) -> dict:
    ext = validate_extension(filename)
    validate_magic(filename, content)

    if ext == ".csv":
        df, sheet_names = _read_csv(content)
        frames = {"sheet1": df}
    else:
        frames = _read_xlsx_frames(content)
        sheet_names = list(frames.keys())

    # Detection uses the largest sheet's headers
    main_name = max(frames.keys(), key=lambda k: len(frames[k]))
    main_df = frames[main_name]
    headers = [str(c) for c in main_df.columns]
    source, scores = detect_source(headers, sheet_names, filename, source_hint)
    if source == "UNKNOWN" and source_hint and source_hint.upper() not in ("", "UNKNOWN", "AUTO"):
        # Explicit user identification wins (user asked to identify rather than guess)
        candidate = source_hint.upper().replace("GSTR1", "GSTR-1").replace("GSTR3B", "GSTR-3B").replace("GSTR2B", "GSTR-2B")
        if candidate in KNOWN_SOURCES:
            source = candidate

    if source == "UNKNOWN":
        raise ReturnFileError(
            "Could not identify return type (GSTR-1 / GSTR-3B / GSTR-2B). "
            "Please select the return type explicitly.",
            code="UNKNOWN_SOURCE",
        )

    detected_period = _extract_period(main_df, sheet_names, period, filename)
    normalizer = NORMALIZERS[source]
    all_rows = []
    for sheet, df in sorted(frames.items()):
        # Skip sheets that look like cover/index pages
        if len(df.columns) < 2:
            continue
        try:
            all_rows.extend(normalizer(df, detected_period, source))
        except Exception:
            continue
    if len(all_rows) > max_rows:
        raise ReturnFileError(
            f"Return file has too many rows ({len(all_rows)}). Maximum is {max_rows}.",
            code="TOO_MANY_ROWS",
        )
    if not all_rows:
        raise ReturnFileError("Return file contains no usable data rows.", code="EMPTY_FILE")

    return {
        "source": source,
        "period": detected_period,
        "rows": all_rows,
        "sheet_names": sheet_names,
        "scores": scores,
    }


def _read_xlsx_frames(content: bytes) -> dict[str, pd.DataFrame]:
    frames, _ = _read_xlsx(content)
    return frames
