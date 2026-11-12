# Five-minute demonstration

1. Run `python -m streamlit run app.py` in the activated `.venv`.
2. Explain the separation: extraction reads the document; Python independently
   checks arithmetic; a person reviews before export.
3. Extract the matching demo. Show its two line items, tax, shipping, discount
   and expected total **253.98 INR**.
4. Extract the mismatch demo. Show the **7.00 INR** discrepancy.
5. Correct the printed total in the form and click **Save edits and verify**.
6. Mark reviewed with a demo reviewer name and download CSV and JSON.
7. Extract the scanned demo to show image OCR. Open the extracted-text panel.
8. If an API key is configured and you choose to pay for a request, demonstrate
   optional AI vision and its explicit upload consent.

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
