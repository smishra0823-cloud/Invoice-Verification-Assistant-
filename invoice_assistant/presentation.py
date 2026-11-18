"""Plain-language result states, separate from extraction and arithmetic."""
import re

MISMATCH_CODES = {"LINE_MISMATCH", "SUBTOTAL_MISMATCH", "TOTAL_MISMATCH", "GROSS_MISMATCH", "GROSS_SUM_MISMATCH"}


def result_summary(report):
    if any(issue.code == "MIXED_CURRENCIES" for issue in report.issues):
        return "attention", "Please confirm the currency first", "Different currencies were detected. Amounts have not been added or compared across currencies. Review the currency evidence below."
    if report.calculated_total is None or report.stated_total is None:
        return "attention", "We couldn’t read enough to check this invoice", "This is a reading problem, not a confirmed invoice error. Compare the extracted details with the original and fill in the missing amounts below."
    if any(issue.code in MISMATCH_CODES for issue in report.issues):
        return "correction", "The amounts don’t match", "The saved amounts disagree with one or more calculations. Check the highlighted values against the original before deciding whether the invoice is wrong."
    if report.error_count:
        return "attention", "Please check the extracted numbers", "Some values could not be used in the check. Correct them against the original, then save to recalculate."
    if any(issue.code == "ROUNDING_REVIEW" for issue in report.issues):
        return "attention", "Totals match · check tax rounding", "The net subtotal plus the printed tax matches the invoice total. Small differences in the item-level gross amounts still need a rounding review."
    if report.warning_count:
        return "attention", "Totals match · a few details to confirm", "The saved item amounts and invoice total agree. Review the missing details and calculation assumptions below."
    return "matched", "The amounts add up", "The arithmetic checks passed. Please confirm that the extracted details match your original."


def field_label(field):
    names = {"vendor_name": "Supplier", "invoice_number": "Invoice number", "invoice_date": "Invoice date", "due_date": "Due date", "currency": "Currency", "quantity": "Quantity", "unit_price": "Unit price", "line_total": "Net amount", "gross_total": "Gross amount", "tax_rate": "VAT rate", "tax_total": "Tax / rounding", "subtotal": "Net subtotal", "total": "Invoice total", "line_items": "Items", "shipping": "Shipping", "discount": "Discount"}
    match = re.fullmatch(r"line_items\[(\d+)\](?:\.(\w+))?", field)
    if match:
        return f"Item {match[1]}" + (f" · {names.get(match[2], match[2])}" if match[2] else "")
    return names.get(field, field.replace("_", " ").capitalize())
