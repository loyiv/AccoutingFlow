from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AccountImportPreviewRow(BaseModel):
    row_no: int
    data: dict[str, Any]


class AccountImportPreviewResponse(BaseModel):
    book_id: str
    detected_delimiter: str
    headers: list[str]
    rows: list[AccountImportPreviewRow]
    warnings: list[str] = Field(default_factory=list)


class AccountImportCommitResponse(BaseModel):
    book_id: str
    created: int
    updated: int
    skipped: int
    warnings: list[str] = Field(default_factory=list)


