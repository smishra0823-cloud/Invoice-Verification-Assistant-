from types import SimpleNamespace

import pytest

from invoice_assistant.ai import AIExtractionError, extract_with_ai
from invoice_assistant.documents import InvoiceDocument
from invoice_assistant.models import Invoice


def test_missing_key_never_makes_request():
    with pytest.raises(AIExtractionError, match="API key"):
        extract_with_ai(InvoiceDocument("demo", [b"image"], [""]), "", "gpt-4.1-mini")


def test_structured_vision_request(monkeypatch):
    import openai

    calls = {}

    class FakeClient:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.responses = self

        def parse(self, **kwargs):
            calls["parse"] = kwargs
            return SimpleNamespace(output_parsed=Invoice(vendor_name="Test"), usage=SimpleNamespace(total_tokens=42), id="test-request")

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    invoice, meta = extract_with_ai(InvoiceDocument("demo", [b"image"], [""]), "test-only-key", "vision-model")
    assert invoice.vendor_name == "Test"
    assert meta["tokens"] == 42
    assert calls["parse"]["store"] is False
    assert calls["parse"]["text_format"] is Invoice
    assert calls["parse"]["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")
    assert calls["client"]["max_retries"] == 0


def test_no_structured_output_is_handled(monkeypatch):
    import openai

    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: SimpleNamespace(responses=SimpleNamespace(parse=lambda **kwargs: SimpleNamespace(output_parsed=None))))
    with pytest.raises(AIExtractionError, match="no usable"):
        extract_with_ai(InvoiceDocument("demo", [b"image"], [""]), "test-only-key", "vision-model")
