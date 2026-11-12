"""Streamlit entry point: python -m streamlit run app.py."""

import hashlib
import os
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from invoice_assistant.ai import AIExtractionError, extract_with_ai
from invoice_assistant.documents import DocumentError, local_text, read_document
from invoice_assistant.exports import csv_bytes, export_record, json_bytes
from invoice_assistant.models import Invoice, LineItem
from invoice_assistant.parser import parse_invoice_text
from invoice_assistant.validation import validate_invoice

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
st.set_page_config(page_title="InvoiceLens · Invoice Verification", page_icon="📑", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1280px; padding-top: 2.5rem;}
h1 {letter-spacing: -.04em;} h2 {letter-spacing: -.025em;}
[data-testid="stMetric"] {background: white; padding: 1rem 1.2rem; border: 1px solid #DCE5E8; border-radius: 12px;}
[data-testid="stSidebar"] {border-right: 1px solid #DCE5E8;}
</style>""", unsafe_allow_html=True)


def clear_result():
    for key in ("invoice", "source", "source_images", "raw_text", "approved", "reviewer", "approved_reviewer"):
        st.session_state.pop(key, None)
    st.session_state["revision"] = st.session_state.get("revision", 0) + 1


def remember(invoice, source, images=None, text=""):
    clear_result()
    st.session_state.update(invoice=invoice.model_dump(), source=source, source_images=images or [], raw_text=text, approved=False)


with st.sidebar:
    st.markdown("### InvoiceLens")
    st.caption("Extract → Review → Verify → Export")
    source_choice = st.selectbox("Choose an invoice", ["Demo: matching invoice", "Demo: total mismatch", "Demo: scanned invoice", "Upload a document", "Paste invoice text", "Manual entry"])
    method = st.radio("Extraction", ["Local / no API key", "AI vision / OpenAI"])
    api_key, model, consent = "", "", False
    if method == "AI vision / OpenAI":
        st.caption("AI vision sends invoice page images to OpenAI. API usage may incur charges. No request runs until you give consent and click Extract.")
        api_key = st.text_input("OpenAI API key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
        model = st.text_input("Vision model", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
        consent = st.checkbox("Allow this invoice to be sent to OpenAI")
    else:
        st.caption("Text PDFs are read locally. Scans use Apple Vision on macOS, or Tesseract if installed. The rule parser is a baseline and may need corrections.")
    st.divider()
    st.markdown("**Document limits**")
    st.caption("One invoice · up to 5 pages · 10 MB\n\nPDF, PNG or JPEG")
    if st.button("Clear invoice and review", width="stretch"):
        clear_result()
        st.rerun()

st.caption("DOCUMENT INTELLIGENCE / PORTFOLIO PROTOTYPE")
st.title("Every invoice deserves a second look.")
st.write("Turn invoice pages into structured data, check the arithmetic, and review the evidence before exporting.")

file_data, file_name, pasted = None, "", ""
if source_choice.startswith("Demo:"):
    sample_name = {
        "Demo: matching invoice": "matching_invoice.pdf",
        "Demo: total mismatch": "mismatch_invoice.pdf",
        "Demo: scanned invoice": "scanned_invoice.png",
    }[source_choice]
    sample = ROOT / "samples" / sample_name
    if not sample.exists():
        st.error("Sample documents are missing. Run: python scripts/generate_samples.py")
        st.stop()
    file_data, file_name = sample.read_bytes(), sample.name
elif source_choice == "Upload a document":
    uploaded = st.file_uploader("Upload one invoice", type=["pdf", "png", "jpg", "jpeg"])
    if uploaded:
        file_data, file_name = uploaded.getvalue(), uploaded.name
elif source_choice == "Paste invoice text":
    pasted = st.text_area("Paste invoice text", height=180, placeholder="Vendor: ABC Supplies\nInvoice No: INV-001\n...")

source_id = hashlib.sha256((source_choice + method + model + pasted + file_name).encode() + (file_data or b"")).hexdigest()
if st.session_state.get("active_source") != source_id:
    clear_result()
    st.session_state["active_source"] = source_id

disabled = not (file_data or pasted.strip() or source_choice == "Manual entry")
if method == "AI vision / OpenAI" and source_choice not in ("Manual entry", "Paste invoice text"):
    disabled = disabled or not (api_key.strip() and model.strip() and consent)

button_label = "Start manual review" if source_choice == "Manual entry" else "Extract invoice"
if st.button(button_label, type="primary", disabled=disabled):
    try:
        with st.spinner("Reading your invoice…"):
            meta = {"filename": file_name or source_choice, "sha256": hashlib.sha256(file_data or pasted.encode()).hexdigest()}
            images, text = [], ""
            if source_choice == "Manual entry":
                invoice = Invoice(line_items=[LineItem()], notes=["Entered manually; no model extraction."])
                meta["method"] = "manual"
            elif source_choice == "Paste invoice text":
                invoice = parse_invoice_text(pasted)
                text, meta["method"] = pasted, "pasted text / rules"
            else:
                document = read_document(file_name, file_data)
                images = document.images
                if method == "AI vision / OpenAI":
                    invoice, usage = extract_with_ai(document, api_key, model)
                    meta.update(method="OpenAI vision", **usage)
                else:
                    text, mode = local_text(document)
                    invoice = parse_invoice_text(text)
                    meta["method"] = mode + " / rules"
            remember(invoice, meta, images, text)
    except (DocumentError, AIExtractionError, ValueError) as error:
        st.error(str(error))

if "invoice" not in st.session_state:
    st.info("Start with the matching demo, then try the mismatch or scanned version. No API key is needed for local mode.")
    st.markdown("#### What gets checked")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**Line arithmetic**\n\nQuantity × unit price, independently recalculated with Decimal.")
    c2.markdown("**Invoice totals**\n\nSubtotal + document tax + shipping − discount, compared with the printed total.")
    c3.markdown("**Missing evidence**\n\nMissing fields, invalid numbers and dates are surfaced for human review.")
    st.stop()

invoice = Invoice.model_validate(st.session_state["invoice"])
source = st.session_state["source"]
st.caption(f"Source: {source['filename']} · Extraction: {source['method']}")
left, right = st.columns([1, 1.3], gap="large")
with left:
    st.subheader("1. Compare with the source")
    images = st.session_state["source_images"]
    if images:
        page_index = st.selectbox("Page", list(range(len(images))), format_func=lambda value: f"Page {value + 1}")
        st.image(images[page_index], width="stretch")
    else:
        st.caption("Use the original document alongside the form.")
    with st.expander("Extracted text and extraction notes"):
        st.code(st.session_state.get("raw_text") or "Image-to-schema extraction or manual entry; no OCR text.", language=None)
        for note in invoice.notes:
            st.write("• " + note)

with right:
    st.subheader("2. Review the extracted fields")
    st.caption("Correct any field, add or remove line items, then save to recalculate. Numeric fields accept decimals; dates use YYYY-MM-DD.")
    revision = st.session_state.get("revision", 0)
    with st.form(f"invoice_review_{revision}"):
        row1 = st.columns(2)
        vendor = row1[0].text_input("Vendor", value=invoice.vendor_name or "")
        invoice_number = row1[1].text_input("Invoice number", value=invoice.invoice_number or "")
        row2 = st.columns(3)
        invoice_date = row2[0].text_input("Invoice date", value=invoice.invoice_date or "")
        due_date = row2[1].text_input("Due date (optional)", value=invoice.due_date or "")
        currency = row2[2].text_input("Currency", value=invoice.currency or "", placeholder="INR")
        frame = pd.DataFrame([item.model_dump() for item in invoice.line_items], columns=["description", "quantity", "unit_price", "line_total"]).fillna("")
        edited = st.data_editor(frame, num_rows="dynamic", hide_index=True, width="stretch",
            column_config={"description": st.column_config.TextColumn("Description", width="large"), "quantity": "Quantity", "unit_price": "Unit price", "line_total": "Printed amount"},
            key=f"line_editor_{revision}")
        totals = {}
        for cols, names in ((st.columns(3), ("subtotal", "tax_total", "shipping")), (st.columns(2), ("discount", "total"))):
            for col, name in zip(cols, names):
                totals[name] = col.text_input(name.replace("_", " ").title(), value=getattr(invoice, name) or "")
        saved = st.form_submit_button("Save edits and verify", type="primary", width="stretch")
    if saved:
        records = edited.fillna("").astype(str).to_dict("records")
        records = [row for row in records if any(value.strip() for value in row.values())]
        invoice = Invoice(vendor_name=vendor.strip() or None, invoice_number=invoice_number.strip() or None,
            invoice_date=invoice_date.strip() or None, due_date=due_date.strip() or None, currency=currency.strip().upper() or None,
            line_items=[LineItem(**{k: (v.strip() or None) if k != "description" else v.strip() for k, v in row.items()}) for row in records],
            notes=invoice.notes, **{name: value.strip() or None for name, value in totals.items()})
        st.session_state.update(invoice=invoice.model_dump(), approved=False)
        st.success("Saved. The checks below use your latest values.")

st.divider()
st.subheader("3. Verification results")
report = validate_invoice(invoice)
cols = st.columns(4)
cols[0].metric("Calculated total", report.calculated_total or "—")
cols[1].metric("Invoice total", report.stated_total or "—")
cols[2].metric("Difference", report.difference or "—")
cols[3].metric("Findings", f"{report.error_count} errors · {report.warning_count} warnings")
if report.error_count:
    st.error(report.status + ". Correct the flagged values and save the form before marking the invoice reviewed.")
elif report.warning_count:
    st.warning("Review required. Confirm missing fields and assumptions against the original invoice.")
else:
    st.success("Arithmetic checks passed. Review the extracted details against the document before exporting.")
if report.issues:
    st.dataframe(pd.DataFrame([asdict(issue) for issue in report.issues]), hide_index=True, width="stretch")
with st.expander("Show independently calculated line amounts"):
    st.dataframe(pd.DataFrame(report.line_calculations), hide_index=True, width="stretch")

st.subheader("4. Review and export")
st.caption("Exports are marked draft until reviewed. Editing the invoice clears the approval. Reviewer names are self-reported; this prototype does not authenticate reviewers.")
reviewer = st.text_input("Reviewer name", key="reviewer")
if st.session_state.get("approved_reviewer") != reviewer:
    st.session_state["approved"] = False
ack = st.checkbox("I compared the saved fields with the source and reviewed all warnings.")
if st.button("Mark reviewed", disabled=bool(report.error_count) or not reviewer.strip() or not ack):
    st.session_state["approved"] = True
    st.session_state["approved_reviewer"] = reviewer
approved = st.session_state.get("approved", False)
if approved:
    st.success(f"Marked reviewed by {reviewer}.")
record = export_record(invoice, report, source, reviewer, approved)
label = "reviewed" if approved else "draft"
downloads = st.columns(2)
downloads[0].download_button(f"Download {label} CSV", data=csv_bytes(record), file_name=f"invoice_{label}.csv", mime="text/csv", width="stretch")
downloads[1].download_button(f"Download {label} JSON report", data=json_bytes(record), file_name=f"invoice_{label}.json", mime="application/json", width="stretch")
st.caption("Prototype scope: ordinary invoices with exclusive document-level tax, shipping and discount. Credit notes, inclusive/per-line tax and per-line discounts require additional validation. API extraction can be wrong even when its JSON is valid.")
