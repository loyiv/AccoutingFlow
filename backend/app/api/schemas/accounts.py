from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class AccountNode(BaseModel):
    id: str
    parent_id: str | None
    code: str
    name: str
    description: str = ""
    type: str
    allow_post: bool
    is_active: bool
    is_hidden: bool = False
    is_placeholder: bool = False
    total: Decimal = Decimal("0")
    children: list["AccountNode"] = []


AccountNode.model_rebuild()


