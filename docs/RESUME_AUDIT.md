# Résumé feature check — 18 November 2026

| Résumé statement | Implementation and verification |
| --- | --- |
| Developing a workflow to extract invoice fields and line items from scans | Implemented: PDF/image reader, native macOS OCR and parser for simple and net/VAT/gross tables. Tested locally on the supplied 15-image batch; unfamiliar layouts can still need correction. |
| Using a vision-language model to return structured data for Python validation | Implemented as an optional OpenAI vision mode using a Pydantic schema through `responses.parse`. The default reader is local OCR. API tests mock the provider: no live-model accuracy result is claimed. A user's API key, model access, credit and explicit document consent are required for a live call. |
| Checking calculations, totals and missing fields; flagging discrepancies | Implemented independently with Decimal: line/net/gross calculations, subtotal, printed tax, shipping, discount and total; missing values, dates, currency ambiguity and tax-rounding notes. Incomplete reading is distinguished from a mismatch. |
| Streamlit review screen with editable results and CSV export | Implemented: original document preview, editable fields/items, recalculation, review status, CSV and JSON downloads. Changes reset previous review approval. |

The wording “Developing” is appropriate for this prototype. For precision, the
second bullet can say: **“Integrated optional vision-language extraction with
structured outputs and independent Python validation.”** This avoids implying
that the local demo always uses a vision-language model, or that a live model
benchmark has been completed.

Do not claim universal accuracy, all-language support, production deployment,
fraud detection, or a trained custom model. Those are not established by this work.
