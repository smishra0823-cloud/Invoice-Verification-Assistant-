from decimal import Decimal

import pytest

from invoice_assistant.models import Invoice, LineItem
from invoice_assistant.validation import decimal_value, validate_invoice


def good_invoice(**updates):
    fields = dict(vendor_name="Demo Supplies", invoice_number="INV-01", invoice_date="2026-11-12", currency="INR",
        line_items=[LineItem(description="Notebook", quantity="2", unit_price="75.50", line_total="151.00")],
        subtotal="151.00", tax_total="0", shipping="0", discount="0", total="151.00")
    fields.update(updates)
    return Invoice(**fields)


def test_exact_decimal_match():
    report = validate_invoice(good_invoice())
    assert report.status == "Checks passed"
    assert report.difference == "0.00"
    assert report.calculated_total == "151.00"


@pytest.mark.parametrize("value,difference", [("160", "9.00"), ("140", "-11.00")])
def test_mismatch_in_both_directions(value, difference):
    report = validate_invoice(good_invoice(total=value))
    assert report.difference == difference
    assert "TOTAL_MISMATCH" in {issue.code for issue in report.issues}


def test_does_not_trust_wrong_line_total():
    invoice = good_invoice(subtotal="160", total="160")
    invoice.line_items[0].line_total = "160"
    report = validate_invoice(invoice)
    assert report.calculated_total == "151.00"
    assert {"LINE_MISMATCH", "SUBTOTAL_MISMATCH", "TOTAL_MISMATCH"} <= {i.code for i in report.issues}


def test_tax_shipping_discount():
    report = validate_invoice(good_invoice(tax_total="27.18", shipping="10", discount="5", total="183.18"))
    assert report.error_count == 0
    assert report.calculated_total == "183.18"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e3", "hello", "1,2", "1.00000001", "", None])
def test_rejects_invalid_numbers(value):
    with pytest.raises(ValueError):
        decimal_value(value)


@pytest.mark.parametrize("value,expected", [("1,234.50", "1234.50"), ("1,23,456.78", "123456.78"), ("₹75.50", "75.50"), ("INR 100", "100"), ("(25.00)", "-25.00")])
def test_currency_and_grouping(value, expected):
    assert decimal_value(value) == Decimal(expected)


@pytest.mark.parametrize("quantity", ["0", "-2", "NaN"])
def test_invalid_quantity_never_passes(quantity):
    invoice = good_invoice()
    invoice.line_items[0].quantity = quantity
    report = validate_invoice(invoice)
    assert report.error_count
    assert report.calculated_total is None


def test_missing_values_are_not_silently_accepted():
    report = validate_invoice(Invoice())
    assert report.error_count
    assert {"NO_LINE_ITEMS", "MISSING_FIELD", "INVALID_NUMBER"} <= {i.code for i in report.issues}


def test_missing_optional_charges_have_explicit_assumptions():
    report = validate_invoice(good_invoice(tax_total=None))
    assert report.calculated_total == "151.00"
    assert report.warning_count == 1
    assert report.status == "Review required"


def test_round_each_line_before_summing():
    invoice = good_invoice(line_items=[LineItem(description="A", quantity="1", unit_price="0.105", line_total="0.11"), LineItem(description="B", quantity="1", unit_price="0.105", line_total="0.11")], subtotal="0.22", total="0.22")
    assert validate_invoice(invoice).calculated_total == "0.22"


def test_invalid_and_reversed_dates():
    assert "INVALID_DATE" in {i.code for i in validate_invoice(good_invoice(invoice_date="2026-99-01")).issues}
    assert "DATE_ORDER" in {i.code for i in validate_invoice(good_invoice(due_date="2026-01-01")).issues}


def test_excess_discount_is_error():
    assert "EXCESS_DISCOUNT" in {i.code for i in validate_invoice(good_invoice(discount="200")).issues}


def test_jpy_uses_whole_units():
    report = validate_invoice(good_invoice(currency="JPY", subtotal="151", total="151"))
    assert report.calculated_total == "151"
