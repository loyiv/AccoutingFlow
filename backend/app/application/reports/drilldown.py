from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.application.engine.accounts import build_account_children_map, collect_descendants, list_accounts
from app.infra.db.models import (
    Account,
    AccountingPeriod,
    Attachment,
    BusinessDocument,
    BusinessDocumentLine,
    ReportItem,
    ReportMapping,
    ReportSnapshot,
    Split,
    Transaction,
)

_CREDIT_TYPES = {"LIABILITY", "EQUITY", "INCOME", "AP"}


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


@dataclass(frozen=True)
class DrillAccount:
    account_id: str
    code: str
    name: str
    amount: Decimal


@dataclass(frozen=True)
class DrillRegisterItem:
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


@dataclass(frozen=True)
class TxnSplitDetail:
    line_no: int
    account_id: str
    account_code: str
    account_name: str
    value: Decimal
    memo: str


@dataclass(frozen=True)
class SourceDocDetail:
    doc_type: str
    doc_id: str
    doc_no: str
    status: str
    doc_date: str
    description: str
    revision_no: int
    draft_id: str | None


@dataclass(frozen=True)
class TxnDetail:
    txn_id: str
    num: str
    txn_date: str
    description: str
    source_type: str
    source_id: str
    version: int
    splits: list[TxnSplitDetail]
    source_doc: SourceDocDetail | None


def _expand_item_accounts(db: Session, snap: ReportSnapshot, statement_type: str, item_code: str) -> tuple[ReportItem, set[str]]:
    item = db.query(ReportItem).filter(ReportItem.statement_type == statement_type, ReportItem.code == item_code).one_or_none()
    if not item:
        raise ValueError("报表项目不存在")

    mappings = db.query(ReportMapping).filter(ReportMapping.basis_id == snap.basis_id, ReportMapping.item_id == item.id).all()
    if not mappings:
        return item, set()

    accounts = list_accounts(db, str(snap.book_id))
    children_map = build_account_children_map(accounts)

    acc_ids: set[str] = set()
    for m in mappings:
        rid = str(m.account_id)
        acc_ids |= collect_descendants(children_map, rid) if m.include_children else {rid}
    return item, acc_ids


def drilldown_accounts(db: Session, snapshot_id: str, statement_type: str, item_code: str) -> list[DrillAccount]:
    snap = db.query(ReportSnapshot).filter(ReportSnapshot.id == snapshot_id).one_or_none()
    if not snap:
        raise ValueError("报表快照不存在")

    item, acc_ids = _expand_item_accounts(db, snap, statement_type, item_code)
    if not acc_ids:
        return []

    period = db.query(AccountingPeriod).filter(AccountingPeriod.id == snap.period_id).one()
    pkey = int(period.year) * 100 + int(period.month)

    acc_tbl = Account.__table__
    sp_tbl = Split.__table__
    tx_tbl = Transaction.__table__
    pe_tbl = AccountingPeriod.__table__

    norm_value = sa.case((acc_tbl.c.type.in_(list(_CREDIT_TYPES)), -sp_tbl.c.value), else_=sp_tbl.c.value)

    if item.calc_mode == "BALANCE":
        q = (
            sa.select(sp_tbl.c.account_id, sa.func.coalesce(sa.func.sum(norm_value), 0).label("amt"))
            .select_from(
                sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id)
                .join(pe_tbl, tx_tbl.c.period_id == pe_tbl.c.id)
                .join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id)
            )
            .where(acc_tbl.c.book_id == str(snap.book_id))
            .where(sp_tbl.c.account_id.in_(sa.bindparam("acc_ids", expanding=True)))
            .where((pe_tbl.c.year * 100 + pe_tbl.c.month) <= pkey)
            .group_by(sp_tbl.c.account_id)
        )
        rows = db.execute(q, {"acc_ids": list(acc_ids)}).all()
    else:
        q = (
            sa.select(sp_tbl.c.account_id, sa.func.coalesce(sa.func.sum(norm_value), 0).label("amt"))
            .select_from(sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id).join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id))
            .where(acc_tbl.c.book_id == str(snap.book_id))
            .where(tx_tbl.c.period_id == str(snap.period_id))
            .where(sp_tbl.c.account_id.in_(sa.bindparam("acc_ids", expanding=True)))
            .group_by(sp_tbl.c.account_id)
        )
        rows = db.execute(q, {"acc_ids": list(acc_ids)}).all()

    amt_by_acc = {str(r[0]): _decimal(r[1]) for r in rows}
    acc_rows = db.query(Account).filter(Account.id.in_(list(acc_ids))).all()
    acc_rows.sort(key=lambda a: (a.code, a.name))
    out: list[DrillAccount] = []
    for a in acc_rows:
        amt = amt_by_acc.get(str(a.id), Decimal("0"))
        if amt == 0:
            continue
        out.append(DrillAccount(account_id=str(a.id), code=a.code, name=a.name, amount=amt))
    return out


def drilldown_register(
    db: Session,
    snapshot_id: str,
    statement_type: str,
    item_code: str,
    account_id: str,
    include_children: bool = False,
) -> list[DrillRegisterItem]:
    snap = db.query(ReportSnapshot).filter(ReportSnapshot.id == snapshot_id).one_or_none()
    if not snap:
        raise ValueError("报表快照不存在")

    item, acc_ids = _expand_item_accounts(db, snap, statement_type, item_code)
    if not acc_ids:
        return []

    # 仅允许查询在该 item 映射范围内的科目（或其父科目）
    accounts = list_accounts(db, str(snap.book_id))
    children_map = build_account_children_map(accounts)
    if include_children:
        scope_ids = collect_descendants(children_map, account_id)
    else:
        scope_ids = {account_id}
    scope_ids = set(scope_ids) & set(acc_ids)
    if not scope_ids:
        return []

    period = db.query(AccountingPeriod).filter(AccountingPeriod.id == snap.period_id).one()
    pkey = int(period.year) * 100 + int(period.month)

    acc_tbl = Account.__table__
    sp_tbl = Split.__table__
    tx_tbl = Transaction.__table__
    pe_tbl = AccountingPeriod.__table__

    norm_value = sa.case((acc_tbl.c.type.in_(list(_CREDIT_TYPES)), -sp_tbl.c.value), else_=sp_tbl.c.value)

    if item.calc_mode == "BALANCE":
        q = (
            sa.select(
                tx_tbl.c.id,
                tx_tbl.c.num,
                tx_tbl.c.txn_date,
                tx_tbl.c.description,
                sp_tbl.c.line_no,
                norm_value.label("value"),
                sp_tbl.c.memo,
                tx_tbl.c.source_type,
                tx_tbl.c.source_id,
                tx_tbl.c.version,
            )
            .select_from(
                sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id)
                .join(pe_tbl, tx_tbl.c.period_id == pe_tbl.c.id)
                .join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id)
            )
            .where(acc_tbl.c.book_id == str(snap.book_id))
            .where(sp_tbl.c.account_id.in_(sa.bindparam("scope_ids", expanding=True)))
            .where((pe_tbl.c.year * 100 + pe_tbl.c.month) <= pkey)
            .order_by(tx_tbl.c.txn_date.desc(), tx_tbl.c.num.desc(), sp_tbl.c.line_no.asc())
            .limit(500)
        )
        rows = db.execute(q, {"scope_ids": list(scope_ids)}).all()
    else:
        q = (
            sa.select(
                tx_tbl.c.id,
                tx_tbl.c.num,
                tx_tbl.c.txn_date,
                tx_tbl.c.description,
                sp_tbl.c.line_no,
                norm_value.label("value"),
                sp_tbl.c.memo,
                tx_tbl.c.source_type,
                tx_tbl.c.source_id,
                tx_tbl.c.version,
            )
            .select_from(sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id).join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id))
            .where(acc_tbl.c.book_id == str(snap.book_id))
            .where(tx_tbl.c.period_id == str(snap.period_id))
            .where(sp_tbl.c.account_id.in_(sa.bindparam("scope_ids", expanding=True)))
            .order_by(tx_tbl.c.txn_date.desc(), tx_tbl.c.num.desc(), sp_tbl.c.line_no.asc())
            .limit(500)
        )
        rows = db.execute(q, {"scope_ids": list(scope_ids)}).all()

    out: list[DrillRegisterItem] = []
    for r in rows:
        txn_id, num, txn_date, desc, line_no, value, memo, st, sid, ver = r
        out.append(
            DrillRegisterItem(
                txn_id=str(txn_id),
                txn_num=str(num),
                txn_date=(txn_date.date().isoformat() if hasattr(txn_date, "date") else str(txn_date)),
                description=str(desc or ""),
                split_line_no=int(line_no),
                value=_decimal(value),
                memo=str(memo or ""),
                source_type=str(st),
                source_id=str(sid),
                version=int(ver),
            )
        )
    return out


def get_transaction_detail(db: Session, txn_id: str) -> TxnDetail:
    txn = db.query(Transaction).filter(Transaction.id == txn_id).one_or_none()
    if not txn:
        raise ValueError("凭证不存在")
    splits = db.query(Split).filter(Split.txn_id == txn.id).order_by(Split.line_no.asc()).all()
    acc_ids = [str(s.account_id) for s in splits]
    accs = db.query(Account).filter(Account.id.in_(acc_ids)).all()
    by_id = {str(a.id): a for a in accs}

    split_out: list[TxnSplitDetail] = []
    for s in splits:
        a = by_id.get(str(s.account_id))
        split_out.append(
            TxnSplitDetail(
                line_no=s.line_no,
                account_id=str(s.account_id),
                account_code=a.code if a else "",
                account_name=a.name if a else "",
                value=_decimal(s.value),
                memo=s.memo or "",
            )
        )

    source_doc: SourceDocDetail | None = None
    if txn.source_type in ("PURCHASE_ORDER", "SALES_ORDER", "EXPENSE_CLAIM"):
        doc = db.query(BusinessDocument).filter(BusinessDocument.id == txn.source_id).one_or_none()
        if doc:
            source_doc = SourceDocDetail(
                doc_type=doc.doc_type,
                doc_id=str(doc.id),
                doc_no=doc.doc_no,
                status=doc.status,
                doc_date=(doc.doc_date.date().isoformat() if hasattr(doc.doc_date, "date") else str(doc.doc_date)),
                description=doc.description or "",
                revision_no=int(doc.revision_no),
                draft_id=str(doc.draft_id) if doc.draft_id else None,
            )

    return TxnDetail(
        txn_id=str(txn.id),
        num=txn.num,
        txn_date=(txn.txn_date.date().isoformat() if hasattr(txn.txn_date, "date") else str(txn.txn_date)),
        description=txn.description or "",
        source_type=txn.source_type,
        source_id=txn.source_id,
        version=int(txn.version),
        splits=split_out,
        source_doc=source_doc,
    )


