from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, get_current_user, require_roles
from app.api.schemas.business import (
    BusinessDocumentOut,
    ExpenseClaimCreateIn,
    DocumentResubmitIn,
    PartyCreateIn,
    PartyOut,
    PurchaseOrderCreateIn,
    SalesOrderCreateIn,
)
from app.application.business.service import (
    create_expense_claim,
    create_party,
    create_purchase_order,
    create_sales_order,
    get_document,
    list_documents,
    list_parties,
    resubmit_document,
)
from app.infra.db.models import Attachment, BusinessDocumentLine

router = APIRouter(prefix="/business", tags=["business"])


def _date_to_dt(d) -> datetime:
    return datetime.combine(d, time.min)


def _doc_out(db: Session, doc_id: str) -> BusinessDocumentOut:
    doc = get_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="单据不存在")
    lines = (
        db.query(BusinessDocumentLine)
        .filter(BusinessDocumentLine.doc_id == doc.id)
        .order_by(BusinessDocumentLine.line_no.asc())
        .all()
    )
    atts = db.query(Attachment).filter(Attachment.owner_type == "business_document", Attachment.owner_id == doc.id).all()
    return BusinessDocumentOut(
        id=str(doc.id),
        doc_type=doc.doc_type,
        status=doc.status,
        book_id=str(doc.book_id),
        period_id=str(doc.period_id),
        doc_date=doc.doc_date.date().isoformat() if hasattr(doc.doc_date, "date") else str(doc.doc_date),
        doc_no=doc.doc_no,
        party_id=str(doc.party_id) if doc.party_id else None,
        employee_id=doc.employee_id or "",
        project=doc.project or "",
        term_days=doc.term_days,
        description=doc.description or "",
        total_amount=Decimal(str(doc.total_amount)),
        tax_amount=Decimal(str(doc.tax_amount)),
        currency_code=doc.currency_code,
        revision_no=doc.revision_no,
        draft_id=str(doc.draft_id) if doc.draft_id else None,
        rejected_reason=doc.rejected_reason or "",
        lines=[
            {
                "line_no": x.line_no,
                "description": x.description,
                "account_id": str(x.account_id),
                "quantity": x.quantity,
                "unit_price": x.unit_price,
                "tax_rate": x.tax_rate,
                "amount": x.amount,
                "tax_amount": x.tax_amount,
                "memo": x.memo,
            }
            for x in lines
        ],
        attachment_ids=[str(a.id) for a in atts],
    )


@router.get("/customers", response_model=list[PartyOut])
def list_customers(
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(get_current_user),
) -> list[PartyOut]:
    rows = list_parties(db, type_="CUSTOMER")
    return [
        PartyOut(
            id=str(p.id),
            type=p.type,
            name=p.name,
            tax_no=p.tax_no,
            credit_limit=p.credit_limit,
            payment_term_days=p.payment_term_days,
            contact_json=p.contact_json,
        )
        for p in rows
    ]


@router.post("/customers", response_model=PartyOut)
def create_customer(
    payload: PartyCreateIn,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(get_current_user),
) -> PartyOut:
    p = create_party(db, type_="CUSTOMER", payload=payload.model_dump())
    return PartyOut(
        id=str(p.id),
        type=p.type,
        name=p.name,
        tax_no=p.tax_no,
        credit_limit=p.credit_limit,
        payment_term_days=p.payment_term_days,
        contact_json=p.contact_json,
    )


@router.get("/vendors", response_model=list[PartyOut])
def list_vendors(
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(get_current_user),
) -> list[PartyOut]:
    rows = list_parties(db, type_="VENDOR")
    return [
        PartyOut(
            id=str(p.id),
            type=p.type,
            name=p.name,
            tax_no=p.tax_no,
            credit_limit=p.credit_limit,
            payment_term_days=p.payment_term_days,
            contact_json=p.contact_json,
        )
        for p in rows
    ]


@router.post("/vendors", response_model=PartyOut)
def create_vendor(
    payload: PartyCreateIn,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(get_current_user),
) -> PartyOut:
    p = create_party(db, type_="VENDOR", payload=payload.model_dump())
    return PartyOut(
        id=str(p.id),
        type=p.type,
        name=p.name,
        tax_no=p.tax_no,
        credit_limit=p.credit_limit,
        payment_term_days=p.payment_term_days,
        contact_json=p.contact_json,
    )


@router.post("/purchase-orders", response_model=BusinessDocumentOut)
def create_po(
    payload: PurchaseOrderCreateIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(get_current_user),
) -> BusinessDocumentOut:
    try:
        r = create_purchase_order(
            db,
            book_id=payload.book_id,
            period_id=payload.period_id,
            doc_no=payload.doc_no,
            doc_date=_date_to_dt(payload.doc_date),
            vendor_id=payload.vendor_id,
            project=payload.project,
            term_days=payload.term_days,
            description=payload.description,
            lines=[x.model_dump() for x in payload.lines],
            attachment_ids=payload.attachment_ids,
            actor_user_id=u.id,
        )
        return _doc_out(db, r.doc_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sales-orders", response_model=BusinessDocumentOut)
def create_so(
    payload: SalesOrderCreateIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(get_current_user),
) -> BusinessDocumentOut:
    try:
        r = create_sales_order(
            db,
            book_id=payload.book_id,
            period_id=payload.period_id,
            doc_no=payload.doc_no,
            doc_date=_date_to_dt(payload.doc_date),
            customer_id=payload.customer_id,
            project=payload.project,
            term_days=payload.term_days,
            description=payload.description,
            lines=[x.model_dump() for x in payload.lines],
            attachment_ids=payload.attachment_ids,
            actor_user_id=u.id,
        )
        return _doc_out(db, r.doc_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/expense-claims", response_model=BusinessDocumentOut)
def create_ec(
    payload: ExpenseClaimCreateIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(get_current_user),
) -> BusinessDocumentOut:
    try:
        r = create_expense_claim(
            db,
            book_id=payload.book_id,
            period_id=payload.period_id,
            doc_no=payload.doc_no,
            doc_date=_date_to_dt(payload.doc_date),
            employee_id=payload.employee_id,
            project=payload.project,
            description=payload.description,
            lines=[x.model_dump() for x in payload.lines],
            attachment_ids=payload.attachment_ids,
            actor_user_id=u.id,
        )
        return _doc_out(db, r.doc_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/documents", response_model=list[BusinessDocumentOut])
def list_docs(
    doc_type: str = Query(..., description="PURCHASE_ORDER/SALES_ORDER/EXPENSE_CLAIM"),
    status_: str | None = Query(default=None, alias="status"),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(get_current_user),
) -> list[BusinessDocumentOut]:
    rows = list_documents(db, doc_type=doc_type, status=status_)
    return [_doc_out(db, str(d.id)) for d in rows]


@router.get("/documents/{doc_id}", response_model=BusinessDocumentOut)
def get_doc(
    doc_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(get_current_user),
) -> BusinessDocumentOut:
    return _doc_out(db, doc_id)


@router.post("/documents/{doc_id}:resubmit", response_model=BusinessDocumentOut)
def resubmit(
    doc_id: str,
    payload: DocumentResubmitIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(get_current_user),
) -> BusinessDocumentOut:
    try:
        patch = payload.model_dump()
        if patch.get("doc_date") is not None:
            patch["doc_date"] = _date_to_dt(patch["doc_date"])
        r = resubmit_document(db, doc_id=doc_id, patch=patch, actor_user_id=u.id)
        return _doc_out(db, r.doc_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


