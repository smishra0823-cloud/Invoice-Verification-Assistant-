# Five-minute demonstration

1. Run `python -m streamlit run app.py` in the activated `.venv`.
2. Explain the separation: extraction reads the document; Python independently
   checks arithmetic; a person reviews before export.
3. Click **Try a matching invoice**. Show its two line items, tax, shipping, discount
   and expected total **253.98 INR**.
4. Click **Check another invoice**, then **Find a mismatch**. Show the **7.00 INR** discrepancy.
5. Open **Something looks wrong? Edit the details**, correct the total and click **Save changes and recheck**.
6. Open **Mark as reviewed (optional)**, complete the review and download CSV and JSON.
7. Return home and click **Try a scan**. Open **How this was read** to show the OCR text.
8. If an API key is configured and you choose to pay for a request, demonstrate
   cloud AI inside **Optional settings** and its explicit upload consent.

## Questions to be ready to answer

- **Why Decimal?** Binary floating-point can introduce surprises with money.
- **Why validate outside the model?** A model can misread or invent numbers;
  deterministic checks are independently testable.
- **Does a passing result mean an invoice is genuine?** No; it only means the
  implemented arithmetic checks passed on the saved data.
- **What happens when extraction fails?** The user sees a clear error or missing
  fields and can enter/correct data manually.
- **Why two extraction modes?** A local baseline supports inexpensive,
  reproducible demonstrations; optional multimodal AI handles richer layouts.
- **How was it evaluated?** Automated behavior tests and a small synthetic
  fixture evaluation. Do not describe that as real-world accuracy.
- **What needs improvement?** Real-world labeled evaluation, inclusive/per-line
  tax, duplicate detection, authenticated reviewers and deployment controls.

## Implementation disclosure

This project was built with AI coding assistance. Review and understand the
implementation before presenting it as personal independent work. The original
learning program is preserved in `main.py`.
