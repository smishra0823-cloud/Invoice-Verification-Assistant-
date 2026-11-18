# Simple interview demo

## Before the interview

In VS Code, choose **Terminal → Run Task → Check interview demo**.
This reads the actual sample PDFs and scan, checks the expected calculations,
and checks exports. It runs locally without an API key or paid request.

Then choose **Terminal → Run Task → Run InvoiceLens**. Open the URL printed
in Terminal. On this Mac the project is configured for <http://127.0.0.1:8502>.
Alternatively run `zsh run.command`; it checks the PDF demos before launching.
If the app is already running, use its existing browser tab rather than starting
a second server. Stop a running server with Control+C in its Terminal.

## Demonstrate three things

1. **Try a matching invoice.** Total and calculated total are **₹253.98**;
   the difference is **₹0.00**. Show the extracted items and currency.
2. **Check another invoice → Find a mismatch.** Printed total is **₹260.98**;
   calculated total remains **₹253.98**. The app flags a **₹7.00** difference.
   Open Edit the details, correct the total and save to show recalculation.
3. **Try a scan** or upload a clear supported invoice. Show its original next
   to the extracted fields, then download the spreadsheet or detailed report.

The examples are labeled fictional samples. Do not present them as proof that
all unseen invoices work perfectly. Do not edit an incorrect total automatically
just to make the check pass.

## Explain the result simply

- **The amounts add up:** read values reconcile. Currency/date/assumption notes
  can still need confirmation; they are not calculation failures.
- **Main total matches · rounding note:** the main total reconciles, while small
  item-level tax differences remain listed for review.
- **The amounts don't match:** a calculation disagrees with a saved amount.
- **Reading incomplete:** the app could not read enough evidence. Keep the
  original visible, correct missing fields and save. No false pass is issued.

The reviewer can confirm a specific currency when only an ambiguous symbol is
printed. A bare dollar sign is shown as dollars, without guessing its country.

## Three sentences to understand

“The local reader extracts invoice fields from PDF text or scanned images.
Python recalculates the amounts independently using Decimal and flags differences.
A person reviews the original and can correct the extracted fields before export.”

Optional vision-language extraction is implemented separately and requires an API
key, credit and consent. It has mocked integration tests, but no live paid-model
benchmark has been completed. The normal demo does not depend on that service.
