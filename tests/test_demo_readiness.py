from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from invoice_assistant.parser import parse_invoice_text
from invoice_assistant.presentation import result_summary
from invoice_assistant.validation import validate_invoice
from invoice_assistant.documents import DocumentError

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("header,row", [
    ("Description | Unit price | Qty | Amount", "Notebook | ₹10.50 | 2 | ₹21.00"),
    ("No. | Item | Quantity | Rate | Total", "1 | Notebook | 2 | ₹10.50 | ₹21.00"),
    ("Product\tQty\tUnit cost\tLine amount", "Notebook\t2\t₹10.50\t₹21.00"),
    ("Description  Price  Quantity  Amount", "Notebook  ₹10.50  2  ₹21.00"),
])
def test_explicit_table_headers_allow_reordered_columns(header, row):
    invoice = parse_invoice_text(f"Vendor: Example\nInvoice No: DEMO\nDate: 18 November 2026\nCurrency: INR\n{header}\n{row}\nSubtotal:21\nTax:0\nShipping:0\nDiscount:0\nBalance due:21")
    assert invoice.invoice_date == "2026-11-18"
    assert len(invoice.line_items) == 1
    assert invoice.line_items[0].quantity == "2"
    report = validate_invoice(invoice)
    assert report.difference == "0.00" and not report.error_count


def test_skipped_unreadable_row_cannot_be_reported_as_a_clean_check():
    invoice = parse_invoice_text("Currency: INR\nDescription | Qty | Rate | Amount\nNotebook | 2 | 10 | 20\nPen | unreadable | 5 | 10\nTotal:30")
    report = validate_invoice(invoice)
    assert invoice.reading_warnings
    assert report.arithmetic_status == "needs_details"
    assert result_summary(report)[1] == "Please check the item details we read"


def test_metadata_notes_are_not_calculation_failures():
    invoice = parse_invoice_text("Notebook | 2 | $10 | $20\nTotal: $20")
    report = validate_invoice(invoice)
    assert report.warning_count
    assert report.arithmetic_status == "matched"
    assert report.to_dict()["review_required"] is True
    assert result_summary(report)[0] == "matched"


def test_review_notes_are_collapsed_when_amounts_reconcile():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.text_area[0].set_value("Notebook | 2 | $10 | $20\nTotal: $20")
    next(b for b in app.button if b.label == "Check pasted text").click().run()
    assert not app.exception
    assert any("The amounts add up" in m.value for m in app.markdown)
    notes = next(e for e in app.expander if e.label.startswith("Review notes"))
    assert notes.proto.expanded is False


def test_ocr_failure_keeps_original_and_opens_manual_recovery(monkeypatch):
    def fail_read(_document):
        raise DocumentError("The photo could not be read clearly.")
    monkeypatch.setattr("invoice_assistant.documents.local_text", fail_read)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(b for b in app.button if b.label == "Try a scan").click().run()
    assert not app.exception
    assert app.session_state["source_images"]
    assert app.session_state["invoice"]["reading_warnings"]
    editor = next(e for e in app.expander if e.label == "Something looks wrong? Edit the details")
    assert editor.proto.expanded is True
    assert next(b for b in app.button if b.label == "Mark reviewed").disabled
