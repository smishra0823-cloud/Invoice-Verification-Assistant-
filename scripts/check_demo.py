"""Offline preflight: actual sample reading, arithmetic and export checks.

Run .venv/bin/python scripts/check_demo.py --ocr before an interview.
This does not call an API or hide problems in an uploaded document.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--ocr", action="store_true", help="Also read the actual scanned sample locally")
    options = args.parse_args()
    missing = [name for name in ("streamlit", "pandas", "pydantic", "PIL", "pypdf", "pypdfium2", "dotenv") if importlib.util.find_spec(name) is None]
    if missing:
        print("Missing packages: " + ", ".join(missing))
        print("Install them in this environment: python -m pip install -r requirements.txt")
        return 1
    from invoice_assistant.documents import read_document, local_text
    from invoice_assistant.parser import parse_invoice_text
    from invoice_assistant.validation import validate_invoice
    from invoice_assistant.exports import export_record, csv_bytes, json_bytes
    try:
        for name, total, difference in (("matching_invoice.pdf", "253.98", "0.00"), ("mismatch_invoice.pdf", "253.98", "7.00")):
            path = ROOT / "samples" / name
            text, _ = local_text(read_document(path.name, path.read_bytes()))
            invoice = parse_invoice_text(text)
            report = validate_invoice(invoice)
            if report.calculated_total != total or report.difference != difference:
                raise ValueError(f"Unexpected result for {name}; run the project tests before presenting.")
            record = export_record(invoice, report, {"filename": name})
            if not csv_bytes(record) or json.loads(json_bytes(record))["validation"]["calculated_total"] != total:
                raise ValueError("The export check did not pass.")
            print(f"PASS  {name}: expected calculation and CSV/JSON exports")
    except Exception as error:
        print(f"The demo needs attention: {error}")
        return 1
    if options.ocr:
        try:
            path = ROOT / "samples/scanned_invoice.png"
            text, _ = local_text(read_document(path.name, path.read_bytes()))
            report = validate_invoice(parse_invoice_text(text))
            if report.calculated_total != "253.98" or report.difference != "0.00":
                raise ValueError("The scanned example did not produce the expected amounts.")
            print("PASS  Scanned image: local OCR and arithmetic")
        except Exception as error:
            print(f"Photo reading needs attention: {error}")
            print("Text PDFs and manual review remain available.")
            return 2
    print("READY  Offline demo checked. No API key or paid request was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
