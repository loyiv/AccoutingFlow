from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class PriceUpsertIn(BaseModel):
    book_id: str
    commodity_type: str = Field(default="CURRENCY", max_length=16)
    commodity_code: str = Field(min_length=1, max_length=32)
    currency_type: str = Field(default="CURRENCY", max_length=16)
    currency_code: str = Field(min_length=1, max_length=32)
    price_date: date
    value: Decimal
    source: str = Field(default="USER", max_length=32)
    type: str = Field(default="LAST", max_length=32)


class PriceOut(BaseModel):
    id: str
    book_id: str
    commodity_code: str
    currency_code: str
    price_date: date
    value: Decimal
    source: str
    type: str


class InvoiceLineIn(BaseModel):
    description: str = Field(default="", max_length=256)
    account_id: str
    quantity: Decimal = Field(default=1)
    unit_price: Decimal = Field(default=0)
    tax_rate: Decimal = Field(default=0)
    memo: str = Field(default="", max_length=256)


class InvoiceCreateIn(BaseModel):
    book_id: str
    period_id: str
    invoice_type: str = Field(pattern=r"^(AR|AP)$")
    doc_no: str = Field(default="", max_length=32)
    doc_date: datetime = Field(default_factory=datetime.utcnow)
    due_date: date | None = None
    party_id: str | None = None
    currency_type: str = Field(default="CURRENCY", max_length=16)
    currency_code: str = Field(default="CNY", max_length=32)
    notes: str = Field(default="", max_length=1024)
    lines: list[InvoiceLineIn]
    create_draft: bool = True


class InvoiceOut(BaseModel):
    id: str
    book_id: str
    invoice_type: str
    status: str
    doc_no: str
    doc_date: datetime
    due_date: date | None
    party_id: str | None
    currency_code: str
    notes: str
    total_net: Decimal
    total_tax: Decimal
    total_gross: Decimal
    posted_txn_id: str | None
    lot_id: str | None
    draft_id: str | None = None
    lines: list[dict[str, Any]] = Field(default_factory=list)


class PaymentApplyIn(BaseModel):
    invoice_id: str
    amount: Decimal


class PaymentCreateIn(BaseModel):
    book_id: str
    period_id: str
    payment_type: str = Field(pattern=r"^(RECEIPT|DISBURSEMENT)$")
    pay_date: datetime = Field(default_factory=datetime.utcnow)
    party_id: str | None = None
    currency_type: str = Field(default="CURRENCY", max_length=16)
    currency_code: str = Field(default="CNY", max_length=32)
    amount: Decimal = Field(default=0)
    cash_account_id: str
    method: str = Field(default="", max_length=32)
    reference_no: str = Field(default="", max_length=64)
    notes: str = Field(default="", max_length=512)
    applications: list[PaymentApplyIn] = Field(default_factory=list)
    create_draft: bool = True


class PaymentOut(BaseModel):
    id: str
    book_id: str
    payment_type: str
    status: str
    pay_date: datetime
    party_id: str | None
    currency_code: str
    amount: Decimal
    method: str
    reference_no: str
    notes: str
    txn_id: str | None
    draft_id: str | None = None
    applications: list[dict[str, Any]] = Field(default_factory=list)


class ApplyResultOut(BaseModel):
    invoice_id: str
    total_gross: Decimal
    applied_amount: Decimal
    outstanding_amount: Decimal
    status: str
    lot_closed: bool


class AgingItemOut(BaseModel):
    invoice_id: str
    invoice_type: str
    party_id: str | None
    doc_no: str
    doc_date: datetime
    due_date: date | None
    currency_code: str
    total_gross: Decimal
    applied_amount: Decimal
    outstanding_amount: Decimal
    days_past_due: int
    bucket: str


class AgingResponse(BaseModel):
    book_id: str
    as_of: date
    items: list[AgingItemOut]


