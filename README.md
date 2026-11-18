# InvoiceLens

**A multimodal invoice verification assistant with editable extraction and independent arithmetic checks.**

Upload a PDF or invoice photo, extract its fields, compare them with the source,
fix mistakes, and export a review record. The original beginner exercise remains
in `main.py`; the complete application starts from `app.py`.

## Run on a Mac

```bash
cd ~/Documents/AI-ML-Projects/invoice-assistant
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed in Terminal, usually <http://localhost:8501>.
Stop the server with **Control+C** in the same Terminal.

For a fresh clone:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/generate_samples.py
python -m streamlit run app.py
```

In **VS Code**, select the `.venv` Python interpreter. The included tasks let you
choose **Terminal → Run Task → Run InvoiceLens** or **Test InvoiceLens**. F5 can
also start the `InvoiceLens: Streamlit` debug configuration. `zsh run.command` is
another shortcut. Keep `.venv`, `.env` and actual invoices out of Git.

## Try the demonstration

1. Click **Try a matching invoice**. No setup or API key is needed.
   The expected total is **253.98 INR**.
2. Compare the original with the readable supplier, dates, line items and totals.
3. Click **Check another invoice**, then **Find a mismatch**. The printed total is
   **260.98 INR**, so the checker flags a **7.00 INR** overcharge.
4. Open **Something looks wrong? Edit the details**, change the total to
   `253.98` and click **Save changes and recheck**.
5. Download the spreadsheet (CSV) or detailed report (JSON). To label the export
   reviewed, open **Mark as reviewed (optional)**, enter a name, acknowledge
   the source review and click **Mark reviewed**.
6. Click **Check another invoice**, then **Try a scan** to exercise image OCR. The first macOS OCR run
   compiles a small Swift helper and may take longer.

All sample documents are synthetic. They are not real purchases or customer
invoices. The printed calculation on the demo PDF is teaching material; the
checker computes its own total from the line items.

## Extraction choices

### Local baseline: no API charges

- Text PDFs: `pypdf` reads the document's text layer.
- Scanned PDFs and PNG/JPEG images: Apple's Vision OCR runs locally on macOS.
  Apple command-line developer tools are needed to compile the included Swift
  helper. If Tesseract is installed, it is available as a fallback and is the
  local image-OCR route on Windows/Linux.
- A conservative rule parser recognizes labeled invoice fields and simple
  four-column tables: `Description | Qty | Unit Price | Amount` or equivalent
  whitespace-separated rows. It handles CGST/SGST totals and Indian number
  grouping. Arbitrary layouts may require manual correction or AI vision.
- Net/VAT/gross tables are also supported: comma decimals and spaced thousands
  are normalized, the seller is separated from the client, wrapped descriptions
  stay with their item, and summary rows are excluded from the item list.
  Tax IDs are never interpreted as tax amounts. Ambiguous dates and dollar
  currency codes remain unconfirmed rather than guessed.
- macOS OCR retains more scan resolution and uses overlapping strip passes to
  fill text regions missed by the initial page pass, without replacing numbers
  to make the arithmetic balance.
- **Paste invoice text** and **Manual entry** remain available if OCR cannot run.

### Optional multimodal AI extraction

The OpenAI Responses API accepts rendered invoice page images and returns a
Pydantic `Invoice` object using Structured Outputs. Missing evidence stays null;
the prompt asks the model to preserve printed arithmetic errors rather than
correct them. Independent Python rules do the actual financial checks.

1. Copy `.env.example` to `.env` locally and set your own API key, or enter a key
   in the app's password field. Do not commit it or paste it into a public issue.
2. On the upload screen, open **Optional settings** and enable **Use cloud AI
   for complex layouts**. The configurable default is `gpt-4.1-mini`;
   choose a compatible vision model your API account can access.
3. Explicitly allow that invoice to be sent to OpenAI, then click **Check my invoice**.

Cloud AI is off by default and hidden inside optional settings. Sample buttons
always use the local reader, even when cloud AI is selected for uploads.

The application does not make a paid request automatically, retries are disabled,
and requests use `store=False`. Image transmission still leaves the computer;
this setting is not a guarantee of zero provider retention. A ChatGPT subscription
and API billing are separate products. Use synthetic documents for demonstrations.

The live paid API path requires the user's own key and account credit. Unit tests
mock that boundary; no live API accuracy or cost result is claimed in this repo.

Official references:
- [Images and vision](https://developers.openai.com/api/docs/guides/images-vision)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

## Verification rules

### Currency identification and display

The reader detects supported printed ISO codes, currency names and symbols.
Examples: `₹` / `INR` / “Indian rupees”, `€` / `EUR` / “euros”, and `US$` / `USD`
/ “US dollars”. Amounts, items and totals show the detected symbol and the
currency name/code. CSV and JSON retain both code and symbol as separate fields.

A bare `$` is displayed as dollars, without guessing USD versus CAD/AUD/etc.
Likewise, bare `Rs` and `¥` need a specific code. A small optional currency picker
lets the reviewer confirm the code. Conflicting currency evidence blocks amount
comparison until resolved; the application does not convert between currencies.
Codes, names and symbols are supported for the currencies listed in
`invoice_assistant/currency.py`; this is not an all-currency/all-language guarantee.

See [Résumé feature audit](docs/RESUME_AUDIT.md) for the implementation status of
the project bullets and the distinction between local OCR and optional vision AI.

The checker uses `Decimal`, with `ROUND_HALF_UP`, and rounds each line before
summing. Most currencies use two decimal places; JPY uses zero and KWD/BHD three.

```text
line amount = quantity × unit price
subtotal = sum(calculated line amounts)
expected total = subtotal + document tax + shipping − document discount
difference = printed invoice total − expected total
```

It checks line amounts, subtotal and invoice total independently. A wrong printed
line total cannot hide inside a matching wrong subtotal. Missing identifiers and
dates, invalid dates, missing charges and empty line amounts are surfaced. Missing
optional charges are explicitly flagged as assumed zero rather than silently
accepted. Invalid, negative, non-finite and oversized numeric inputs are rejected.

For rows with an explicit VAT rate and gross amount, the checker also compares
net × (1 + VAT rate) with the printed gross and sums the printed gross amounts.
Differences of one minor currency unit per affected line are **review warnings**,
not silently accepted tolerances: the supplier's tax-rounding policy is unknown.
Larger differences remain errors. Original printed values are retained.

Unreadable/missing amounts produce **Reading incomplete**, not a claim that the
invoice is incorrect. The UI distinguishes extraction problems, confirmed
arithmetic mismatches, and matching totals with details left to confirm.

Arithmetic passing does **not** establish that the goods, vendor, tax treatment
or invoice are genuine. Extraction can be wrong even when JSON is well formed.

## Human review and exports

- Review changes are saved explicitly before recalculation.
- Changing the invoice/source or reviewer clears the previous approval.
- Errors block the **Mark reviewed** action; warnings need human acknowledgement.
- Draft exports remain possible and are labeled `draft`.
- JSON includes source filename and SHA-256, extraction method, invoice data,
  findings, expected/actual amounts, export time and self-reported review status.
- CSV includes one row per item and escapes formula-like text to reduce
  spreadsheet formula injection.
- Uploads are held in session memory. OCR temporary images are deleted when the
  OCR call ends. No invoice database or persistent upload archive is created.
- Reviewer identity is not authenticated; this is a portfolio review workflow,
  not an enterprise audit/approval system.

## Tests and evaluation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/evaluate_samples.py
```

Tests cover decimal arithmetic, incorrect line/subtotals, tax/discount/shipping,
missing and invalid values, upload checks, text extraction, exports, mocked AI
requests, and Streamlit review flows. The evaluation script reports results on
the included **small synthetic fixture set only**, not real-world accuracy.

The GitHub Actions workflow runs the portable tests on Python 3.12. macOS native
OCR is tested separately on a Mac; it is not a Linux CI capability.

## Project map

```text
app.py                      Streamlit application
assets/style.css            Responsive upload and results interface
main.py                     Original terminal learning exercise (preserved)
invoice_assistant/
  models.py                 Invoice and line-item schema
  documents.py              PDF/image reading and local OCR
  parser.py                 Local text extraction baseline
  ai.py                     Optional vision-model integration
  validation.py             Independent Decimal checks
  presentation.py           Plain-language reading/mismatch/review states
  currency.py               Currency evidence, ambiguity and amount display
  exports.py                CSV/JSON review records
scripts/
  ocr_macos.swift           Native Apple Vision OCR
  generate_samples.py       Synthetic invoice generation
  evaluate_samples.py       Reproducible fixture evaluation
samples/                    Synthetic PDFs, scan, text and expected values
tests/                      Unit, integration and UI-flow tests
docs/                       Demo and implementation notes
```

## Current scope and limitations

- One invoice per upload, at most five pages, 10 MB and 25 megapixels per image.
- Ordinary invoices with exclusive document-level tax, shipping and discount,
  plus explicit net/VAT/gross item tables with a printed tax summary.
- Credit notes, tax-inclusive unit pricing, per-line discounts, currency conversion,
  duplicate invoices and bank/vendor verification are outside the implemented rules.
- The local baseline targets English labels and simple tables; it is not a
  general document-understanding model.
- No measured real-world accuracy, production certification or employer deployment
  is claimed. Add a labeled, permission-cleared real-world test set before making
  stronger extraction claims.

See [Validation notes](docs/VALIDATION.md) for the supplied batch regression and
its limits. No supplied invoice images, OCR caches, tax IDs or bank details are
included in the repository.
- API keys and invoice content must not be placed in GitHub. The default app binds
  only to localhost. Deploying publicly needs authentication, rate limits,
  retention controls and a separate security review.

## GitHub publication

This folder contains a `.gitignore`, tests, synthetic samples and a CI workflow.
Publish the code and synthetic samples, not the virtual environment, `.env`,
personal invoices, export files or local caches. Keep the repository private
until its contents and intended visibility have been reviewed.
