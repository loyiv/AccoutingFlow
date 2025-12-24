from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, get_current_user, require_roles
from app.api.schemas.accounts import AccountNode
from app.api.schemas.accounts_crud import AccountCreateIn, AccountOut, AccountUpdateIn
from app.api.schemas.gl import RegisterResponse, RegisterSplitOut
from app.application.engine.accounts import AccountRow, build_account_children_map, list_accounts
from app.infra.db.models import Account, AccountingPeriod, Book, Commodity, Split, Transaction

router = APIRouter(prefix="/accounts", tags=["accounts"])

_CREDIT_TYPES = {"LIABILITY", "EQUITY", "INCOME", "AP"}


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _compute_totals(db: Session, book_id: str, period_id: str | None) -> dict[str, Decimal]:
    acc_tbl = Account.__table__
    sp_tbl = Split.__table__
    tx_tbl = Transaction.__table__

    norm_value = sa.case((acc_tbl.c.type.in_(list(_CREDIT_TYPES)), -sp_tbl.c.value), else_=sp_tbl.c.value)

    if period_id:
        pe_tbl = AccountingPeriod.__table__
        period = db.query(AccountingPeriod).filter(AccountingPeriod.id == period_id, AccountingPeriod.book_id == book_id).one_or_none()
        if not period:
            return {}
        pkey = int(period.year) * 100 + int(period.month)
        q = (
            sa.select(sp_tbl.c.account_id, sa.func.coalesce(sa.func.sum(norm_value), 0).label("amt"))
            .select_from(
                sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id)
                .join(pe_tbl, tx_tbl.c.period_id == pe_tbl.c.id)
                .join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id)
            )
            .where(acc_tbl.c.book_id == book_id)
            .where((pe_tbl.c.year * 100 + pe_tbl.c.month) <= pkey)
            .group_by(sp_tbl.c.account_id)
        )
        rows = db.execute(q).all()
    else:
        q = (
            sa.select(sp_tbl.c.account_id, sa.func.coalesce(sa.func.sum(norm_value), 0).label("amt"))
            .select_from(sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id).join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id))
            .where(acc_tbl.c.book_id == book_id)
            .group_by(sp_tbl.c.account_id)
        )
        rows = db.execute(q).all()

    return {str(r[0]): _decimal(r[1]) for r in rows}


def _build_tree(children: dict[str | None, list[AccountRow]], totals_own: dict[str, Decimal], parent_id: str | None) -> list[AccountNode]:
    out: list[AccountNode] = []

    def build_one(a: AccountRow) -> AccountNode:
        child_nodes = _build_tree(children, totals_own, a.id)
        own = totals_own.get(a.id, Decimal("0"))
        total = own + sum((c.total for c in child_nodes), start=Decimal("0"))
        return AccountNode(
            id=a.id,
            parent_id=a.parent_id,
            code=a.code,
            name=a.name,
            description=a.description or "",
            type=a.type,
            allow_post=a.allow_post,
            is_active=a.is_active,
            is_hidden=a.is_hidden,
            is_placeholder=a.is_placeholder,
            total=total,
            children=child_nodes,
        )

    for a in children.get(parent_id, []):
        if a.is_hidden:
            continue
        out.append(build_one(a))
    return out


@router.get("/tree", response_model=list[AccountNode])
def get_accounts_tree(
    book_id: str = Query(...),
    period_id: str | None = Query(default=None),
    db: Session = Depends(db_session),
    _=Depends(get_current_user),
) -> list[AccountNode]:
    accounts = list_accounts(db, book_id)
    children = build_account_children_map(accounts)
    totals_own = _compute_totals(db, book_id, period_id)
    return _build_tree(children, totals_own, None)


@router.get("/{account_id}/register", response_model=RegisterResponse)
def get_register(
    account_id: str,
    period_id: str | None = Query(default=None),
    db: Session = Depends(db_session),
    _=Depends(get_current_user),
) -> RegisterResponse:
    q = (
        db.query(Split, Transaction)
        .join(Transaction, Split.txn_id == Transaction.id)
        .filter(Split.account_id == account_id)
        .order_by(Transaction.posted_at.desc(), Split.line_no.asc())
    )
    if period_id:
        q = q.filter(Transaction.period_id == period_id)

    rows = q.limit(500).all()
    items = [
        RegisterSplitOut(
            split_id=str(sp.id),
            txn_id=str(txn.id),
            txn_num=txn.num,
            txn_date=txn.txn_date.date().isoformat(),
            description=txn.description,
            split_line_no=sp.line_no,
            value=sp.value,
            memo=sp.memo,
            reconcile_state=sp.reconcile_state,
        )
        for sp, txn in rows
    ]
    return RegisterResponse(account_id=account_id, items=items)


@router.post("/splits/{split_id}:set_reconcile")
def set_split_reconcile_state(
    split_id: str,
    state: str = Query(..., description="n/c/y"),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
):
    if state not in ("n", "c", "y"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="state 必须为 n/c/y")
    with db.begin():
        sp = db.query(Split).filter(Split.id == split_id).with_for_update().one_or_none()
        if not sp:
            raise HTTPException(status_code=404, detail="分录不存在")
        sp.reconcile_state = state
        db.flush()
        return {"split_id": split_id, "reconcile_state": state}


@router.get("/{account_id}", response_model=AccountOut)
def get_account(
    account_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(get_current_user),
) -> AccountOut:
    a = db.query(Account).filter(Account.id == account_id).one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="科目不存在")
    return AccountOut(
        id=str(a.id),
        book_id=str(a.book_id),
        parent_id=str(a.parent_id) if a.parent_id else None,
        code=a.code,
        name=a.name,
        description=getattr(a, "description", "") or "",
        type=a.type,
        commodity_id=str(a.commodity_id),
        allow_post=bool(a.allow_post),
        is_active=bool(a.is_active),
        is_hidden=bool(getattr(a, "is_hidden", False)),
        is_placeholder=bool(getattr(a, "is_placeholder", False)),
    )


@router.post("", response_model=AccountOut)
def create_account(
    body: AccountCreateIn,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> AccountOut:
    try:
        with db.begin():
            # 基本存在性校验
            if not db.query(Book).filter(Book.id == body.book_id).one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="账簿不存在")
            if not db.query(Commodity).filter(Commodity.id == body.commodity_id).one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="币种/商品不存在")
            if body.parent_id:
                parent = db.query(Account).filter(Account.id == body.parent_id).one_or_none()
                if not parent or str(parent.book_id) != body.book_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父科目不存在或不属于该账簿")

            allow_post = body.allow_post and (not body.is_placeholder)
            a = Account(
                book_id=body.book_id,
                parent_id=body.parent_id,
                code=body.code,
                name=body.name,
                description=body.description or "",
                type=body.type,
                commodity_id=body.commodity_id,
                allow_post=allow_post,
                is_active=body.is_active,
                is_hidden=body.is_hidden,
                is_placeholder=body.is_placeholder,
            )
            db.add(a)
            db.flush()
            return AccountOut(
                id=str(a.id),
                book_id=str(a.book_id),
                parent_id=str(a.parent_id) if a.parent_id else None,
                code=a.code,
                name=a.name,
                description=a.description or "",
                type=a.type,
                commodity_id=str(a.commodity_id),
                allow_post=bool(a.allow_post),
                is_active=bool(a.is_active),
                is_hidden=bool(a.is_hidden),
                is_placeholder=bool(a.is_placeholder),
            )
    except IntegrityError:
        # 避免唯一约束冲突直接变成 500 → 前端“服务不可用”
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="科目代码已存在，请更换代码或刷新后重试")


@router.put("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: str,
    body: AccountUpdateIn,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> AccountOut:
    try:
        with db.begin():
            a = db.query(Account).filter(Account.id == account_id).one_or_none()
            if not a:
                raise HTTPException(status_code=404, detail="科目不存在")

        if body.parent_id is not None:
            if body.parent_id == "":
                a.parent_id = None
            else:
                parent = db.query(Account).filter(Account.id == body.parent_id).one_or_none()
                if not parent or str(parent.book_id) != str(a.book_id):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="父科目不存在或不属于该账簿")
                a.parent_id = parent.id
        if body.code is not None:
            a.code = body.code
        if body.name is not None:
            a.name = body.name
        if body.description is not None:
            a.description = body.description
        if body.type is not None:
            a.type = body.type
        if body.commodity_id is not None:
            if not db.query(Commodity).filter(Commodity.id == body.commodity_id).one_or_none():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="币种/商品不存在")
            a.commodity_id = body.commodity_id
        if body.is_hidden is not None:
            a.is_hidden = body.is_hidden
        if body.is_placeholder is not None:
            a.is_placeholder = body.is_placeholder
        if body.is_active is not None:
            a.is_active = body.is_active
        if body.allow_post is not None:
            a.allow_post = body.allow_post

        # placeholder 强制不可记账
        if bool(getattr(a, "is_placeholder", False)):
            a.allow_post = False

            db.flush()
            return AccountOut(
                id=str(a.id),
                book_id=str(a.book_id),
                parent_id=str(a.parent_id) if a.parent_id else None,
                code=a.code,
                name=a.name,
                description=getattr(a, "description", "") or "",
                type=a.type,
                commodity_id=str(a.commodity_id),
                allow_post=bool(a.allow_post),
                is_active=bool(a.is_active),
                is_hidden=bool(getattr(a, "is_hidden", False)),
                is_placeholder=bool(getattr(a, "is_placeholder", False)),
            )
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="科目代码冲突，请更换代码后重试")


