from pathlib import Path

import pytest

from invoice_assistant.documents import DocumentError, MAX_BYTES, local_text, read_document
from invoice_assistant.exports import csv_bytes, export_record, json_bytes, spreadsheet_safe
from invoice_assistant.parser import parse_invoice_text
from invoice_assistant.validation import validate_invoice

ROOT = Path(__file__).resolve().parents[1]


def test_pdf_extraction_and_validation_end_to_end():
    document = read_document("matching_invoice.pdf", (ROOT / "samples/matching_invoice.pdf").read_bytes())
    text, method = local_text(document)
    assert method == "PDF text"
    invoice = parse_invoice_text(text)
    assert invoice.vendor_name == "Sample Stationery Shop"
    assert invoice.invoice_number == "DEMO-001"
    assert len(invoice.line_items) == 2
    report = validate_invoice(invoice)
    assert report.calculated_total == "253.98"
    assert report.error_count == 0


def test_sample_mismatch_is_detected():
    document = read_document("mismatch_invoice.pdf", (ROOT / "samples/mismatch_invoice.pdf").read_bytes())
    text, _ = local_text(document)
    report = validate_invoice(parse_invoice_text(text))
    assert report.difference == "7.00"
    assert report.error_count == 1


def test_image_loading():
    doc = read_document("invoice.png", (ROOT / "samples/scanned_invoice.png").read_bytes())
    assert len(doc.images) == 1 and doc.page_texts == [""]


@pytest.mark.parametrize("name,data", [("bad.pdf", b"not a pdf"), ("bad.png", b"broken"), ("bad.exe", b"binary"), ("empty.pdf", b""), ("huge.png", b"a" * (MAX_BYTES + 1))])
def test_upload_validation(name, data):
    with pytest.raises(DocumentError):
        read_document(name, data)


def test_parser_keeps_unknown_fields_missing():
    invoice = parse_invoice_text("Unclear document\nNo line amounts available")
    assert invoice.total is None
    assert invoice.line_items == []


def test_whitespace_table_and_indian_number_format():
    invoice = parse_invoice_text("Vendor: Demo\nCurrency: INR\nSteel plate 2 1,000.50 2,001.00\nSubtotal: 2,001.00\nTax: 0\nShipping: 0\nDiscount: 0\nTotal: 2,001.00")
    assert len(invoice.line_items) == 1
    assert validate_invoice(invoice).calculated_total == "2001.00"


def test_gst_components_sum():
    invoice = parse_invoice_text("Vendor: Demo\nCGST 9%: 9.00\nSGST 9%: 9.00")
    assert invoice.tax_total == "18.00"


@pytest.mark.parametrize("value", ["=SUM(A1:A2)", "+cmd", "-cmd", "@evil", "\tformula", "  =HYPERLINK(1)"])
def test_spreadsheet_formula_protection(value):
    assert spreadsheet_safe(value).startswith("'")


def test_review_export_and_json_roundtrip():
    import json

    invoice = parse_invoice_text((ROOT / "samples/matching_invoice.txt").read_text())
    invoice.vendor_name = "=HYPERLINK(1)"
    report = validate_invoice(invoice)
    record = export_record(invoice, report, {"filename": "synthetic.pdf"}, reviewer="Demo Reviewer", approved=True)
    assert record["review"]["status"] == "reviewed"
    assert "'=HYPERLINK(1)" in csv_bytes(record).decode("utf-8-sig")
    assert json.loads(json_bytes(record))["validation"]["calculated_total"] == "253.98"
