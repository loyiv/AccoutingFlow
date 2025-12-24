from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ScheduledLine(BaseModel):
    account_id: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    memo: str = ""
    aux_json: dict[str, Any] | None = None


class ScheduledTemplate(BaseModel):
    description: str = ""
    lines: list[ScheduledLine] = Field(default_factory=list)


class ScheduledCreateIn(BaseModel):
    book_id: str
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=256)
    enabled: bool = True
    rule: str = Field(description="DAILY/WEEKLY/MONTHLY")
    interval: int = Field(default=1, ge=1, le=365)
    next_run_date: date
    end_date: date | None = None
    template: ScheduledTemplate


class ScheduledOut(BaseModel):
    id: str
    book_id: str
    name: str
    description: str
    enabled: bool
    rule: str
    interval: int
    next_run_date: date
    end_date: date | None
    template: dict[str, Any]


class ScheduledRunRequest(BaseModel):
    run_date: date | None = None


class ScheduledRunOut(BaseModel):
    sched_id: str
    run_date: date
    status: str
    draft_id: str | None = None
    error: str = ""


