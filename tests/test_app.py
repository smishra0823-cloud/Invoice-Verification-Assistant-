from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_demo_review_and_approval():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    extract = next(button for button in app.button if button.label == "Try a matching invoice")
    extract.click().run()
    assert not app.exception
    assert any(metric.value == "253.98" for metric in app.metric)
    assert any("The amounts add up" in item.value for item in app.markdown)
    reviewer = next(widget for widget in app.text_input if widget.label == "Reviewer name")
    reviewer.set_value("Demo Reviewer").run()
    app.checkbox[0].check().run()
    next(button for button in app.button if button.label == "Mark reviewed").click().run()
    assert app.session_state["approved"] is True


def test_mismatch_blocks_approval():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(button for button in app.button if button.label == "Find a mismatch").click().run()
    assert not app.exception
    assert any(metric.value == "7.00" for metric in app.metric)
    assert next(button for button in app.button if button.label == "Mark reviewed").disabled


def test_new_source_clears_previous_review():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(button for button in app.button if button.label == "Try a matching invoice").click().run()
    next(button for button in app.button if button.label == "Check another invoice").click().run()
    assert "invoice" not in app.session_state
    assert not app.exception


def test_default_flow_requires_no_cloud_setup():
    app = AppTest.from_file(str(ROOT / "app.py")).run()
    assert not app.sidebar.children
    assert not app.text_input  # No API key or model field in the default flow.
    assert next(b for b in app.button if b.label == "Check my invoice").disabled
    next(b for b in app.button if b.label == "Try a matching invoice").click().run()
    assert app.session_state["source"]["method"] == "PDF text / rules"


def test_edit_clears_approval_and_rechecks_visible_totals():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(b for b in app.button if b.label == "Try a matching invoice").click().run()
    next(w for w in app.text_input if w.label == "Reviewer name").set_value("Demo Reviewer").run()
    app.checkbox[0].check().run()
    next(b for b in app.button if b.label == "Mark reviewed").click().run()
    assert app.session_state["approved"] is True
    next(w for w in app.text_input if w.label == "Total").set_value("260.98")
    next(b for b in app.button if b.label == "Save changes and recheck").click().run()
    assert not app.exception
    assert app.session_state["approved"] is False
    assert app.session_state["review_ack"] is False
    assert any(m.value == "7.00" for m in app.metric)
    assert next(b for b in app.button if b.label == "Mark reviewed").disabled


def test_cloud_selection_never_changes_free_sample_reader():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(w for w in app.checkbox if w.label == "Use cloud AI for complex layouts").check().run()
    next(b for b in app.button if b.label == "Try a matching invoice").click().run()
    assert not app.exception
    assert app.session_state["source"]["method"] == "PDF text / rules"


def test_manual_entry_and_pasted_text_remain_available():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(b for b in app.button if b.label == "Enter details manually").click().run()
    assert not app.exception
    assert app.session_state["source"]["method"] == "manual"
    next(b for b in app.button if b.label == "Check another invoice").click().run()
    app.text_area[0].set_value((ROOT / "samples/matching_invoice.txt").read_text())
    next(b for b in app.button if b.label == "Check pasted text").click().run()
    assert not app.exception
    assert any(m.value == "253.98" for m in app.metric)
