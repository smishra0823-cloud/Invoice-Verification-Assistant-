"""InvoiceLens: upload, check, download. Run with Streamlit."""

import hashlib
import html
import os
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
st.set_page_config(page_title="InvoiceLens · Clear invoice checks", page_icon="📄", layout="wide")
st.markdown(f"<style>{(ROOT / 'assets/style.css').read_text()}</style>", unsafe_allow_html=True)


def clear_result():
    for key in ("invoice", "source", "source_images", "raw_text", "approved", "reviewer", "approved_reviewer", "review_ack"):
        st.session_state.pop(key, None)
    st.session_state["revision"] = st.session_state.get("revision", 0) + 1


def start_over():
    clear_result()
    st.session_state["upload_revision"] = st.session_state.get("upload_revision", 0) + 1


def scan_invoice(name, data=None, text="", manual=False, cloud=False, api_key="", model="", consent=False):
    """An explicit scan or sample action is required before any processing."""
    try:
        if cloud and not manual and not text and not (api_key.strip() and model.strip() and consent):
            st.warning("Add your key and permission in Optional settings, or turn cloud AI off to read the invoice on this computer.")
            return
        with st.spinner("Reading your invoice and checking the amounts…"):
            meta = {"filename": name, "sha256": hashlib.sha256(data or text.encode()).hexdigest()}
            images = []
            if manual:
                invoice = Invoice(line_items=[LineItem()], notes=["Entered manually; no model extraction."])
                meta["method"] = "manual"
            elif text:
                invoice = parse_invoice_text(text)
                meta["method"] = "pasted text / rules"
            else:
                document = read_document(name, data)
                images = document.images
                if cloud:
                    invoice, usage = extract_with_ai(document, api_key, model)
                    meta.update(method="OpenAI vision", **usage)
                else:
                    text, mode = local_text(document)
                    invoice = parse_invoice_text(text)
                    meta["method"] = mode + " / rules"
            clear_result()
            st.session_state.update(invoice=invoice.model_dump(), source=meta, source_images=images, raw_text=text, approved=False)
        st.rerun()
    except (DocumentError, AIExtractionError, ValueError) as error:
        st.error(str(error))
        st.caption("Try another file, paste the invoice text, or enter the details below.")


def sample_invoice(filename):
    path = ROOT / "samples" / filename
    if path.exists():
        # Samples always run locally; trying an example never incurs API charges.
        scan_invoice(path.name, path.read_bytes())
    else:
        st.error("This sample is unavailable. Please upload an invoice instead.")


def detail(label, value):
    st.markdown(f'<div class="detail"><span>{html.escape(label)}</span><strong>{html.escape(value or "Not found")}</strong></div>', unsafe_allow_html=True)


def footer():
    st.markdown('<div class="footer"><span>InvoiceLens</span><span>A little clarity for every invoice.</span></div>', unsafe_allow_html=True)


has_invoice = "invoice" in st.session_state
st.markdown('<div class="masthead"><div class="brand"><span class="brand-icon">i<span>✓</span></span>InvoiceLens<span class="brand-dot">.</span></div><span class="nav-label">INVOICE VERIFICATION</span></div>', unsafe_allow_html=True)
if not has_invoice:
    st.markdown('<div class="hero"><div class="eyebrow">LESS ADMIN. MORE CONFIDENCE.</div><h1>Invoice checks.<br><span class="hero-accent">Beautifully simple.</span></h1><p>Upload your invoice. Find mismatched amounts.<br>Leave with a clear, organised report.</p></div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="results-heading"><div class="eyebrow">YOUR INVOICE, AT A GLANCE</div><h1>A clearer picture.</h1><p>Here’s what we read and what needs your attention.</p></div>', unsafe_allow_html=True)
st.markdown(f'<div class="steps"><div class="step {"done" if has_invoice else "active"}"><b>{"✓" if has_invoice else "1"}</b><span>Upload invoice</span></div><i></i><div class="step {"active" if has_invoice else ""}"><b>2</b><span>Check the details</span></div><i></i><div class="step"><b>3</b><span>Download report</span></div></div>', unsafe_allow_html=True)

if not has_invoice:
    upload_col, sample_col = st.columns([1.45, 1], gap="large")
    with upload_col, st.container(border=True, key="upload_card"):
        st.markdown('<div class="section-kicker">START HERE</div>', unsafe_allow_html=True)
        st.subheader("Upload your invoice")
        st.write("Choose a PDF or a clear photo to get started.")
        upload = st.file_uploader("Choose an invoice", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed", key=f"upload_{st.session_state.get('upload_revision', 0)}")
        st.caption("PDF, JPG or PNG · up to 10 MB · 5 pages maximum")
        cloud, api_key, model, consent = False, "", "", False
        with st.expander("Optional settings"):
            st.caption("The standard reader works on this computer. No account or API key is needed.")
            cloud = st.checkbox("Use cloud AI for complex layouts", key="cloud_mode")
            if cloud:
                st.info("This sends invoice images to OpenAI and may incur API charges. It runs only when you click Check my invoice.")
                api_key = st.text_input("OpenAI API key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
                model = st.text_input("Model", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
                consent = st.checkbox("Allow this invoice to be sent to OpenAI")
        if st.button("Check my invoice", type="primary", width="stretch", disabled=upload is None):
            scan_invoice(upload.name, upload.getvalue(), cloud=cloud, api_key=api_key, model=model, consent=consent)
        st.markdown(f'<div class="privacy-note">{"Cloud AI selected · requires permission before sending" if cloud else "✓ Read on your computer · no cloud upload"}</div>', unsafe_allow_html=True)
    with sample_col, st.container(border=True, key="sample_card"):
        st.markdown('<div class="section-kicker">JUST EXPLORING?</div>', unsafe_allow_html=True)
        st.subheader("Try it with a sample")
        st.write("See the results without uploading a file.")
        st.markdown('<div class="sample-art"><div class="sample-sheet"><div class="sheet-top"><b>INVOICE</b><span>DEMO–001</span></div><div class="sheet-line long"></div><div class="sheet-line short"></div><div class="sheet-table"><span>Notebook</span><span>151.00</span><span>Pen set</span><span>60.00</span></div><div class="sheet-total"><span>Total · INR</span><b>253.98</b></div></div><div class="sample-stamp">✓ Amounts match</div></div>', unsafe_allow_html=True)
        if st.button("Try a matching invoice", width="stretch"):
            sample_invoice("matching_invoice.pdf")
        samples = st.columns(2)
        if samples[0].button("Find a mismatch", width="stretch"):
            sample_invoice("mismatch_invoice.pdf")
        if samples[1].button("Try a scan", width="stretch"):
            sample_invoice("scanned_invoice.png")
        st.caption("Fictional examples. No real customer information.")
    with st.expander("Have invoice text instead? Or enter details yourself"):
        text = st.text_area("Paste invoice text", height=140, placeholder="Vendor: ABC Supplies\nInvoice No: INV-001\n...")
        extra = st.columns(2)
        if extra[0].button("Check pasted text", disabled=not text.strip(), width="stretch"):
            scan_invoice("Pasted invoice text", text=text)
        if extra[1].button("Enter details manually", width="stretch"):
            scan_invoice("Manual entry", manual=True)
    st.markdown('<div class="benefits"><div><span>01 / READ</span><h3>The details, in one place.</h3><p>Supplier, dates and line items organised into a readable summary.</p></div><div><span>02 / CHECK</span><h3>Small errors, spotted.</h3><p>Item amounts and totals recalculated, with differences clearly flagged.</p></div><div><span>03 / KEEP</span><h3>Ready for your next step.</h3><p>Review the details and download a spreadsheet or detailed report.</p></div></div>', unsafe_allow_html=True)
    with st.expander("What can this tool check?"):
        st.write("It checks quantities × prices, subtotal, tax, shipping, discount and the final total. Missing or unreadable details are flagged for review. Always compare the details with your original invoice.")
        st.caption("Best for ordinary invoices with tax shown separately. Credit notes, tax-inclusive prices and tax or discounts on individual items need additional checks. The local reader may need corrections for unfamiliar layouts.")
    footer()
    st.stop()

invoice = Invoice.model_validate(st.session_state["invoice"])
source = st.session_state["source"]
report = validate_invoice(invoice)
top = st.columns([3, 1])
top[0].caption(f"CURRENT DOCUMENT  /  {source['filename']}")
if top[1].button("Check another invoice", width="stretch"):
    start_over()
    st.rerun()
if report.error_count:
    tone, title = "correction", "Some amounts need a second look"
    subtitle = f"We found {report.error_count} issue{'s' if report.error_count != 1 else ''} to correct. Compare the details below with your invoice."
elif report.warning_count:
    tone, title = "attention", "A few details need your review"
    subtitle = "Some fields are missing or need confirmation. Check the notes below before marking this reviewed."
else:
    tone, title = "matched", "The amounts add up"
    subtitle = "The arithmetic checks passed. Please confirm that the extracted details match your original."
st.markdown(f'<div class="result-banner {tone}"><div class="result-symbol">{"!" if report.issues else "✓"}</div><div><strong>{title}</strong><p>{subtitle}</p></div></div>', unsafe_allow_html=True)
metrics = st.columns(3)
metrics[0].metric("Total on invoice", report.stated_total or "Not found")
metrics[1].metric("Recalculated total", report.calculated_total or "Needs details")
metrics[2].metric("Difference", report.difference or "Not available")
st.caption(f"Amounts in {invoice.currency or 'the invoice currency'}. Difference = invoice total − recalculated total.")
if report.issues:
    with st.expander(f"What needs attention ({len(report.issues)})", expanded=True):
        for issue in report.issues:
            field = issue.field.replace("_", " ")
            message = f"**{field.title()}** — {issue.message}"
            if issue.expected:
                message += f" Expected: **{issue.expected}**."
            if issue.actual:
                message += f" Read: **{issue.actual}**."
            (st.error if issue.severity == "ERROR" else st.warning)(message)

left, right = st.columns([1, 1.25], gap="large")
with left, st.container(border=True, key="original_card"):
    st.markdown('<div class="section-kicker">THE ORIGINAL</div>', unsafe_allow_html=True)
    st.subheader("Your invoice")
    images = st.session_state["source_images"]
    if images:
        page_index = 0
        if len(images) > 1:
            page_index = st.selectbox("Page", list(range(len(images))), format_func=lambda value: f"Page {value + 1}")
        st.image(images[page_index], width="stretch")
    elif st.session_state.get("raw_text"):
        st.text(st.session_state["raw_text"])
    else:
        st.info("You’re entering this invoice manually. Keep your original nearby.")
    with st.expander("How this was read"):
        st.caption(f"Reader: {source['method']}")
        for note in invoice.notes:
            st.write(note)
        if st.session_state.get("raw_text") and images:
            st.text(st.session_state["raw_text"])
with right, st.container(border=True, key="details_card"):
    st.markdown('<div class="section-kicker">THE DETAILS</div>', unsafe_allow_html=True)
    st.subheader("Everything in one place")
    info = st.columns(2)
    with info[0]:
        detail("Supplier", invoice.vendor_name)
        detail("Invoice date", invoice.invoice_date)
    with info[1]:
        detail("Invoice number", invoice.invoice_number)
        detail("Due date", invoice.due_date or "Not stated")
    st.markdown("#### Items")
    frame = pd.DataFrame([item.model_dump() for item in invoice.line_items], columns=["description", "quantity", "unit_price", "line_total"]).fillna("")
    st.dataframe(frame.rename(columns={"description": "Description", "quantity": "Qty", "unit_price": "Unit price", "line_total": "Amount"}), hide_index=True, width="stretch")
    summary = ""
    for label, value in (("Subtotal", invoice.subtotal), ("Tax", invoice.tax_total), ("Shipping", invoice.shipping), ("Discount", invoice.discount)):
        summary += f'<div class="total-row"><span>{label}</span><span>{html.escape(value or "Not stated")}</span></div>'
    st.markdown(f'<div class="totals">{summary}<div class="total-row final-total"><strong>Invoice total <small>{html.escape(invoice.currency or "")}</small></strong><strong>{html.escape(invoice.total or "Not found")}</strong></div></div>', unsafe_allow_html=True)
    with st.expander("Something looks wrong? Edit the details", expanded=source["method"] == "manual"):
        st.caption("Edit and save to recheck. Dates: YYYY-MM-DD. Amounts: 150.00.")
        revision = st.session_state.get("revision", 0)
        with st.form(f"invoice_review_{revision}"):
            row1 = st.columns(2)
            vendor = row1[0].text_input("Supplier", value=invoice.vendor_name or "")
            invoice_number = row1[1].text_input("Invoice number", value=invoice.invoice_number or "")
            row2 = st.columns(3)
            invoice_date = row2[0].text_input("Invoice date", value=invoice.invoice_date or "")
            due_date = row2[1].text_input("Due date", value=invoice.due_date or "")
            currency = row2[2].text_input("Currency", value=invoice.currency or "", placeholder="INR")
            edited = st.data_editor(frame, num_rows="dynamic", hide_index=True, width="stretch", column_config={"description": st.column_config.TextColumn("Description", width="large"), "quantity": "Qty", "unit_price": "Unit price", "line_total": "Amount"}, key=f"line_editor_{revision}")
            totals = {}
            for cols, names in ((st.columns(3), ("subtotal", "tax_total", "shipping")), (st.columns(2), ("discount", "total"))):
                for col, name in zip(cols, names):
                    totals[name] = col.text_input(name.replace("_", " ").title(), value=getattr(invoice, name) or "")
            saved = st.form_submit_button("Save changes and recheck", type="primary", width="stretch")
        if saved:
            records = edited.fillna("").astype(str).to_dict("records")
            records = [row for row in records if any(value.strip() for value in row.values())]
            updated = Invoice(vendor_name=vendor.strip() or None, invoice_number=invoice_number.strip() or None, invoice_date=invoice_date.strip() or None, due_date=due_date.strip() or None, currency=currency.strip().upper() or None, line_items=[LineItem(**{k: (v.strip() or None) if k != "description" else v.strip() for k, v in row.items()}) for row in records], notes=invoice.notes, **{name: value.strip() or None for name, value in totals.items()})
            st.session_state.update(invoice=updated.model_dump(), approved=False, review_ack=False)
            st.rerun()

st.markdown('<div class="download-intro"><div class="section-kicker">YOUR NEXT STEP</div><h2>Take the results with you.</h2><p>Download a spreadsheet for everyday use, or keep a detailed report.</p></div>', unsafe_allow_html=True)
with st.container(border=True, key="download_card"):
    with st.expander("Mark as reviewed (optional)"):
        st.caption("Compare the saved details with the original first. Changes clear this status. The reviewer name is self-reported.")
        reviewer = st.text_input("Reviewer name", key="reviewer")
        if st.session_state.get("approved_reviewer") != reviewer:
            st.session_state["approved"] = False
        ack = st.checkbox("I compared the details with the original and checked all notes.", key="review_ack")
        if st.button("Mark reviewed", disabled=bool(report.error_count) or not reviewer.strip() or not ack):
            st.session_state.update(approved=True, approved_reviewer=reviewer)
        if report.error_count:
            st.caption("Correct the flagged amounts first. You can still download a draft.")
    approved = st.session_state.get("approved", False)
    reviewer = st.session_state.get("reviewer", "")
    if approved:
        st.success(f"Marked reviewed by {reviewer}.")
    else:
        st.caption("DRAFT · Download now, or mark as reviewed above after checking the original.")
    record = export_record(invoice, report, source, reviewer, approved)
    label = "reviewed" if approved else "draft"
    downloads = st.columns(2)
    downloads[0].download_button("Download spreadsheet (CSV)", data=csv_bytes(record), file_name=f"invoice_{label}.csv", mime="text/csv", type="primary", width="stretch")
    downloads[1].download_button("Download detailed report (JSON)", data=json_bytes(record), file_name=f"invoice_{label}.json", mime="application/json", width="stretch")
with st.expander("About these checks"):
    st.write("Quantities × prices are recalculated independently, then tax and shipping are added and discount subtracted. Matching amounts confirm the arithmetic; they do not confirm the supplier or whether an invoice is genuine.")
    st.dataframe(pd.DataFrame(report.line_calculations), hide_index=True, width="stretch")
    st.caption("Portfolio prototype for ordinary invoices with separately stated document-level tax. Credit notes, inclusive/per-item tax and per-item discounts need additional validation. Always compare with the original.")
footer()
