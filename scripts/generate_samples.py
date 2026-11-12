"""Generate synthetic documents only. No real customer or employer data."""

import json
from pathlib import Path

import pypdfium2 as pdfium
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"

BASE = """Vendor: Sample Stationery Shop
Invoice No: DEMO-001
Invoice Date: 2026-11-12
Due Date: 2026-11-26
Currency: INR

Description | Qty | Unit Price | Amount
Notebook | 2 | 75.50 | 151.00
Pen set | 3 | 20.00 | 60.00

Subtotal: 211.00
Tax total: 37.98
Shipping: 10.00
Discount: 5.00
Grand Total: {total}
"""


def create_pdf(path, total):
    canvas = Canvas(str(path), pagesize=A4)
    canvas.setTitle("Synthetic demo invoice")
    canvas.setFillColor(colors.HexColor("#087F75"))
    canvas.rect(0, 750, A4[0], 92, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 28)
    canvas.drawString(50, 793, "INVOICE")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(50, 772, "SYNTHETIC DEMO · No real transaction")
    text = canvas.beginText(50, 710)
    text.setFillColor(colors.HexColor("#152D36"))
    text.setFont("Courier", 11)
    text.setLeading(24)
    for line in BASE.format(total=total).splitlines():
        text.textLine(line)
    canvas.drawText(text)
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.HexColor("#63777D"))
    canvas.drawString(50, 100, "Expected calculation: 211.00 + 37.98 + 10.00 - 5.00 = 253.98 INR")
    canvas.save()


def main():
    SAMPLES.mkdir(exist_ok=True)
    for name, total in (("matching_invoice", "253.98"), ("mismatch_invoice", "260.98")):
        create_pdf(SAMPLES / f"{name}.pdf", total)
        (SAMPLES / f"{name}.txt").write_text(BASE.format(total=total))
    pdf = pdfium.PdfDocument(str(SAMPLES / "matching_invoice.pdf"))
    page = pdf[0]
    bitmap = page.render(scale=2)
    bitmap.to_pil().save(SAMPLES / "scanned_invoice.png")
    bitmap.close()
    page.close()
    pdf.close()
    (SAMPLES / "expected.json").write_text(json.dumps({
        "matching_invoice.pdf": {"vendor_name": "Sample Stationery Shop", "invoice_number": "DEMO-001", "line_items": 2, "calculated_total": "253.98", "difference": "0.00", "errors": 0},
        "mismatch_invoice.pdf": {"calculated_total": "253.98", "difference": "7.00", "error_code": "TOTAL_MISMATCH"},
    }, indent=2) + "\n")
    print(f"Generated synthetic invoices in {SAMPLES}")


if __name__ == "__main__":
    main()
