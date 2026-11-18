"""Evidence-based local parsing for simple tables and net/VAT/gross tables.

Locale conversion happens here; the independent checker receives canonical
decimal strings. Never choose a number because it makes the totals balance.
"""

import re
from datetime import date, datetime

from .models import Invoice, LineItem
from .currency import set_currency, strip_currency
from .validation import decimal_value

AMOUNT = r"[+-]?(?:\d{1,3}(?:[ \u00a0]\d{3})+(?:[.,]\d+)?|\d[\d.,]*)"
VAT_ROW = re.compile(
    r"^(?P<description>.*?)\s*(?P<quantity>" + AMOUNT + r")\s+"
    r"(?:each|pcs?\.?|units?|kg|hrs?|hours?|sets?|boxes?)\s+"
    r"(?P<unit_price>" + AMOUNT + r")\s+(?P<line_total>" + AMOUNT + r")\s+"
    r"(?P<tax_rate>\d+(?:[.,]\d+)?)\s*%\s+(?P<gross_total>" + AMOUNT + r")$", re.I)


def normalized_number(value: str, comma_decimal=False) -> str:
    value = value.strip().replace("\u00a0", " ")
    value = strip_currency(value)
    if " " in value:
        if not re.fullmatch(r"[+-]?\d{1,3}(?: \d{3})+(?:[.,]\d+)?", value):
            raise ValueError("Unclear number grouping")
        value = value.replace(" ", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            if not re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})*,\d+", value):
                raise ValueError("Unclear decimal format")
            value = value.replace(".", "").replace(",", ".")
    elif "," in value and (comma_decimal or re.fullmatch(r"[+-]?\d+,\d{1,2}", value)):
        if value.count(",") != 1:
            raise ValueError("Unclear decimal format")
        value = value.replace(",", ".")
    return str(decimal_value(value))


def normalized_date(value):
    if not value:
        return None
    value = value.strip()
    match = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", value)
    if match:
        first, second, year = map(int, match.groups())
        # Resolve only when the order is evidenced; 04/09 remains ambiguous.
        month, day = (second, first) if first > 12 else (first, second)
        if first > 12 or second > 12 or first == second:
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                pass
    for pattern in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    return value


def table_columns(line):
    """Recognize explicit column names instead of assuming one fixed order."""
    cells = re.split(r"\s*\|\s*|\t+|\s{2,}", line.strip())
    aliases = {
        "description": {"description", "item", "items", "product", "particulars", "service", "item description"},
        "quantity": {"qty", "quantity", "qty."},
        "unit_price": {"price", "unit price", "rate", "net price", "unit cost"},
        "line_total": {"amount", "total", "line total", "net amount", "net worth", "line amount"},
    }
    mapped = {}
    for index, cell in enumerate(cells):
        label = re.sub(r"\s*\([^)]*\)", "", cell.lower()).strip()
        for field, names in aliases.items():
            if label in names:
                mapped[field] = index
    return mapped if {"description", "quantity", "unit_price"} <= mapped.keys() else None


def parse_invoice_text(text: str) -> Invoice:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    invoice = Invoice(notes=["Read locally. Compare the extracted details with the original invoice."])
    comma_decimal = len(re.findall(r"\d+,\d{2}(?!\d)", text)) > len(re.findall(r"\d+\.\d{2}(?!\d)", text))
    if comma_decimal:
        invoice.notes.append("Comma decimals were converted to dot decimals, e.g. 113,45 → 113.45.")

    def labeled(pattern, next_line=False):
        for index, line in enumerate(lines):
            match = re.match(pattern + r"\s*[:#\-]?\s*(.*)$", line, flags=re.I)
            if match:
                value = re.split(r"\s{2,}|\b(?:client|customer|buyer)\s*:", match[1], maxsplit=1, flags=re.I)[0].strip()
                if value:
                    return value
                if next_line and index + 1 < len(lines):
                    return re.split(r"\s{2,}", lines[index + 1])[0].strip()
        return None

    invoice.vendor_name = labeled(r"(?:(?:vendor|supplier|seller)(?: name)?|bill from)\b", next_line=True)
    if not invoice.vendor_name:
        candidates = [line for line in lines[:3] if not re.search(r"\binvoice\b|^date\b", line, re.I)]
        invoice.vendor_name = candidates[0] if candidates else None
        if invoice.vendor_name:
            invoice.notes.append("Supplier inferred from the first heading; confirm it.")
    invoice.invoice_number = labeled(r"invoice\s*(?:number\b|no\.?\b|#)")
    invoice.invoice_date = normalized_date(labeled(r"(?:date of issue|invoice date|issue date|date)\b"))
    invoice.due_date = normalized_date(labeled(r"due date\b"))
    set_currency(invoice, text)

    vat_layout = bool(re.search(r"net\s+price", text, re.I) and re.search(r"net\s+worth", text, re.I) and re.search(r"\bVAT\b", text, re.I) and re.search(r"\bgross\b", text, re.I))
    summary_at = next((i for i, line in enumerate(lines) if re.fullmatch(r"summary", line, re.I)), len(lines))
    items_at = next((i + 1 for i, line in enumerate(lines[:summary_at]) if re.fullmatch(r"items", line, re.I)), 0)

    if vat_layout:
        for line in lines[items_at:summary_at]:
            match = VAT_ROW.match(line)
            if match:
                fields = match.groupdict()
                fields["description"] = re.sub(r"^\d+[.)]\s*", "", fields["description"]).strip()
                try:
                    fields.update({name: normalized_number(value, comma_decimal) for name, value in fields.items() if name != "description"})
                    invoice.line_items.append(LineItem(**fields))
                except ValueError:
                    invoice.notes.append("An item row contained an unreadable number; review the source.")
            elif invoice.line_items and not re.search(r"\b(?:qty|net price|net worth|VAT|gross)\b|^worth$", line, re.I):
                # Multiline descriptions belong to the preceding item, never a new row.
                invoice.line_items[-1].description += " " + line
        for line in reversed(lines[summary_at:]):
            if re.match(r"^total\b", line, re.I):
                values = re.findall(AMOUNT, line)
                if len(values) == 3:
                    try:
                        invoice.subtotal, invoice.tax_total, invoice.total = [normalized_number(value, comma_decimal) for value in values]
                    except ValueError:
                        pass
                break
        invoice.notes.append("Net price and net worth were read separately from VAT rate and gross worth.")
    else:
        reserved = r"^(?:sub[ -]?total|tax|gst|cgst|sgst|igst|discount|shipping|delivery|freight|grand total|invoice|amount due|total|date|due date|currency|vendor|supplier|seller|summary)\b"
        pattern = re.compile(r"^(.+?)\s+(" + AMOUNT + r")\s+(" + AMOUNT + r")\s+(" + AMOUNT + r")$")
        columns = None
        for line in lines[:summary_at]:
            header = table_columns(line)
            if header:
                columns = header
                continue
            if re.search(reserved, line, re.I):
                columns = None
                continue
            if columns:
                cells = re.split(r"\s*\|\s*|\t+|\s{2,}", line.strip())
                if len(cells) > max(columns.values()):
                    try:
                        fields = {field: cells[index] if field == "description" else normalized_number(cells[index], comma_decimal) for field, index in columns.items()}
                        invoice.line_items.append(LineItem(**fields))
                    except ValueError:
                        invoice.reading_warnings.append("An item row could not be read completely. Check all quantities, prices and amounts in the edit form.")
                    continue
                if len(cells) == 1 and invoice.line_items and not re.fullmatch(r"[-_= ]+", line):
                    invoice.line_items[-1].description += " " + line
                    continue
                if not re.fullmatch(r"[-_=| ]+", line):
                    invoice.reading_warnings.append("An item row had missing columns. Check the original before relying on the calculated total.")
                continue
            cells = [cell.strip() for cell in line.split("|")]
            match = pattern.match(line) if len(cells) != 4 else None
            if match:
                cells = list(match.groups())
            if len(cells) == 4:
                try:
                    values = [normalized_number(value, comma_decimal) for value in cells[1:]]
                    invoice.line_items.append(LineItem(description=cells[0], quantity=values[0], unit_price=values[1], line_total=values[2]))
                except ValueError:
                    pass

    labels = {
        "subtotal": r"(?:sub[ -]?total|net total)",
        "tax_total": r"(?:tax(?: total)?|total tax|gst(?: total)?|vat(?: total)?)(?!\s*(?:id|no\b|number|identification))",
        "discount": r"(?:discount|total discount)",
        "shipping": r"(?:shipping|delivery|freight)(?: charge[s]?)?",
        "total": r"(?:grand total|gross total|invoice total|bill total|balance due|total due|amount payable|amount due|total amount|total)(?!\s*(?:tax|discount|items|qty|quantity)\b)",
    }
    for field, pattern in labels.items():
        if getattr(invoice, field) is not None:
            continue
        for line in lines:
            if re.match(r"^" + pattern + r"\b", line, flags=re.I):
                values = re.findall(AMOUNT, line)
                # Do not treat a percentage by itself as a tax amount.
                if values and not (field == "tax_total" and len(values) == 1 and "%" in line):
                    try:
                        setattr(invoice, field, normalized_number(values[-1], comma_decimal))
                    except ValueError:
                        continue
                    break
    if invoice.tax_total is None:
        taxes = []
        for line in lines:
            if re.match(r"^(?:CGST|SGST|IGST)\b", line, re.I):
                values = re.findall(AMOUNT, line)
                if values and not (len(values) == 1 and "%" in line):
                    try:
                        taxes.append(decimal_value(normalized_number(values[-1], comma_decimal)))
                    except ValueError:
                        pass
        if taxes:
            invoice.tax_total = str(sum(taxes))
    if not invoice.line_items:
        invoice.notes.append("No reliable item rows were found. The arithmetic cannot be verified until the details are entered or read correctly.")
    return invoice
