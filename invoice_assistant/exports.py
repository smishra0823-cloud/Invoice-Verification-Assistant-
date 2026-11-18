"""Portable review records and spreadsheet-safe CSV exports."""

import csv
import io
import json
from datetime import datetime, timezone

from .models import Invoice
from .validation import ValidationReport


def spreadsheet_safe(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r")):
        return "'" + text
    return text


def export_record(invoice: Invoice, report: ValidationReport, source: dict, reviewer: str = "", approved=False):
    return {
        "schema_version": "1.2",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "invoice": invoice.model_dump(),
        "validation": report.to_dict(),
        "review": {
            "status": "reviewed" if approved else "draft",
            "reviewer": reviewer if approved else "",
            "approved_at": datetime.now(timezone.utc).isoformat() if approved else None,
        },
    }


def json_bytes(record):
    return json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8")


def csv_bytes(record):
    stream = io.StringIO(newline="")
    fields = ["vendor_name", "invoice_number", "invoice_date", "currency", "currency_symbol", "currency_status", "description", "quantity", "unit_price", "line_total", "tax_rate", "gross_total", "invoice_total", "calculated_total", "difference", "validation_status", "review_status", "reviewer"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    invoice = record["invoice"]
    for item in invoice["line_items"] or [{}]:
        row = {
            **{name: invoice.get(name) for name in fields[:6]},
            **{name: item.get(name) for name in ("description", "quantity", "unit_price", "line_total", "tax_rate", "gross_total")},
            "invoice_total": invoice["total"],
            "calculated_total": record["validation"]["calculated_total"],
            "difference": record["validation"]["difference"],
            "validation_status": record["validation"]["status"],
            "review_status": record["review"]["status"],
            "reviewer": record["review"]["reviewer"],
        }
        writer.writerow({key: spreadsheet_safe(value) for key, value in row.items()})
    return stream.getvalue().encode("utf-8-sig")
