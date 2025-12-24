from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ReconcileCreateIn(BaseModel):
    book_id: str
    account_id: str
    statement_date: date
    ending_balance: Decimal


class ReconcileSessionOut(BaseModel):
    id: str
    book_id: str
    account_id: str
    statement_date: date
    ending_balance: Decimal
    status: str


class ReconcileRegisterItem(BaseModel):
    split_id: str
    txn_id: str
    txn_num: str
    txn_date: str
    description: str
    value: Decimal
    memo: str
    reconcile_state: str
    selected: bool


class ReconcileDetailOut(BaseModel):
    session: ReconcileSessionOut
    items: list[ReconcileRegisterItem]
    selected_total: Decimal
    account_total_asof_date: Decimal
    difference: Decimal


class ReconcileToggleIn(BaseModel):
    split_id: str
    selected: bool = True


class ReconcileFinishOut(BaseModel):
    session_id: str
    status: str
    difference: Decimal


