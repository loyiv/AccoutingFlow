from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infra.db.models import BusinessDocument, TransactionDraft, TransactionDraftLine, TransactionDraftRevision


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _draft_snapshot(db: Session, draft: TransactionDraft) -> dict:
    lines = (
        db.query(TransactionDraftLine)
        .filter(TransactionDraftLine.draft_id == draft.id)
        .order_by(TransactionDraftLine.line_no.asc())
        .all()
    )
    return {
        "draft": {
            "id": draft.id,
            "book_id": draft.book_id,
            "period_id": draft.period_id,
            "source_type": draft.source_type,
            "source_id": draft.source_id,
            "version": draft.version,
            "description": draft.description,
            "status": draft.status,
            "posted_txn_id": draft.posted_txn_id,
        },
        "lines": [
            {
                "line_no": l.line_no,
                "account_id": l.account_id,
                "debit": str(_decimal(l.debit)),
                "credit": str(_decimal(l.credit)),
                "memo": l.memo,
                "aux_json": l.aux_json,
            }
            for l in lines
        ],
    }


def append_revision(db: Session, draft: TransactionDraft, action: str, reason: str, actor_id: str | None) -> None:
    last = (
        db.query(TransactionDraftRevision)
        .filter(TransactionDraftRevision.draft_id == draft.id)
        .order_by(TransactionDraftRevision.rev_no.desc())
        .limit(1)
        .one_or_none()
    )
    next_no = (last.rev_no + 1) if last else 1
    rev = TransactionDraftRevision(
        draft_id=draft.id,
        rev_no=next_no,
        action=action,
        reason=reason or "",
        payload_json=_draft_snapshot(db, draft),
        actor_id=actor_id,
        at=datetime.utcnow(),
    )
    db.add(rev)


@dataclass(frozen=True)
class ApproveRejectResult:
    draft_id: str
    status: str


def approve_draft(db: Session, draft_id: str, actor_id: str | None) -> ApproveRejectResult:
    with db.begin():
        draft = (
            db.query(TransactionDraft)
            .filter(TransactionDraft.id == draft_id)
            .with_for_update()
            .one_or_none()
        )
        if not draft:
            raise ValueError("草稿不存在")
        if draft.status in ("POSTED",):
            raise ValueError("草稿已过账，禁止审批")
        if draft.status in ("APPROVED",):
            return ApproveRejectResult(draft_id=draft.id, status=draft.status)

        draft.status = "APPROVED"
        draft.approved_by = actor_id
        # 若来源是业务单据：同步状态
        if draft.source_type in ("PURCHASE_ORDER", "SALES_ORDER", "EXPENSE_CLAIM"):
            doc = db.query(BusinessDocument).filter(BusinessDocument.id == draft.source_id).one_or_none()
            if doc:
                doc.status = "APPROVED"
                doc.approved_by = actor_id
                doc.updated_at = datetime.utcnow()
        append_revision(db, draft, action="APPROVE", reason="", actor_id=actor_id)
        db.flush()
        return ApproveRejectResult(draft_id=draft.id, status=draft.status)


def reject_draft(db: Session, draft_id: str, actor_id: str | None, reason: str) -> ApproveRejectResult:
    with db.begin():
        draft = (
            db.query(TransactionDraft)
            .filter(TransactionDraft.id == draft_id)
            .with_for_update()
            .one_or_none()
        )
        if not draft:
            raise ValueError("草稿不存在")
        if draft.status in ("POSTED",):
            raise ValueError("草稿已过账，禁止退回")

        draft.status = "REJECTED"
        # 若来源是业务单据：同步状态与原因
        if draft.source_type in ("PURCHASE_ORDER", "SALES_ORDER", "EXPENSE_CLAIM"):
            doc = db.query(BusinessDocument).filter(BusinessDocument.id == draft.source_id).one_or_none()
            if doc:
                doc.status = "REJECTED"
                doc.rejected_by = actor_id
                doc.rejected_reason = reason or ""
                doc.updated_at = datetime.utcnow()
        append_revision(db, draft, action="REJECT", reason=reason or "", actor_id=actor_id)
        db.flush()
        return ApproveRejectResult(draft_id=draft.id, status=draft.status)


