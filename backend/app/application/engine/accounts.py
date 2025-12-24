from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.infra.db.models import Account


@dataclass(frozen=True)
class AccountRow:
    id: str
    parent_id: str | None
    code: str
    name: str
    description: str
    type: str
    allow_post: bool
    is_active: bool
    is_hidden: bool
    is_placeholder: bool


def list_accounts(db: Session, book_id: str) -> list[AccountRow]:
    rows = (
        db.query(Account)
        .filter(Account.book_id == book_id)
        .order_by(Account.code.asc())
        .all()
    )
    return [
        AccountRow(
            id=str(a.id),
            parent_id=str(a.parent_id) if a.parent_id else None,
            code=a.code,
            name=a.name,
            description=a.description or "",
            type=a.type,
            allow_post=a.allow_post,
            is_active=a.is_active,
            is_hidden=bool(getattr(a, "is_hidden", False)),
            is_placeholder=bool(getattr(a, "is_placeholder", False)),
        )
        for a in rows
    ]


def build_account_children_map(accounts: Iterable[AccountRow]) -> dict[str | None, list[AccountRow]]:
    m: dict[str | None, list[AccountRow]] = defaultdict(list)
    for a in accounts:
        m[a.parent_id].append(a)
    for k in m:
        m[k].sort(key=lambda x: (x.code, x.name))
    return m


def collect_descendants(children_map: dict[str | None, list[AccountRow]], root_id: str) -> set[str]:
    out: set[str] = set()
    stack = [root_id]
    while stack:
        cur = stack.pop()
        if cur in out:
            continue
        out.add(cur)
        for ch in children_map.get(cur, []):
            stack.append(ch.id)
    return out


