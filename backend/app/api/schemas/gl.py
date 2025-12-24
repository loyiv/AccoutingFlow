from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class DraftLineOut(BaseModel):
    id: str
    line_no: int
    account_id: str
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    memo: str = ""
    aux_json: dict[str, Any] | None = None


class DraftOut(BaseModel):
    id: str
    book_id: str
    period_id: str
    currency_id: str | None = None
    txn_date: str | None = None
    source_type: str
    source_id: str
    version: int
    description: str
    status: str
    posted_txn_id: str | None = None
    lines: list[DraftLineOut]


class DraftListItem(BaseModel):
    id: str
    period_id: str
    currency_id: str | None = None
    txn_date: str | None = None
    source_type: str
    source_id: str
    version: int
    description: str
    status: str


class PrecheckItem(BaseModel):
    code: str
    passed: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PrecheckResponse(BaseModel):
    draft_id: str
    ok: bool
    checks: list[PrecheckItem]


class PostResponse(BaseModel):
    draft_id: str
    txn_id: str
    voucher_num: str


class ApproveRejectResponse(BaseModel):
    draft_id: str
    status: str


class RejectRequest(BaseModel):
    reason: str = Field(default="", max_length=512)


class RegisterSplitOut(BaseModel):
    split_id: str
    txn_id: str
    txn_num: str
    txn_date: str
    description: str
    split_line_no: int
    value: Decimal
    memo: str
    reconcile_state: str = "n"


class RegisterResponse(BaseModel):
    account_id: str
    items: list[RegisterSplitOut]


class DraftCreateLineIn(BaseModel):
    account_id: str
    debit: Decimal = Field(default=0)
    credit: Decimal = Field(default=0)
    memo: str = Field(default="", max_length=256)
    aux_json: dict[str, Any] | None = None


class DraftCreateIn(BaseModel):
    book_id: str
    period_id: str
    currency_id: str | None = None
    txn_date: datetime | None = None
    description: str = Field(default="", max_length=256)
    lines: list[DraftCreateLineIn] = Field(min_length=2)


class DraftCreateResponse(BaseModel):
    draft_id: str


