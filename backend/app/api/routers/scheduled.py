from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, require_roles
from app.api.schemas.scheduled import ScheduledCreateIn, ScheduledOut, ScheduledRunOut, ScheduledRunRequest
from app.infra.db.models import AccountingPeriod, ScheduledRun, ScheduledTransaction, TransactionDraft, TransactionDraftLine, utcnow

router = APIRouter(prefix="/scheduled", tags=["scheduled"])


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _ym_to_period(db: Session, book_id: str, d: date) -> AccountingPeriod | None:
    return (
        db.query(AccountingPeriod)
        .filter(AccountingPeriod.book_id == book_id, AccountingPeriod.year == d.year, AccountingPeriod.month == d.month)
        .one_or_none()
    )


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    # clamp day to last day of month
    if m == 12:
        last = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(y, m + 1, 1) - timedelta(days=1)
    day = min(d.day, last.day)
    return date(y, m, day)


def _next_date(rule: str, interval: int, d: date) -> date:
    rule_u = (rule or "").upper()
    if rule_u == "DAILY":
        return d + timedelta(days=interval)
    if rule_u == "WEEKLY":
        return d + timedelta(days=7 * interval)
    if rule_u == "MONTHLY":
        return _add_months(d, interval)
    raise ValueError("rule 必须是 DAILY/WEEKLY/MONTHLY")


def _validate_template(lines: list[dict]) -> None:
    if not lines or len(lines) < 2:
        raise ValueError("template.lines 至少 2 行")
    s_deb = sum((_decimal(x.get("debit", 0)) for x in lines), start=Decimal("0"))
    s_cred = sum((_decimal(x.get("credit", 0)) for x in lines), start=Decimal("0"))
    if s_deb != s_cred:
        raise ValueError(f"模板不平衡：debit={s_deb} credit={s_cred}")


@router.get("", response_model=list[ScheduledOut])
def list_scheduled(
    book_id: str = Query(...),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> list[ScheduledOut]:
    rows = (
        db.query(ScheduledTransaction)
        .filter(ScheduledTransaction.book_id == book_id)
        .order_by(ScheduledTransaction.next_run_date.asc())
        .all()
    )
    return [
        ScheduledOut(
            id=str(s.id),
            book_id=str(s.book_id),
            name=s.name,
            description=s.description or "",
            enabled=bool(s.enabled),
            rule=s.rule,
            interval=int(s.interval),
            next_run_date=s.next_run_date,
            end_date=s.end_date,
            template=s.template_json,
        )
        for s in rows
    ]


@router.post("", response_model=ScheduledOut)
def create_scheduled(
    payload: ScheduledCreateIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> ScheduledOut:
    tpl = payload.template.model_dump()
    _validate_template(tpl.get("lines") or [])
    if payload.end_date and payload.end_date < payload.next_run_date:
        raise HTTPException(status_code=400, detail="end_date 不能早于 next_run_date")

    with db.begin():
        s = ScheduledTransaction(
            book_id=payload.book_id,
            name=payload.name,
            description=payload.description or "",
            enabled=bool(payload.enabled),
            rule=payload.rule.upper(),
            interval=int(payload.interval),
            next_run_date=payload.next_run_date,
            end_date=payload.end_date,
            template_json=tpl,
            created_by=u.id,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(s)
        db.flush()
        return ScheduledOut(
            id=str(s.id),
            book_id=str(s.book_id),
            name=s.name,
            description=s.description or "",
            enabled=bool(s.enabled),
            rule=s.rule,
            interval=int(s.interval),
            next_run_date=s.next_run_date,
            end_date=s.end_date,
            template=s.template_json,
        )


@router.post("/{sched_id}:run", response_model=ScheduledRunOut)
def run_scheduled(
    sched_id: str,
    body: ScheduledRunRequest,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> ScheduledRunOut:
    run_d = body.run_date or date.today()
    with db.begin():
        s = db.query(ScheduledTransaction).filter(ScheduledTransaction.id == sched_id).with_for_update().one_or_none()
        if not s:
            raise HTTPException(status_code=404, detail="定期交易不存在")
        if not s.enabled:
            return ScheduledRunOut(sched_id=sched_id, run_date=run_d, status="SKIPPED", draft_id=None, error="disabled")
        if s.end_date and run_d > s.end_date:
            return ScheduledRunOut(sched_id=sched_id, run_date=run_d, status="SKIPPED", draft_id=None, error="after end_date")

        # ensure idempotent per date
        existed = db.query(ScheduledRun).filter(ScheduledRun.sched_id == s.id, ScheduledRun.run_date == run_d).one_or_none()
        if existed:
            return ScheduledRunOut(
                sched_id=sched_id,
                run_date=run_d,
                status=existed.status,
                draft_id=str(existed.draft_id) if existed.draft_id else None,
                error=existed.error or "",
            )

        # only allow run when due (run_d >= next_run_date)
        if run_d < s.next_run_date:
            r = ScheduledRun(sched_id=s.id, run_date=run_d, draft_id=None, status="SKIPPED", error="not due", created_at=utcnow())
            db.add(r)
            db.flush()
            return ScheduledRunOut(sched_id=sched_id, run_date=run_d, status=r.status, draft_id=None, error=r.error)

        period = _ym_to_period(db, s.book_id, run_d)
        if not period:
            r = ScheduledRun(sched_id=s.id, run_date=run_d, draft_id=None, status="FAILED", error="period not found", created_at=utcnow())
            db.add(r)
            db.flush()
            return ScheduledRunOut(sched_id=sched_id, run_date=run_d, status=r.status, draft_id=None, error=r.error)
        if period.status != "OPEN":
            r = ScheduledRun(sched_id=s.id, run_date=run_d, draft_id=None, status="FAILED", error="period closed", created_at=utcnow())
            db.add(r)
            db.flush()
            return ScheduledRunOut(sched_id=sched_id, run_date=run_d, status=r.status, draft_id=None, error=r.error)

        tpl = s.template_json or {}
        lines = tpl.get("lines") or []
        try:
            _validate_template(lines)
        except ValueError as e:
            r = ScheduledRun(sched_id=s.id, run_date=run_d, draft_id=None, status="FAILED", error=str(e), created_at=utcnow())
            db.add(r)
            db.flush()
            return ScheduledRunOut(sched_id=sched_id, run_date=run_d, status=r.status, draft_id=None, error=r.error)

        # compute draft version
        maxv = (
            db.query(func.coalesce(func.max(TransactionDraft.version), 0))
            .filter(TransactionDraft.book_id == s.book_id, TransactionDraft.source_type == "SCHEDULED", TransactionDraft.source_id == str(s.id))
            .scalar()
        )
        ver = int(maxv or 0) + 1
        desc = (tpl.get("description") or s.description or s.name or "").strip()
        d = TransactionDraft(
            book_id=s.book_id,
            period_id=period.id,
            source_type="SCHEDULED",
            source_id=str(s.id),
            version=ver,
            description=desc,
            status="DRAFT",
            created_by=u.id,
        )
        db.add(d)
        db.flush()
        for i, ln in enumerate(lines, start=1):
            db.add(
                TransactionDraftLine(
                    draft_id=d.id,
                    line_no=i,
                    account_id=ln["account_id"],
                    debit=_decimal(ln.get("debit", 0)),
                    credit=_decimal(ln.get("credit", 0)),
                    memo=ln.get("memo") or "",
                    aux_json=ln.get("aux_json"),
                )
            )

        r = ScheduledRun(sched_id=s.id, run_date=run_d, draft_id=d.id, status="OK", error="", created_at=utcnow())
        db.add(r)

        # advance next_run_date
        s.next_run_date = _next_date(s.rule, int(s.interval), run_d)
        s.updated_at = utcnow()
        db.flush()
        return ScheduledRunOut(sched_id=sched_id, run_date=run_d, status="OK", draft_id=str(d.id), error="")


