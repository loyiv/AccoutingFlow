from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, require_roles
from app.api.schemas.reconcile import (
    ReconcileCreateIn,
    ReconcileDetailOut,
    ReconcileFinishOut,
    ReconcileSessionOut,
    ReconcileToggleIn,
)
from app.infra.db.models import Account, ReconcileMatch, ReconcileSession, Split, Transaction, utcnow, uuid_str

router = APIRouter(prefix="/reconcile", tags=["reconcile"])

_CREDIT_TYPES = {"LIABILITY", "EQUITY", "INCOME", "AP"}


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _normalize_value(account_type: str, split_value: Decimal) -> Decimal:
    # 与报表/科目树一致：资产/费用正向；负债/权益/收入反向
    if (account_type or "").upper() in _CREDIT_TYPES:
        return -_decimal(split_value)
    return _decimal(split_value)


def _as_dt(d: date) -> datetime:
    # 截止日应包含“当天整日”的交易；否则同一天但时间在 00:00 之后的 txn 会被误过滤，导致前端借/贷栏无候选
    return datetime.combine(d, time.max)


def _load_detail(db: Session, sess: ReconcileSession) -> ReconcileDetailOut:
    acc = db.query(Account).filter(Account.id == sess.account_id).one_or_none()
    if not acc:
        # 避免 .one() 抛异常导致 500；给前端可理解的错误
        raise HTTPException(status_code=400, detail="对账科目不存在或已被删除")

    # 候选：该科目在 statement_date（含）之前、且未对账(y)的 split
    q = (
        db.query(Split, Transaction)
        .join(Transaction, Split.txn_id == Transaction.id)
        .filter(Split.account_id == sess.account_id)
        .filter(Transaction.txn_date <= _as_dt(sess.statement_date))
        .filter(Split.reconcile_state != "y")
        .order_by(Transaction.txn_date.asc(), Split.line_no.asc())
    )
    rows = q.limit(2000).all()

    selected_ids = {
        str(x.split_id)
        for x in db.query(ReconcileMatch.split_id).filter(ReconcileMatch.session_id == sess.id).all()
    }

    items = []
    selected_total = Decimal("0")
    account_total = Decimal("0")

    for sp, txn in rows:
        nv = _normalize_value(acc.type, _decimal(sp.value))
        account_total += nv
        sel = str(sp.id) in selected_ids
        if sel:
            selected_total += nv
        items.append(
            {
                "split_id": str(sp.id),
                "txn_id": str(txn.id),
                "txn_num": txn.num,
                "txn_date": txn.txn_date.date().isoformat(),
                "description": txn.description,
                "value": _decimal(sp.value),
                "memo": sp.memo,
                "reconcile_state": sp.reconcile_state,
                "selected": sel,
            }
        )

    # difference：用“期末余额 - 选中分录之和”作为剩余差额（这里用简化口径）
    # 说明：严格对账应该考虑期初余额；这里按“截至对账日该账户应有余额”为基准简化。
    difference = _decimal(sess.ending_balance) - selected_total

    return ReconcileDetailOut(
        session=ReconcileSessionOut(
            id=str(sess.id),
            book_id=str(sess.book_id),
            account_id=str(sess.account_id),
            statement_date=sess.statement_date,
            ending_balance=_decimal(sess.ending_balance),
            status=sess.status,
        ),
        items=items,  # type: ignore[arg-type]
        selected_total=selected_total,
        account_total_asof_date=account_total,
        difference=difference,
    )


@router.post("/sessions", response_model=ReconcileSessionOut)
def create_session(
    payload: ReconcileCreateIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> ReconcileSessionOut:
    try:
        # 关键：在任何 query 之前就 begin，避免 SQLAlchemy 2.0 autobegin 后再 begin() 引发 500
        with db.begin():
            acc = db.query(Account).filter(Account.id == payload.account_id).one_or_none()
            if not acc or str(acc.book_id) != payload.book_id:
                raise HTTPException(status_code=400, detail="科目不存在或不属于该账簿")

            # 幂等：同一 account_id + statement_date 只允许存在一个会话（uq_recon_account_date）。
            existed = (
                db.query(ReconcileSession)
                .filter(ReconcileSession.account_id == payload.account_id, ReconcileSession.statement_date == payload.statement_date)
                .one_or_none()
            )
            if existed:
                # 允许同一截止日“继续对账”：
                # - 如果会话已 FINISHED，则将其重新打开（OPEN），并允许更新期末余额
                if existed.status != "OPEN":
                    existed.status = "OPEN"
                    existed.finished_at = None
                # 允许用户用新的期末余额继续对账（例如后续补录了同日期交易）
                existed.ending_balance = _decimal(payload.ending_balance)
                db.flush()
                return ReconcileSessionOut(
                    id=str(existed.id),
                    book_id=str(existed.book_id),
                    account_id=str(existed.account_id),
                    statement_date=existed.statement_date,
                    ending_balance=_decimal(existed.ending_balance),
                    status=existed.status,
                )

            sess = ReconcileSession(
                id=uuid_str(),
                book_id=payload.book_id,
                account_id=payload.account_id,
                statement_date=payload.statement_date,
                ending_balance=_decimal(payload.ending_balance),
                status="OPEN",
                created_by=u.id,
                created_at=utcnow(),
                finished_at=None,
            )
            db.add(sess)
            db.flush()
            return ReconcileSessionOut(
                id=str(sess.id),
                book_id=str(sess.book_id),
                account_id=str(sess.account_id),
                statement_date=sess.statement_date,
                ending_balance=_decimal(sess.ending_balance),
                status=sess.status,
            )
    except IntegrityError:
        # 并发/重复点击兜底：唯一约束冲突后，返回已存在的会话
        db.rollback()
        existed3 = (
            db.query(ReconcileSession)
            .filter(ReconcileSession.account_id == payload.account_id, ReconcileSession.statement_date == payload.statement_date)
            .one_or_none()
        )
        if existed3:
            return ReconcileSessionOut(
                id=str(existed3.id),
                book_id=str(existed3.book_id),
                account_id=str(existed3.account_id),
                statement_date=existed3.statement_date,
                ending_balance=_decimal(existed3.ending_balance),
                status=existed3.status,
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="对账会话创建失败，请稍后重试")


@router.get("/sessions", response_model=list[ReconcileSessionOut])
def list_sessions(
    book_id: str = Query(...),
    account_id: str | None = Query(default=None),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> list[ReconcileSessionOut]:
    q = db.query(ReconcileSession).filter(ReconcileSession.book_id == book_id).order_by(ReconcileSession.created_at.desc())
    if account_id:
        q = q.filter(ReconcileSession.account_id == account_id)
    rows = q.limit(200).all()
    return [
        ReconcileSessionOut(
            id=str(s.id),
            book_id=str(s.book_id),
            account_id=str(s.account_id),
            statement_date=s.statement_date,
            ending_balance=_decimal(s.ending_balance),
            status=s.status,
        )
        for s in rows
    ]


@router.get("/sessions/{session_id}", response_model=ReconcileDetailOut)
def get_session_detail(
    session_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> ReconcileDetailOut:
    sess = db.query(ReconcileSession).filter(ReconcileSession.id == session_id).one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="对账会话不存在")
    return _load_detail(db, sess)


@router.post("/sessions/{session_id}:toggle", response_model=ReconcileDetailOut)
def toggle_split(
    session_id: str,
    body: ReconcileToggleIn,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> ReconcileDetailOut:
    with db.begin():
        sess = db.query(ReconcileSession).filter(ReconcileSession.id == session_id).with_for_update().one_or_none()
        if not sess:
            raise HTTPException(status_code=404, detail="对账会话不存在")
        if sess.status != "OPEN":
            raise HTTPException(status_code=400, detail="会话已结束")

        sp = db.query(Split).filter(Split.id == body.split_id, Split.account_id == sess.account_id).one_or_none()
        if not sp:
            raise HTTPException(status_code=400, detail="分录不存在或不属于该科目")
        # toggle
        m = db.query(ReconcileMatch).filter(ReconcileMatch.session_id == sess.id, ReconcileMatch.split_id == sp.id).one_or_none()
        if body.selected:
            if not m:
                db.add(ReconcileMatch(id=uuid_str(), session_id=sess.id, split_id=sp.id, created_at=utcnow()))
            # mark cleared
            if sp.reconcile_state == "n":
                sp.reconcile_state = "c"
        else:
            if m:
                db.delete(m)
        db.flush()
        return _load_detail(db, sess)


@router.post("/sessions/{session_id}:finish", response_model=ReconcileFinishOut)
def finish_session(
    session_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> ReconcileFinishOut:
    with db.begin():
        sess = db.query(ReconcileSession).filter(ReconcileSession.id == session_id).with_for_update().one_or_none()
        if not sess:
            raise HTTPException(status_code=404, detail="对账会话不存在")
        if sess.status != "OPEN":
            raise HTTPException(status_code=400, detail="会话已结束")

        detail = _load_detail(db, sess)
        # 允许 0.01 的误差（浮点/四舍五入）
        if abs(detail.difference) > Decimal("0.01"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"差额不为 0，不能完成对账（difference={detail.difference}）",
            )

        # set selected splits to reconciled
        sel_ids = [x.split_id for x in db.query(ReconcileMatch.split_id).filter(ReconcileMatch.session_id == sess.id).all()]
        if sel_ids:
            db.query(Split).filter(Split.id.in_(sel_ids)).update({Split.reconcile_state: "y"}, synchronize_session=False)

        sess.status = "FINISHED"
        sess.finished_at = utcnow()
        db.flush()
        return ReconcileFinishOut(session_id=str(sess.id), status=sess.status, difference=detail.difference)


