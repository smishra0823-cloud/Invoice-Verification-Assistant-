# Extraction regression — 12 November 2026

The original local reader was too narrow for net/VAT/gross tables. It confused
Tax ID with tax, did not understand decimal commas, included a summary row as
an item, and merged adjacent OCR description lines. These were extraction bugs,
not evidence that an invoice was incorrect.

## Checks performed

- 70 automated tests, including synthetic regressions for these failure modes.
- Local OCR and parsing of the 15 images supplied by the user, compared with
  visible item counts, net subtotals, printed VAT and final totals: 15/15 matched.
- 63 item quantity × net-price calculations reconciled with printed net amounts.
- All 15 main totals reconciled using the printed VAT; currency/date questions
  and observed tax-rounding differences remain explicit review warnings.
- Overlapping OCR strips recovered a previously missing small description.
- Real browser upload of the reported image, result presentation, edited-total
  mismatch detection, and incomplete-reading recovery were checked locally.

## Limits

This is a small batch with a shared layout, used to reproduce a user-reported
failure. It is not a random or independent benchmark and is not evidence of
100% general invoice extraction accuracy. Some product-description characters
are still imperfect OCR. Matching numbers do not establish invoice authenticity.
The local parser targets English labels; it does not claim all-language support.

A dollar symbol is not enough to select USD versus CAD/AUD. Slash dates such
as 04/09/2014 remain ambiguous. Small gross/VAT differences can depend on rounding
at item or document level; the app flags them for review and retains the evidence.

The supplied documents and full OCR output were kept locally and excluded from
GitHub. Public tests use synthetic content with fictional identifiers.

## Currency update — 18 November 2026

110 automated tests pass, including codes, names, symbols, ambiguous dollar/rupee/
yen symbols, conflicting currencies, identifier false positives, export metadata
and manual correction. Browser checks confirmed rupee and euro display, dollar
family display and explicit USD confirmation. Re-parsing the retained local OCR
for the previous 15 images preserved every main total comparison and identified
the printed dollar symbol. Currency display does not establish general OCR
accuracy, and no live vision-model call was made as part of this update.

## Offline interview-demo hardening — 18 November 2026

118 tests pass. Added explicit reordered table-column support, month-name dates,
unreadable-row warnings, preserved-source recovery when OCR is unavailable, and
separate arithmetic/review status in exports. Long item descriptions now wrap so
they do not hide the numeric columns. Non-critical metadata notes stay collapsed;
real mismatches and incomplete readings remain visible.

The offline preflight read the matching PDF, mismatching PDF and scanned sample
and checked CSV/JSON export. The 15 supplied images were read again with native
OCR: all expected item counts, net subtotals, printed tax and main totals still
matched, and all 63 net item calculations reconciled. Product-description OCR
can still contain character errors; this is not a guarantee for arbitrary files.
