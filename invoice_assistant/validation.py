"""Deterministic verification independent of the extraction model."""

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .models import Invoice
from .currency import CURRENCIES, currency_precision, strip_currency


def decimal_value(value: object) -> Decimal:
    """Parse ordinary invoice numbers; reject NaN, infinity and exponent notation."""
    if value is None or str(value).strip() == "":
        raise ValueError("Missing number")
    text = str(value).strip()
    if len(text) > 40:
        raise ValueError("Number is too long")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    text = strip_currency(text)
    # Accept standard and Indian grouping, but never silently remove arbitrary commas.
    number = r"(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d+)?"
    if not re.fullmatch(r"[+-]?" + number, text):
        raise ValueError("Use a numeric amount such as 150.00")
    try:
        result = Decimal(text.replace(",", ""))
    except InvalidOperation as error:
        raise ValueError("Invalid number") from error
    if negative:
        result = -result
    if not result.is_finite() or abs(result) > Decimal("1000000000000"):
        raise ValueError("Number is outside the supported range")
    if result.as_tuple().exponent < -6:
        raise ValueError("Use at most six decimal places")
    return result


@dataclass
class Issue:
    severity: str
    code: str
    field: str
    message: str
    expected: str = ""
    actual: str = ""


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)
    calculated_subtotal: str | None = None
    calculated_total: str | None = None
    stated_total: str | None = None
    difference: str | None = None
    line_calculations: list[dict] = field(default_factory=list)

    @property
    def error_count(self):
        return sum(issue.severity == "ERROR" for issue in self.issues)

    @property
    def warning_count(self):
        return sum(issue.severity == "WARNING" for issue in self.issues)

    @property
    def arithmetic_status(self):
        if any(issue.code == "MIXED_CURRENCIES" for issue in self.issues):
            return "not_checked"
        if self.calculated_total is None or self.stated_total is None:
            return "incomplete"
        if any(issue.code == "EXTRACTION_REVIEW" for issue in self.issues):
            return "needs_details"
        if self.error_count:
            return "mismatch" if any(issue.code.endswith("MISMATCH") for issue in self.issues) else "needs_details"
        return "matched_with_rounding_note" if any(issue.code == "ROUNDING_REVIEW" for issue in self.issues) else "matched"

    @property
    def status(self):
        if any(issue.code == "MIXED_CURRENCIES" for issue in self.issues):
            return "Currency review required"
        if self.calculated_total is None or self.stated_total is None:
            return "Reading incomplete"
        return "Needs correction" if self.error_count else "Review required" if self.warning_count else "Checks passed"

    def to_dict(self):
        return {**asdict(self), "status": self.status, "arithmetic_status": self.arithmetic_status, "review_required": bool(self.issues), "errors": self.error_count, "warnings": self.warning_count}


def validate_invoice(invoice: Invoice) -> ValidationReport:
    report = ValidationReport()
    currency = (invoice.currency or "").strip().upper()
    precision = currency_precision(currency)
    quantum = Decimal(1).scaleb(-precision)

    def rounded(amount):
        return amount.quantize(quantum, rounding=ROUND_HALF_UP)

    def money(amount):
        return f"{rounded(amount):.{precision}f}"

    def issue(severity, code, name, message, expected="", actual=""):
        report.issues.append(Issue(severity, code, name, message, expected, actual))

    def number(value, name, optional=False):
        if optional and (value is None or str(value).strip() == ""):
            issue("WARNING", "ASSUMED_ZERO", name, f"{name.replace('_', ' ').title()} is not stated; treated as zero for this check.")
            return Decimal(0)
        try:
            parsed = decimal_value(value)
            if parsed < 0:
                raise ValueError("Negative values are not supported for ordinary invoices")
            return parsed
        except ValueError as error:
            issue("ERROR", "INVALID_NUMBER", name, str(error), actual=str(value or ""))
            return None

    if invoice.currency_status == "mixed":
        issue("ERROR", "MIXED_CURRENCIES", "currency", "Conflicting currency evidence was read. Confirm one currency or separate the invoices before comparing amounts. No currency conversion has been performed.")
        return report
    for warning in dict.fromkeys(invoice.reading_warnings):
        issue("WARNING", "EXTRACTION_REVIEW", "line_items", warning)
    for name in ("vendor_name", "invoice_number", "invoice_date"):
        if not str(getattr(invoice, name) or "").strip():
            issue("WARNING", "MISSING_FIELD", name, f"{name.replace('_', ' ').title()} is missing.")
    if not currency:
        if invoice.currency_symbol:
            note = " Two decimal places are used provisionally; select JPY or CNY to confirm the required precision." if invoice.currency_symbol == "¥" else " The numeric checks below use the same printed units."
            issue("WARNING", "AMBIGUOUS_CURRENCY", "currency", f"The {invoice.currency_symbol} symbol was identified. Its country-specific currency code is not specified." + note)
        else:
            issue("WARNING", "MISSING_FIELD", "currency", "No currency code, name or symbol could be read. Enter it if known.")
    if currency and currency not in CURRENCIES:
        issue("WARNING", "CURRENCY_FORMAT", "currency", "Use a three-letter currency code such as INR.")
    parsed_dates = {}
    for name in ("invoice_date", "due_date"):
        value = getattr(invoice, name)
        if value:
            try:
                parsed_dates[name] = date.fromisoformat(value)
            except ValueError:
                if re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{4}", value):
                    issue("WARNING", "AMBIGUOUS_DATE", name, "The printed date may use month/day or day/month. Confirm the order and enter it as YYYY-MM-DD.", actual=value)
                else:
                    issue("WARNING", "INVALID_DATE", name, "This date could not be read as a valid date. Confirm it against the document.", actual=value)
    if len(parsed_dates) == 2 and parsed_dates["due_date"] < parsed_dates["invoice_date"]:
        issue("WARNING", "DATE_ORDER", "due_date", "Due date precedes invoice date.")

    computed = Decimal(0)
    printed_gross, rounding_notes = [], []
    all_lines_valid = bool(invoice.line_items)
    if not invoice.line_items:
        issue("ERROR", "NO_LINE_ITEMS", "line_items", "Add at least one line item before verifying the invoice.")
    for index, item in enumerate(invoice.line_items, 1):
        prefix = f"line_items[{index}]"
        if not item.description.strip():
            issue("WARNING", "MISSING_DESCRIPTION", prefix, f"Line {index} has no description.")
        quantity = number(item.quantity, f"{prefix}.quantity")
        price = number(item.unit_price, f"{prefix}.unit_price")
        if quantity is not None and quantity <= 0:
            issue("ERROR", "INVALID_QUANTITY", f"{prefix}.quantity", "Quantity must be greater than zero.")
            quantity = None
        if quantity is None or price is None:
            all_lines_valid = False
            continue
        expected = rounded(quantity * price)
        computed += expected
        report.line_calculations.append({"line": index, "description": item.description, "calculated_amount": money(expected)})
        if item.tax_rate is not None or item.gross_total is not None:
            rate = number(item.tax_rate, f"{prefix}.tax_rate")
            gross = number(item.gross_total, f"{prefix}.gross_total")
            if rate is not None and rate > 100:
                issue("ERROR", "INVALID_NUMBER", f"{prefix}.tax_rate", "Tax percentage must be between 0 and 100.")
                rate = None
            if rate is not None and gross is not None:
                calculated_gross = rounded(expected * (1 + rate / 100))
                printed_gross.append(gross)
                difference = rounded(gross - calculated_gross)
                report.line_calculations[-1].update(tax_rate=str(rate), calculated_gross=money(calculated_gross), printed_gross=money(gross))
                if difference:
                    if abs(difference) <= quantum:
                        rounding_notes.append(f"Item {index}: printed gross {money(gross)}, recalculated {money(calculated_gross)}")
                    else:
                        issue("ERROR", "GROSS_MISMATCH", f"{prefix}.gross_total", f"Item {index}: net amount plus VAT does not match the printed gross amount.", money(calculated_gross), money(gross))
        if item.line_total is None or not item.line_total.strip():
            issue("WARNING", "MISSING_LINE_TOTAL", f"{prefix}.line_total", "Line amount is missing; quantity × unit price was used.", expected=money(expected))
        else:
            stated = number(item.line_total, f"{prefix}.line_total")
            if stated is not None and rounded(stated) != expected:
                issue("ERROR", "LINE_MISMATCH", f"{prefix}.line_total", f"Line {index}: quantity × unit price does not match the stated line amount.", money(expected), money(stated))

    stated_subtotal = None
    if invoice.subtotal is None or not invoice.subtotal.strip():
        issue("WARNING", "MISSING_SUBTOTAL", "subtotal", "Subtotal is not stated; sum of calculated line amounts was used.")
    else:
        stated_subtotal = number(invoice.subtotal, "subtotal")
    tax = number(invoice.tax_total, "tax_total", optional=True)
    discount = number(invoice.discount, "discount", optional=True)
    shipping = number(invoice.shipping, "shipping", optional=True)
    total = number(invoice.total, "total")
    if total is not None:
        report.stated_total = money(total)
    if all_lines_valid:
        report.calculated_subtotal = money(computed)
        if stated_subtotal is not None and rounded(stated_subtotal) != rounded(computed):
            issue("ERROR", "SUBTOTAL_MISMATCH", "subtotal", "Subtotal does not match the sum of quantity × unit price for all lines.", money(computed), money(stated_subtotal))
        if all(value is not None for value in (tax, discount, shipping)):
            expected_total = rounded(computed + tax + shipping - discount)
            report.calculated_total = money(expected_total)
            if expected_total < 0:
                issue("ERROR", "EXCESS_DISCOUNT", "discount", "Discount exceeds the invoice's positive charges.")
            if total is not None:
                difference = rounded(total - expected_total)
                report.difference = money(difference)
                if difference:
                    direction = "high" if difference > 0 else "low"
                    issue("ERROR", "TOTAL_MISMATCH", "total", f"Invoice total is too {direction} by {money(abs(difference))} {currency}.".strip(), money(expected_total), money(total))
            if total is not None and len(printed_gross) == len(invoice.line_items):
                sum_gross = rounded(sum(printed_gross) + shipping - discount)
                difference = rounded(total - sum_gross)
                if difference:
                    if abs(difference) <= quantum * len(printed_gross):
                        rounding_notes.append(f"Printed gross item amounts total {money(sum_gross)}, invoice total {money(total)}")
                    else:
                        issue("ERROR", "GROSS_SUM_MISMATCH", "total", "Printed gross item amounts do not add up to the invoice total after shipping and discount.", money(sum_gross), money(total))
    if rounding_notes:
        issue("WARNING", "ROUNDING_REVIEW", "tax_total", "Possible tax-rounding difference. Confirm the supplier's rounding method: " + "; ".join(rounding_notes) + ". The difference has not been silently accepted.")
    return report
