from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class PartyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    tax_no: str = Field(default="", max_length=64)
    credit_limit: Decimal | None = None
    payment_term_days: int | None = Field(default=None, ge=0, le=3650)
    contact_json: dict[str, Any] | None = None


class PartyOut(BaseModel):
    id: str
    type: str
    name: str
    tax_no: str = ""
    credit_limit: Decimal | None = None
    payment_term_days: int | None = None
    contact_json: dict[str, Any] | None = None


class BusinessLineIn(BaseModel):
    description: str = Field(default="", max_length=256)
    account_id: str
    quantity: Decimal = Field(default=1)
    unit_price: Decimal = Field(default=0)
    tax_rate: Decimal | None = Field(default=None, description="例如 0.07 表示 7%")
    memo: str = Field(default="", max_length=256)


class PurchaseOrderCreateIn(BaseModel):
    book_id: str
    period_id: str
    doc_no: str = Field(default="", max_length=32)
    doc_date: date
    vendor_id: str
    project: str = Field(default="", max_length=128)
    term_days: int | None = Field(default=None, ge=0, le=3650)
    description: str = Field(default="", max_length=512)
    lines: list[BusinessLineIn] = Field(min_length=1)
    attachment_ids: list[str] = Field(default_factory=list)


class SalesOrderCreateIn(BaseModel):
    book_id: str
    period_id: str
    doc_no: str = Field(default="", max_length=32)
    doc_date: date
    customer_id: str
    project: str = Field(default="", max_length=128)
    term_days: int | None = Field(default=None, ge=0, le=3650)
    description: str = Field(default="", max_length=512)
    lines: list[BusinessLineIn] = Field(min_length=1, description="account_id=收入科目")
    attachment_ids: list[str] = Field(default_factory=list)


class ExpenseClaimCreateIn(BaseModel):
    book_id: str
    period_id: str
    doc_no: str = Field(default="", max_length=32)
    doc_date: date
    employee_id: str
    project: str = Field(default="", max_length=128, description="项目/部门")
    description: str = Field(default="", max_length=512)
    lines: list[BusinessLineIn] = Field(min_length=1, description="account_id=费用科目")
    attachment_ids: list[str] = Field(default_factory=list)


class DocumentResubmitIn(BaseModel):
    doc_date: date | None = None
    project: str | None = Field(default=None, max_length=128)
    term_days: int | None = Field(default=None, ge=0, le=3650)
    description: str | None = Field(default=None, max_length=512)
    lines: list[BusinessLineIn] | None = None
    attachment_ids: list[str] | None = None


class BusinessLineOut(BaseModel):
    line_no: int
    description: str
    account_id: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    amount: Decimal
    tax_amount: Decimal
    memo: str = ""


class BusinessDocumentOut(BaseModel):
    id: str
    doc_type: str
    status: str
    book_id: str
    period_id: str
    doc_date: str
    doc_no: str
    party_id: str | None = None
    employee_id: str = ""
    project: str = ""
    term_days: int | None = None
    description: str = ""
    total_amount: Decimal
    tax_amount: Decimal
    currency_code: str
    revision_no: int
    draft_id: str | None = None
    rejected_reason: str = ""
    lines: list[BusinessLineOut]
    attachment_ids: list[str] = Field(default_factory=list)


