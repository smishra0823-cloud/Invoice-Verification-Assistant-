"""Synthetic examples of the failure modes reported on uploaded VAT invoices."""
import pytest

from invoice_assistant.models import Invoice, LineItem
from invoice_assistant.parser import normalized_number, parse_invoice_text
from invoice_assistant.presentation import field_label, result_summary
from invoice_assistant.validation import validate_invoice

VAT_TEXT = """Invoice no: TEST-009
Date of issue: 01/17/2013
Seller:  Client:
Example Supplies  Example Customer
Tax Id: 999-11-2222  Tax Id: 111-22-3333
ITEMS
No. Description  Qty  UM  Net price  Net worth  VAT [%]  Gross
worth
1.  Notebook holder  5,00  each  10,75  53,75  10%  59,13
2.  Metal stand  3,00  each  19,90  59,70  10%  65,67
with a long second description line
SUMMARY
VAT [%]  Net worth  VAT  Gross worth
10%  113,45  11,34  124,79
Total  $113,45  $ 11,34  $124,79
"""


def test_net_vat_gross_extraction_and_rounding_review():
    invoice = parse_invoice_text(VAT_TEXT)
    assert invoice.vendor_name == "Example Supplies"
    assert invoice.invoice_number == "TEST-009"
    assert invoice.invoice_date == "2013-01-17"
    assert invoice.currency is None  # $ does not establish a specific ISO code.
    assert len(invoice.line_items) == 2  # Summary is not a third item.
    assert invoice.line_items[0].quantity == "5.00"
    assert invoice.line_items[0].tax_rate == "10"
    assert invoice.line_items[0].gross_total == "59.13"
    assert "second description line" in invoice.line_items[1].description
    assert (invoice.subtotal, invoice.tax_total, invoice.total) == ("113.45", "11.34", "124.79")
    report = validate_invoice(invoice)
    assert report.error_count == 0 and report.difference == "0.00"
    assert "ROUNDING_REVIEW" in {i.code for i in report.issues}
    assert result_summary(report)[1] == "Totals match · check tax rounding"


@pytest.mark.parametrize("value,expected", [("1 234,56", "1234.56"), ("40 677,81", "40677.81"), ("1.234,56", "1234.56"), ("113,45", "113.45"), ("1,234.56", "1234.56"), ("1,23,456.78", "123456.78")])
def test_decimal_locales(value, expected):
    assert normalized_number(value) == expected


def test_tax_identifiers_never_become_tax_amounts():
    invoice = parse_invoice_text("Vendor: Test\nTax Id: 999-11-2222\nTax Number: 111-22-3333\nTax identification: 999999\nNotebook | 2 | 10 | 20\nTotal: 20")
    assert invoice.tax_total is None
    assert len(invoice.line_items) == 1


def test_ambiguous_dates_are_not_guessed():
    invoice = parse_invoice_text(VAT_TEXT.replace("01/17/2013", "04/09/2014"))
    assert invoice.invoice_date == "04/09/2014"
    assert "AMBIGUOUS_DATE" in {i.code for i in validate_invoice(invoice).issues}


def test_large_grouped_values_and_missing_row_numbers():
    text = VAT_TEXT.replace("1.  Notebook holder  5,00  each  10,75  53,75  10%  59,13", "Notebook holder  5,00  each  1 840,10  9 200,50  10%  10 120,55")
    invoice = parse_invoice_text(text)
    assert len(invoice.line_items) == 2
    assert invoice.line_items[0].unit_price == "1840.10"
    assert invoice.line_items[0].gross_total == "10120.55"
    assert "SUBTOTAL_MISMATCH" in {i.code for i in validate_invoice(invoice).issues}


def test_unsupported_format_is_reading_failure_not_invoice_failure():
    report = validate_invoice(parse_invoice_text("Unclear invoice image"))
    assert report.status == "Reading incomplete"
    assert result_summary(report)[0] == "attention"
    assert "reading problem" in result_summary(report)[2]


def test_significant_gross_error_is_not_hidden_as_rounding():
    invoice = parse_invoice_text(VAT_TEXT.replace("10%  59,13", "10%  79,13"))
    report = validate_invoice(invoice)
    assert "GROSS_MISMATCH" in {i.code for i in report.issues}
    assert result_summary(report)[1] == "The amounts don’t match"


def test_invalid_gross_inputs_are_flagged():
    invoice = Invoice(line_items=[LineItem(description="Test", quantity="1", unit_price="10", line_total="10", tax_rate="999", gross_total="bad")], subtotal="10", tax_total="1", shipping="0", discount="0", total="11")
    report = validate_invoice(invoice)
    assert report.error_count >= 2


def test_friendly_field_names():
    assert field_label("line_items[2].quantity") == "Item 2 · Quantity"


def test_summary_total_tax_not_misread_as_invoice_total():
    invoice = parse_invoice_text("Vendor: Test\nTotal tax: 10\nGrand total: 110")
    assert invoice.tax_total == "10" and invoice.total == "110"
