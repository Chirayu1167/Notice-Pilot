import os
import sys

import pymupdf
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import database as _database

# Ensure the (possibly pre-existing) test/dev database has the latest schema,
# including Phase-2 return/reconciliation tables.
_database.init_db()

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture_path(name: str) -> str:
    return os.path.join(FIXTURES, name)


def make_pdf(path: str, lines: list[str]) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "\n".join(lines), fontsize=11)
    doc.save(path)
    doc.close()


def make_scanned_pdf(path: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), 0)
    pix.clear_with(255)
    page.insert_image(page.rect, pixmap=pix)
    doc.save(path)
    doc.close()


@pytest.fixture
def drc01b_pdf(tmp_path):
    path = tmp_path / "synthetic_drc01b.pdf"
    make_pdf(
        str(path),
        [
            "SYNTHETIC DEMO DATA - NOT A REAL GST NOTICE.",
            "Form DRC-01B (Reconciliation of Outward Supplies)",
            "Notice No. : DRC-01B/2025-26/SYN/1001",
            "GSTIN: 99SYNTA0000A1Z9",
            "FY 2024-25 difference of Rs. 1,50,000.00",
            "Issue date: 15/01/2025",
            "Due date: 14/02/2025",
            "You are required to submit a reply explaining the difference.",
        ],
    )
    return str(path)


@pytest.fixture
def scanned_pdf(tmp_path):
    path = tmp_path / "scanned.pdf"
    make_scanned_pdf(str(path))
    return str(path)
