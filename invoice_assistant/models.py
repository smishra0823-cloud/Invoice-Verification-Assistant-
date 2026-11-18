"""Shared extraction schema. Missing evidence remains null rather than guessed."""

from pydantic import BaseModel, ConfigDict, Field


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = ""
    quantity: str | None = None
    unit_price: str | None = None
    line_total: str | None = None
    tax_rate: str | None = None
    gross_total: str | None = None


class Invoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    currency_symbol: str | None = None
    currency_status: str = "unknown"
    currency_candidates: list[str] = Field(default_factory=list)
    currency_evidence: list[str] = Field(default_factory=list)
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: str | None = None
    tax_total: str | None = None
    discount: str | None = None
    shipping: str | None = None
    total: str | None = None
    notes: list[str] = Field(default_factory=list)
    reading_warnings: list[str] = Field(default_factory=list)
