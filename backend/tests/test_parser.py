from app.parsers import notice_parser, validation
from tests.conftest import fixture_path


def load(name):
    with open(fixture_path(name), encoding="utf-8") as f:
        return f.read()


def test_parse_notice_number():
    text = load("synthetic_drc01b.txt")
    assert notice_parser.parse_notice_number(text) == "DRC-01B/2025-26/SYN/1001"


def test_parse_notice_type_drc01b():
    assert notice_parser.parse_notice_type(load("synthetic_drc01b.txt")) == "DRC-01B"


def test_parse_notice_type_drc01c():
    assert notice_parser.parse_notice_type(load("synthetic_drc01c.txt")) == "DRC-01C"


def test_parse_notice_type_unknown():
    assert notice_parser.parse_notice_type(load("unrelated.txt")) == "UNKNOWN"


def test_parse_gstin():
    text = load("synthetic_drc01b.txt")
    assert notice_parser.parse_gstin(text) == "99SYNTA0000A1Z9"


def test_parse_tax_period_fy():
    text = load("synthetic_drc01b.txt")
    assert notice_parser.parse_tax_period(text) == "2024-25"


def test_parse_tax_period_month():
    text = load("synthetic_drc01c.txt")
    assert notice_parser.parse_tax_period(text) == "2024-04"


def test_parse_issue_date():
    text = load("synthetic_drc01b.txt")
    issue, _ = notice_parser.parse_dates(text)
    assert issue == "2025-01-15"


def test_parse_due_date():
    text = load("synthetic_drc01b.txt")
    _, due = notice_parser.parse_dates(text)
    assert due == "2025-02-14"


def test_parse_difference_amount():
    text = load("synthetic_drc01b.txt")
    assert notice_parser.parse_difference_amount(text) == 150000.0


def test_parse_requested_action():
    text = load("synthetic_drc01b.txt")
    action = notice_parser.parse_requested_action(text)
    assert action is not None
    assert "submit a reply" in action.lower()


def test_missing_fields_are_null():
    text = "GST notice regarding your filing. Please respond."
    parsed = notice_parser.parse_notice(text)
    assert parsed["notice_number"] is None
    assert parsed["gstin"] is None
    assert parsed["tax_period"] is None
    assert parsed["difference_amount"] is None


def test_validate_valid():
    text = load("synthetic_drc01b.txt")
    parsed = notice_parser.parse_notice(text)
    assert validation.validate(parsed, text) == "VALID"


def test_validate_partial():
    text = (
        "GST show cause notice to GSTIN 99SYNTA0000A1Z9. "
        "You are required to explain the discrepancy."
    )
    parsed = notice_parser.parse_notice(text)
    assert validation.validate(parsed, text) == "PARTIAL"


def test_validate_unsupported():
    text = load("unrelated.txt")
    parsed = notice_parser.parse_notice(text)
    assert validation.validate(parsed, text) == "UNSUPPORTED"
