"""Small reproducible fixture evaluation; never presented as a real-world benchmark."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from invoice_assistant.documents import local_text, read_document
from invoice_assistant.parser import parse_invoice_text
from invoice_assistant.validation import validate_invoice


def main():
    expected = json.loads((ROOT / "samples/expected.json").read_text())
    results = []
    for name, target in expected.items():
        document = read_document(name, (ROOT / "samples" / name).read_bytes())
        text, method = local_text(document)
        invoice = parse_invoice_text(text)
        report = validate_invoice(invoice)
        actual = {"vendor_name": invoice.vendor_name, "invoice_number": invoice.invoice_number,
                  "line_items": len(invoice.line_items), "calculated_total": report.calculated_total,
                  "difference": report.difference, "errors": report.error_count}
        checks = {key: (value in {issue.code for issue in report.issues} if key == "error_code" else actual[key] == value) for key, value in target.items()}
        results.append({"file": name, "method": method, "checks": checks, "passed": all(checks.values())})
    print(json.dumps({"scope": "Two synthetic fixtures only; not real-world extraction accuracy.", "results": results}, indent=2))
    return 0 if all(row["passed"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
