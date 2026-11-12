from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_demo_review_and_approval():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    app.button[0]  # Clear button appears first in the sidebar.
    extract = next(button for button in app.button if button.label == "Extract invoice")
    extract.click().run()
    assert not app.exception
    assert any(metric.value == "253.98" for metric in app.metric)
    assert any("Arithmetic checks passed" in success.value for success in app.success)
    reviewer = next(widget for widget in app.text_input if widget.label == "Reviewer name")
    reviewer.set_value("Demo Reviewer").run()
    app.checkbox[0].check().run()
    next(button for button in app.button if button.label == "Mark reviewed").click().run()
    assert app.session_state["approved"] is True


def test_mismatch_blocks_approval():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(widget for widget in app.selectbox if widget.label == "Choose an invoice").select("Demo: total mismatch").run()
    next(button for button in app.button if button.label == "Extract invoice").click().run()
    assert not app.exception
    assert any(metric.value == "7.00" for metric in app.metric)
    assert next(button for button in app.button if button.label == "Mark reviewed").disabled


def test_new_source_clears_previous_review():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    next(button for button in app.button if button.label == "Extract invoice").click().run()
    next(widget for widget in app.selectbox if widget.label == "Choose an invoice").select("Manual entry").run()
    assert "invoice" not in app.session_state
    assert not app.exception
