from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user
from app.infra.db.models import AccountingPeriod

router = APIRouter(prefix="/periods", tags=["periods"])


@router.get("")
def list_periods(
    book_id: str = Query(...),
    db: Session = Depends(db_session),
    _=Depends(get_current_user),
):
    rows = (
        db.query(AccountingPeriod)
        .filter(AccountingPeriod.book_id == book_id)
        .order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc())
        .all()
    )
    return [
        {
            "id": str(p.id),
            "book_id": str(p.book_id),
            "year": p.year,
            "month": p.month,
            "status": p.status,
        }
        for p in rows
    ]


