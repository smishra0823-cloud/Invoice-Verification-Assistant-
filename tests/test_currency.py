import csv
import io
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from invoice_assistant.currency import detect_currency, format_money, set_currency
from invoice_assistant.exports import csv_bytes, export_record, json_bytes
from invoice_assistant.models import Invoice
from invoice_assistant.parser import normalized_number, parse_invoice_text
from invoice_assistant.presentation import result_summary
from invoice_assistant.validation import validate_invoice


@pytest.mark.parametrize("text,code", [
    ("Total ₹150.00", "INR"), ("Currency: INR", "INR"), ("Indian rupees 150", "INR"),
    ("Total €1.234,56", "EUR"), ("Total 150 euros", "EUR"), ("EUR 150", "EUR"),
    ("US$ 150", "USD"), ("Currency: USD\nTotal $150", "USD"),
    ("US dollars 150", "USD"), ("Canadian dollars C$150", "CAD"),
    ("A$150 Australian dollars", "AUD"), ("NZ$150", "NZD"), ("S$150", "SGD"),
    ("HK$150", "HKD"), ("£150", "GBP"), ("Japanese yen ¥150", "JPY"),
    ("Chinese yuan ¥150", "CNY"), ("AED 150", "AED"), ("currency: usd", "USD"),
    ("usd", "USD"), ("KWD 1.234", "KWD"), ("₹150 INR", "INR"),
])
def test_codes_names_symbols(text, code):
    result = detect_currency(text)
    assert result["currency"] == code
    assert result["currency_status"] == "detected"
    assert result["currency_evidence"]


@pytest.mark.parametrize("symbol", ["$", "¥", "Rs.", "rupees", "dollars"])
def test_ambiguous_symbol_identifies_family_without_guessing_country(symbol):
    result = detect_currency(f"Total {symbol} 150")
    assert result["currency"] is None
    assert result["currency_status"] == "ambiguous"
    assert result["currency_symbol"]


@pytest.mark.parametrize("text", ["INR 150\nEUR 5", "Currency USD\nTotal €150", "$150\n₹500"])
def test_conflicting_currency_blocks_comparison(text):
    invoice = parse_invoice_text(text)
    report = validate_invoice(invoice)
    assert invoice.currency_status == "mixed"
    assert report.calculated_total is None
    assert report.status == "Currency review required"
    assert result_summary(report)[1] == "Please confirm the currency first"


def test_does_not_infer_from_country_bank_or_lowercase_verb():
    assert detect_currency("Seller in India\nIBAN GB123\nPLEASE TRY AGAIN")["currency_status"] == "unknown"


def test_currency_fragments_in_invoice_identifiers_are_not_evidence():
    assert detect_currency("Invoice No: USD-EUR-123\nTotal: ₹150")["currency"] == "INR"
    assert detect_currency("Reference: CAD-001\nTotal: €150")["currency"] == "EUR"


@pytest.mark.parametrize("value,number", [("US$150.00", "150.00"), ("1.234,56 €", "1234.56"), ("C$ 150", "150"), ("₹75.50", "75.50"), ("Rs. 150", "150")])
def test_currency_decorated_numeric_cells(value, number):
    assert normalized_number(value) == number


def test_generic_dollar_is_displayed_and_exported_without_currency_missing_error():
    invoice = parse_invoice_text("Vendor: Example\nInvoice No: TEST\nDate: 2026-11-18\nNotebook | 2 | $10 | $20\nSubtotal: $20\nTax: $0\nShipping: $0\nDiscount: $0\nTotal: $20")
    report = validate_invoice(invoice)
    assert len(invoice.line_items) == 1
    assert report.difference == "0.00"
    assert format_money(report.stated_total, invoice) == "$ 20.00"
    assert "AMBIGUOUS_CURRENCY" in {issue.code for issue in report.issues}
    record = export_record(invoice, report, {"filename": "synthetic.txt"})
    row = next(csv.DictReader(io.StringIO(csv_bytes(record).decode("utf-8-sig"))))
    assert row["currency_symbol"] == "$" and row["currency"] == ""
    assert json.loads(json_bytes(record))["invoice"]["currency_status"] == "ambiguous"


def test_manual_confirmation_and_decimal_precision():
    invoice = Invoice()
    set_currency(invoice, "usd", manual=True)
    assert invoice.currency_status == "confirmed"
    assert format_money("1234.50", invoice) == "US$ 1,234.50"
    assert format_money("1.005", invoice) == "US$ 1.005"
    set_currency(invoice, "KWD")
    assert format_money("1.234", invoice) == "KWD 1.234"


def test_ui_currency_symbols_and_manual_correction_clear_review():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    next(b for b in app.button if b.label == "Try a matching invoice").click().run()
    assert any(m.value == "₹ 253.98" for m in app.metric)
    next(w for w in app.text_input if w.label == "Currency").set_value("EUR")
    next(b for b in app.button if b.label == "Save changes and recheck").click().run()
    assert not app.exception
    assert app.session_state["invoice"]["currency"] == "EUR"
    assert any(m.value == "€ 253.98" for m in app.metric)
    assert app.session_state["approved"] is False
