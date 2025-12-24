from __future__ import annotations

from pydantic import BaseModel, Field


class AccountOut(BaseModel):
    id: str
    book_id: str
    parent_id: str | None
    code: str
    name: str
    description: str = ""
    type: str
    commodity_id: str
    allow_post: bool
    is_active: bool
    is_hidden: bool = False
    is_placeholder: bool = False


class AccountCreateIn(BaseModel):
    book_id: str
    parent_id: str | None = None
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=256)
    type: str = Field(min_length=1, max_length=24)
    commodity_id: str
    allow_post: bool = True
    is_active: bool = True
    is_hidden: bool = False
    is_placeholder: bool = False


class AccountUpdateIn(BaseModel):
    parent_id: str | None = None
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=256)
    type: str | None = Field(default=None, max_length=24)
    commodity_id: str | None = None
    allow_post: bool | None = None
    is_active: bool | None = None
    is_hidden: bool | None = None
    is_placeholder: bool | None = None


