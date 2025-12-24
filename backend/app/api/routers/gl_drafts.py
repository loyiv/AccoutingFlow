from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, require_roles
from app.api.schemas.gl import (
    ApproveRejectResponse,
    DraftCreateIn,
    DraftCreateResponse,
    DraftListItem,
    DraftOut,
    PrecheckResponse,
    PostResponse,
    RejectRequest,
)
from app.application.gl.draft_workflow import approve_draft, reject_draft
from app.application.gl.posting import post_draft, precheck_draft
from app.application.gl.draft_workflow import append_revision
from app.infra.db.models import Account, AccountingPeriod, Book, Commodity, TransactionDraft, TransactionDraftLine

router = APIRouter(prefix="/gl", tags=["gl"])


@router.get("/drafts", response_model=list[DraftListItem])
def list_drafts(
    period: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> list[DraftListItem]:
    q = db.query(TransactionDraft).filter(TransactionDraft.status.in_(["DRAFT", "SUBMITTED", "APPROVED"]))
    if period:
        q = q.filter(TransactionDraft.period_id == period)
    if source_type:
        q = q.filter(TransactionDraft.source_type == source_type)
    rows = q.order_by(TransactionDraft.created_at.desc()).limit(200).all()
    return [
        DraftListItem(
            id=str(d.id),
            period_id=str(d.period_id),
            currency_id=str(d.currency_id) if getattr(d, "currency_id", None) else None,
            txn_date=d.txn_date.isoformat() if getattr(d, "txn_date", None) else None,
            source_type=d.source_type,
            source_id=d.source_id,
            version=d.version,
            description=d.description,
            status=d.status,
        )
        for d in rows
    ]


@router.get("/drafts/{draft_id}", response_model=DraftOut)
def get_draft(
    draft_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> DraftOut:
    d = db.query(TransactionDraft).filter(TransactionDraft.id == draft_id).one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="草稿不存在")
    lines = (
        db.query(TransactionDraftLine)
        .filter(TransactionDraftLine.draft_id == d.id)
        .order_by(TransactionDraftLine.line_no.asc())
        .all()
    )
    account_ids = [x.account_id for x in lines]
    accs = db.query(Account).filter(Account.id.in_(account_ids)).all()
    by_id = {str(a.id): a for a in accs}
    return DraftOut(
        id=str(d.id),
        book_id=str(d.book_id),
        period_id=str(d.period_id),
        currency_id=str(d.currency_id) if getattr(d, "currency_id", None) else None,
        txn_date=d.txn_date.isoformat() if getattr(d, "txn_date", None) else None,
        source_type=d.source_type,
        source_id=d.source_id,
        version=d.version,
        description=d.description,
        status=d.status,
        posted_txn_id=str(d.posted_txn_id) if d.posted_txn_id else None,
        lines=[
            {
                "id": str(l.id),
                "line_no": l.line_no,
                "account_id": str(l.account_id),
                "account_code": by_id[str(l.account_id)].code if str(l.account_id) in by_id else "",
                "account_name": by_id[str(l.account_id)].name if str(l.account_id) in by_id else "",
                "debit": l.debit,
                "credit": l.credit,
                "memo": l.memo,
                "aux_json": l.aux_json,
            }
            for l in lines
        ],
    )


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


@router.post("/drafts", response_model=DraftCreateResponse)
def create_manual_draft(
    body: DraftCreateIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> DraftCreateResponse:
    """
    手工创建“凭证草稿”（用于日常过账、对账平衡分录等）。
    说明：
    - 草稿默认状态 DRAFT，需要先 approve 再 post
    - 借贷平衡与基本合法性在服务端先做一轮校验
    """
    # 基础校验（在 begin 之外做轻量检查也没问题，但这里保持简单）
    if not body.lines or len(body.lines) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少包含 2 条分录行")

    with db.begin():
        book = db.query(Book).filter(Book.id == body.book_id).one_or_none()
        if not book:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="账簿不存在")

        period = (
            db.query(AccountingPeriod)
            .filter(AccountingPeriod.id == body.period_id, AccountingPeriod.book_id == body.book_id)
            .one_or_none()
        )
        if not period:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会计期间不存在或不属于该账簿")

        currency_id = body.currency_id or str(book.base_currency_id)
        if not db.query(Commodity).filter(Commodity.id == currency_id).one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="币种/商品不存在")

        # 科目校验 + 借贷平衡
        total = Decimal("0")
        rows = []
        for i, ln in enumerate(body.lines, start=1):
            debit = _decimal(ln.debit)
            credit = _decimal(ln.credit)
            if debit < 0 or credit < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"第{i}行借贷金额必须>=0")
            if debit != 0 and credit != 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"第{i}行借贷不可同时填写")
            if debit == 0 and credit == 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"第{i}行借贷不可同时为 0")
            a = db.query(Account).filter(Account.id == ln.account_id).one_or_none()
            if not a or str(a.book_id) != str(body.book_id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"第{i}行科目不存在或不属于该账簿")
            if not a.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"第{i}行科目已停用")
            if not a.allow_post or bool(getattr(a, "is_placeholder", False)):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"第{i}行科目不允许记账")
            total += debit - credit
            rows.append((debit, credit, ln))

        if total != 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"借贷不平衡（sum(value)={total}）")

        sid = str(uuid.uuid4())
        txn_date = body.txn_date or datetime.utcnow()
        draft = TransactionDraft(
            book_id=body.book_id,
            period_id=body.period_id,
            currency_id=currency_id,
            txn_date=txn_date,
            source_type="MANUAL",
            source_id=sid,
            version=1,
            description=body.description or "",
            status="DRAFT",
            created_by=u.id,
            approved_by=None,
            posted_txn_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(draft)
        db.flush()

        for idx, (debit, credit, ln) in enumerate(rows, start=1):
            db.add(
                TransactionDraftLine(
                    draft_id=str(draft.id),
                    line_no=idx,
                    account_id=ln.account_id,
                    debit=debit,
                    credit=credit,
                    memo=(ln.memo or "")[:256],
                    aux_json=ln.aux_json,
                )
            )
        db.flush()
        append_revision(db, draft, action="CREATE", reason="MANUAL_CREATE", actor_id=u.id)
        db.flush()
        return DraftCreateResponse(draft_id=str(draft.id))

@router.post("/drafts/{draft_id}:precheck", response_model=PrecheckResponse)
def precheck(
    draft_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> PrecheckResponse:
    res = precheck_draft(db, draft_id)
    return PrecheckResponse(draft_id=draft_id, ok=res.ok, checks=res.checks)


@router.post("/drafts/{draft_id}:post", response_model=PostResponse)
def post(
    draft_id: str,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> PostResponse:
    try:
        r = post_draft(db, draft_id, u.id)
        return PostResponse(draft_id=draft_id, txn_id=r.txn_id, voucher_num=r.voucher_num)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except IntegrityError:
        # 避免 DB 唯一约束/并发导致的 500 → 前端“服务不可用”
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="过账发生冲突，请刷新后重试")


@router.post("/drafts/{draft_id}:approve", response_model=ApproveRejectResponse)
def approve(
    draft_id: str,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> ApproveRejectResponse:
    try:
        r = approve_draft(db, draft_id, actor_id=u.id)
        return ApproveRejectResponse(draft_id=str(r.draft_id), status=r.status)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/drafts/{draft_id}:reject", response_model=ApproveRejectResponse)
def reject(
    draft_id: str,
    payload: RejectRequest,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> ApproveRejectResponse:
    try:
        r = reject_draft(db, draft_id, actor_id=u.id, reason=payload.reason)
        return ApproveRejectResponse(draft_id=str(r.draft_id), status=r.status)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


