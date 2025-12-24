from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReportGenerateRequest(BaseModel):
    book_id: str
    period_id: str
    basis_code: str = "LEGAL"  # LEGAL / MGMT


class ReportItemAmount(BaseModel):
    code: str
    name: str
    amount: Decimal


class ReportStatement(BaseModel):
    statement_type: Literal["BS", "IS", "CF"]
    items: list[ReportItemAmount]


class ReportSnapshotOut(BaseModel):
    id: str
    book_id: str
    period_id: str
    basis_code: str
    generated_at: str
    is_stale: bool
    result: dict[str, Any]
    log: dict[str, Any]


class ReportGenerateResponse(BaseModel):
    snapshot_id: str


class DrilldownAccountAmount(BaseModel):
    account_id: str
    code: str
    name: str
    amount: Decimal


class DrilldownResponse(BaseModel):
    snapshot_id: str
    statement_type: str
    item_code: str
    accounts: list[DrilldownAccountAmount]


class DrilldownRegisterItem(BaseModel):
    txn_id: str
    txn_num: str
    txn_date: str
    description: str
    split_line_no: int
    value: Decimal
    memo: str
    source_type: str
    source_id: str
    version: int


class DrilldownRegisterResponse(BaseModel):
    snapshot_id: str
    statement_type: str
    item_code: str
    account_id: str
    include_children: bool = False
    items: list[DrilldownRegisterItem]


class TxnSplitDetail(BaseModel):
    line_no: int
    account_id: str
    account_code: str
    account_name: str
    value: Decimal
    memo: str = ""


class SourceDocDetail(BaseModel):
    doc_type: str
    doc_id: str
    doc_no: str
    status: str
    doc_date: str
    description: str = ""
    revision_no: int
    draft_id: str | None = None


class TransactionDetailResponse(BaseModel):
    txn_id: str
    num: str
    txn_date: str
    description: str
    source_type: str
    source_id: str
    version: int
    splits: list[TxnSplitDetail]
    source_doc: SourceDocDetail | None = None


class ReportExportRequest(BaseModel):
    snapshot_id: str
    format: Literal["pdf", "excel"] = "excel"


