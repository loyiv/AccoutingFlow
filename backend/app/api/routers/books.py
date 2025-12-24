from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user
from app.infra.db.models import Book

router = APIRouter(prefix="/books", tags=["books"])


@router.get("")
def list_books(db: Session = Depends(db_session), _=Depends(get_current_user)):
    rows = db.query(Book).order_by(Book.created_at.asc()).all()
    return [{"id": str(b.id), "name": b.name, "base_currency_id": str(b.base_currency_id)} for b in rows]


