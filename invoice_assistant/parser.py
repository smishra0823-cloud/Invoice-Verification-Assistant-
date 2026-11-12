"""Conservative rule baseline for printed invoice text; unknown fields stay empty."""

import re

from .models import Invoice, LineItem
from .validation import decimal_value

AMOUNT = r"[+-]?(?:\d[\d,]*)(?:\.\d+)?"
LABELS = {
    "subtotal": r"sub[ -]?total",
    "tax_total": r"(?:tax(?: total)?|total tax|gst(?: total)?)",
    "discount": r"(?:discount|total discount)",
    "shipping": r"(?:shipping|delivery|freight)(?: charge[s]?)?",
    "total": r"(?:grand total|invoice total|amount due|total amount|total)",
}


def parse_invoice_text(text: str) -> Invoice:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    invoice = Invoice(notes=["Local rule-based extraction. Review all fields against the original invoice."])

    def labeled(pattern):
        for line in lines:
            match = re.match(pattern + r"\s*[:#\-]?\s*(.+)$", line, flags=re.I)
            if match:
                return match.group(1).strip()
        return None

    invoice.vendor_name = labeled(r"(?:vendor|supplier|seller)(?: name)?")
    if not invoice.vendor_name:
        candidates = [line for line in lines[:3] if not re.search(r"\binvoice\b|^date\b", line, re.I)]
        invoice.vendor_name = candidates[0] if candidates else None
        if invoice.vendor_name:
            invoice.notes.append("Vendor was inferred from the first heading; confirm it.")
    invoice.invoice_number = labeled(r"invoice\s*(?:number|no\.?|#)")
    invoice.invoice_date = labeled(r"(?:invoice date|date)")
    invoice.due_date = labeled(r"due date")
    currency = re.search(r"\b(INR|USD|EUR|GBP|CAD|AUD|JPY|KWD|BHD)\b", text, re.I)
    invoice.currency = currency.group(1).upper() if currency else ("INR" if "₹" in text else None)

    for field, pattern in LABELS.items():
        for line in lines:
            if re.match(r"^" + pattern + r"\b", line, flags=re.I):
                numbers = re.findall(AMOUNT, line)
                if numbers:
                    setattr(invoice, field, numbers[-1])
                    break
    if invoice.tax_total is None:
        taxes = []
        for line in lines:
            if re.match(r"^(?:CGST|SGST|IGST)\b", line, flags=re.I):
                numbers = re.findall(AMOUNT, line)
                if numbers:
                    taxes.append(decimal_value(numbers[-1]))
        if taxes:
            invoice.tax_total = str(sum(taxes))

    reserved = r"^(?:sub[ -]?total|tax|gst|cgst|sgst|igst|discount|shipping|delivery|freight|grand total|invoice|amount due|total|date|due date|currency|vendor|supplier|seller)\b"
    row_pattern = re.compile(r"^(.+?)\s+(" + AMOUNT + r")\s+(" + AMOUNT + r")\s+(" + AMOUNT + r")$")
    for line in lines:
        if re.search(reserved, line, re.I):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 4:
            try:
                for value in cells[1:]:
                    decimal_value(value)
                invoice.line_items.append(LineItem(description=cells[0], quantity=cells[1], unit_price=cells[2], line_total=cells[3]))
            except ValueError:
                continue
        else:
            match = row_pattern.match(line)
            if match:
                invoice.line_items.append(LineItem(description=match[1], quantity=match[2], unit_price=match[3], line_total=match[4]))
    if not invoice.line_items:
        invoice.notes.append("No reliable table rows were found. Add rows manually or try AI vision extraction.")
    return invoice
