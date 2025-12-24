from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, require_roles
from app.api.schemas.ar_ap import (
    AgingResponse,
    InvoiceCreateIn,
    InvoiceOut,
    PaymentCreateIn,
    PaymentOut,
    PriceOut,
    PriceUpsertIn,
)
from app.application.ar_ap.service import aging_report, create_invoice, create_payment
from app.infra.db.models import Commodity, Invoice, InvoiceLine, Payment, PaymentApplication, Price

router = APIRouter(prefix="/ar-ap", tags=["ar/ap"])


def _commodity_code_by_id(db: Session, cid: str) -> str:
    c = db.query(Commodity).filter(Commodity.id == cid).one_or_none()
    return c.code if c else ""


@router.post("/prices", response_model=PriceOut)
def upsert_price(
    body: PriceUpsertIn,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> PriceOut:
    # 简化：用唯一约束 upsert（先查，存在则更新）
    com = db.query(Commodity).filter(Commodity.type == body.commodity_type, Commodity.code == body.commodity_code).one_or_none()
    cur = db.query(Commodity).filter(Commodity.type == body.currency_type, Commodity.code == body.currency_code).one_or_none()
    if not com or not cur:
        raise HTTPException(status_code=400, detail="commodity/currency 不存在")

    with db.begin():
        row = (
            db.query(Price)
            .filter(
                Price.book_id == body.book_id,
                Price.commodity_id == str(com.id),
                Price.currency_id == str(cur.id),
                Price.price_date == body.price_date,
                Price.source == body.source,
                Price.type == body.type,
            )
            .one_or_none()
        )
        if row:
            row.value = body.value
        else:
            row = Price(
                book_id=body.book_id,
                commodity_id=str(com.id),
                currency_id=str(cur.id),
                price_date=body.price_date,
                source=body.source,
                type=body.type,
                value=body.value,
            )
            db.add(row)
        db.flush()
        return PriceOut(
            id=str(row.id),
            book_id=str(row.book_id),
            commodity_code=body.commodity_code,
            currency_code=body.currency_code,
            price_date=row.price_date,
            value=row.value,
            source=row.source,
            type=row.type,
        )


@router.get("/prices/latest", response_model=PriceOut)
def get_latest_price(
    book_id: str,
    commodity_code: str,
    currency_code: str,
    as_of: date | None = None,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> PriceOut:
    com = db.query(Commodity).filter(Commodity.type == "CURRENCY", Commodity.code == commodity_code).one_or_none()
    cur = db.query(Commodity).filter(Commodity.type == "CURRENCY", Commodity.code == currency_code).one_or_none()
    if not com or not cur:
        raise HTTPException(status_code=400, detail="币种不存在")

    q = (
        db.query(Price)
        .filter(Price.book_id == book_id, Price.commodity_id == str(com.id), Price.currency_id == str(cur.id))
        .order_by(Price.price_date.desc())
    )
    if as_of:
        q = q.filter(Price.price_date <= as_of)
    row = q.first()
    if not row:
        raise HTTPException(status_code=404, detail="未找到价格/汇率")
    return PriceOut(
        id=str(row.id),
        book_id=str(row.book_id),
        commodity_code=commodity_code,
        currency_code=currency_code,
        price_date=row.price_date,
        value=row.value,
        source=row.source,
        type=row.type,
    )


@router.post("/invoices", response_model=InvoiceOut)
def create_invoice_api(
    body: InvoiceCreateIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> InvoiceOut:
    try:
        r = create_invoice(
            db,
            book_id=body.book_id,
            period_id=body.period_id,
            invoice_type=body.invoice_type,
            doc_no=body.doc_no,
            doc_date=body.doc_date,
            due_date=body.due_date,
            party_id=body.party_id,
            currency_type=body.currency_type,
            currency_code=body.currency_code,
            notes=body.notes,
            lines=[x.model_dump() for x in body.lines],
            actor_user_id=u.id,
            create_draft=body.create_draft,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    inv = db.query(Invoice).filter(Invoice.id == r.invoice_id).one()
    lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.line_no.asc()).all()
    return InvoiceOut(
        id=str(inv.id),
        book_id=str(inv.book_id),
        invoice_type=inv.invoice_type,
        status=inv.status,
        doc_no=inv.doc_no,
        doc_date=inv.doc_date,
        due_date=inv.due_date,
        party_id=str(inv.party_id) if inv.party_id else None,
        currency_code=_commodity_code_by_id(db, str(inv.currency_id)),
        notes=inv.notes,
        total_net=inv.total_net,
        total_tax=inv.total_tax,
        total_gross=inv.total_gross,
        posted_txn_id=str(inv.posted_txn_id) if inv.posted_txn_id else None,
        lot_id=str(inv.lot_id) if inv.lot_id else None,
        draft_id=r.draft_id,
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
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> InvoiceOut:
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    lines = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.line_no.asc()).all()
    return InvoiceOut(
        id=str(inv.id),
        book_id=str(inv.book_id),
        invoice_type=inv.invoice_type,
        status=inv.status,
        doc_no=inv.doc_no,
        doc_date=inv.doc_date,
        due_date=inv.due_date,
        party_id=str(inv.party_id) if inv.party_id else None,
        currency_code=_commodity_code_by_id(db, str(inv.currency_id)),
        notes=inv.notes,
        total_net=inv.total_net,
        total_tax=inv.total_tax,
        total_gross=inv.total_gross,
        posted_txn_id=str(inv.posted_txn_id) if inv.posted_txn_id else None,
        lot_id=str(inv.lot_id) if inv.lot_id else None,
        draft_id=None,
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
    )


@router.post("/payments", response_model=PaymentOut)
def create_payment_api(
    body: PaymentCreateIn,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> PaymentOut:
    try:
        r = create_payment(
            db,
            book_id=body.book_id,
            period_id=body.period_id,
            payment_type=body.payment_type,
            pay_date=body.pay_date,
            party_id=body.party_id,
            currency_type=body.currency_type,
            currency_code=body.currency_code,
            amount=body.amount,
            cash_account_id=body.cash_account_id,
            method=body.method,
            reference_no=body.reference_no,
            notes=body.notes,
            applications=[x.model_dump() for x in body.applications],
            actor_user_id=u.id,
            create_draft=body.create_draft,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    pay = db.query(Payment).filter(Payment.id == r.payment_id).one()
    apps = db.query(PaymentApplication).filter(PaymentApplication.payment_id == pay.id).all()
    return PaymentOut(
        id=str(pay.id),
        book_id=str(pay.book_id),
        payment_type=pay.payment_type,
        status=pay.status,
        pay_date=pay.pay_date,
        party_id=str(pay.party_id) if pay.party_id else None,
        currency_code=_commodity_code_by_id(db, str(pay.currency_id)),
        amount=pay.amount,
        method=pay.method,
        reference_no=pay.reference_no,
        notes=pay.notes,
        txn_id=str(pay.txn_id) if pay.txn_id else None,
        draft_id=r.draft_id,
        applications=[{"invoice_id": str(x.invoice_id), "amount": x.amount, "applied_at": x.applied_at} for x in apps],
    )


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> PaymentOut:
    pay = db.query(Payment).filter(Payment.id == payment_id).one_or_none()
    if not pay:
        raise HTTPException(status_code=404, detail="收付款不存在")
    apps = db.query(PaymentApplication).filter(PaymentApplication.payment_id == pay.id).all()
    return PaymentOut(
        id=str(pay.id),
        book_id=str(pay.book_id),
        payment_type=pay.payment_type,
        status=pay.status,
        pay_date=pay.pay_date,
        party_id=str(pay.party_id) if pay.party_id else None,
        currency_code=_commodity_code_by_id(db, str(pay.currency_id)),
        amount=pay.amount,
        method=pay.method,
        reference_no=pay.reference_no,
        notes=pay.notes,
        txn_id=str(pay.txn_id) if pay.txn_id else None,
        draft_id=None,
        applications=[{"invoice_id": str(x.invoice_id), "amount": x.amount, "applied_at": x.applied_at} for x in apps],
    )


@router.get("/aging", response_model=AgingResponse)
def aging(
    book_id: str,
    as_of: date = Query(...),
    invoice_type: str | None = Query(default=None),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> AgingResponse:
    items = aging_report(db, book_id=book_id, as_of=as_of, invoice_type=invoice_type)
    return AgingResponse(book_id=book_id, as_of=as_of, items=items)  # type: ignore[arg-type]


