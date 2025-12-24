from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.application.gl.draft_workflow import append_revision
from app.infra.db.models import (
    Account,
    AccountingPeriod,
    Book,
    Commodity,
    Invoice,
    InvoiceLine,
    Lot,
    Payment,
    PaymentApplication,
    Price,
    TransactionDraft,
    TransactionDraftLine,
)


def _d(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _q(v: Decimal, places: str) -> Decimal:
    return v.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _q2(v: Decimal) -> Decimal:
    return _q(v, "0.01")


def _require_period_open(db: Session, period_id: str) -> AccountingPeriod:
    p = db.query(AccountingPeriod).filter(AccountingPeriod.id == period_id).one_or_none()
    if not p or p.status != "OPEN":
        raise ValueError("会计期间未开放/不存在")
    return p


def _require_book(db: Session, book_id: str) -> Book:
    b = db.query(Book).filter(Book.id == book_id).one_or_none()
    if not b:
        raise ValueError("账簿不存在")
    return b


def _require_commodity_by_code(db: Session, type_: str, code: str) -> Commodity:
    c = db.query(Commodity).filter(Commodity.type == type_, Commodity.code == code).one_or_none()
    if not c:
        raise ValueError(f"币种/商品不存在: {type_}:{code}")
    return c


def _require_account(db: Session, book_id: str, account_id: str) -> Account:
    a = db.query(Account).filter(Account.id == account_id).one_or_none()
    if not a:
        raise ValueError(f"科目不存在: {account_id}")
    if str(a.book_id) != str(book_id):
        raise ValueError("科目不属于当前账簿")
    if not a.is_active:
        raise ValueError(f"科目已停用: {a.code} {a.name}")
    if not a.allow_post:
        raise ValueError(f"科目不允许记账: {a.code} {a.name}")
    return a


def _require_account_by_code(db: Session, book_id: str, code: str) -> Account:
    a = db.query(Account).filter(Account.book_id == book_id, Account.code == code).one_or_none()
    if not a:
        raise ValueError(f"缺少科目(code={code})，请先初始化科目树")
    if not a.is_active or not a.allow_post:
        raise ValueError(f"科目不可用(code={code})")
    return a


def _calc_invoice_lines(lines: list[dict]) -> tuple[list[dict], Decimal, Decimal, Decimal]:
    out: list[dict] = []
    total_net = Decimal("0")
    total_tax = Decimal("0")
    for i, ln in enumerate(lines, start=1):
        qty = _d(ln.get("quantity", 1))
        price = _d(ln.get("unit_price", 0))
        if qty <= 0:
            raise ValueError(f"第{i}行数量必须>0")
        if price < 0:
            raise ValueError(f"第{i}行单价必须>=0")
        rate = _d(ln.get("tax_rate", 0))
        if rate < 0 or rate > 1:
            raise ValueError(f"第{i}行税率非法（应为 0~1）")
        net = _q2(qty * price)
        tax = _q2(net * rate)
        out.append(
            {
                "line_no": i,
                "description": ln.get("description", "") or "",
                "account_id": ln["account_id"],
                "quantity": qty,
                "unit_price": price,
                "tax_rate": rate,
                "amount": net,
                "tax_amount": tax,
                "memo": ln.get("memo", "") or "",
            }
        )
        total_net += net
        total_tax += tax
    total_net = _q2(total_net)
    total_tax = _q2(total_tax)
    total_gross = _q2(total_net + total_tax)
    return out, total_net, total_tax, total_gross


def _get_or_create_invoice_lot(db: Session, *, book_id: str, invoice: Invoice, control_account_id: str) -> Lot:
    if invoice.lot_id:
        lot = db.query(Lot).filter(Lot.id == invoice.lot_id).one_or_none()
        if lot:
            return lot
    lot = Lot(
        book_id=book_id,
        account_id=control_account_id,
        title=f"{invoice.invoice_type} 发票 {invoice.doc_no}".strip(),
        notes="",
        is_closed=False,
        opened_at=datetime.utcnow(),
        closed_at=None,
    )
    db.add(lot)
    db.flush()
    invoice.lot_id = lot.id
    db.flush()
    return lot


@dataclass(frozen=True)
class CreateInvoiceResult:
    invoice_id: str
    draft_id: str | None


def create_invoice(
    db: Session,
    *,
    book_id: str,
    period_id: str,
    invoice_type: str,
    doc_no: str,
    doc_date: datetime,
    due_date: date | None,
    party_id: str | None,
    currency_type: str,
    currency_code: str,
    notes: str,
    lines: list[dict],
    actor_user_id: str | None,
    create_draft: bool,
) -> CreateInvoiceResult:
    with db.begin():
        _require_period_open(db, period_id)
        _require_book(db, book_id)
        cur = _require_commodity_by_code(db, currency_type, currency_code)

        norm_lines, total_net, total_tax, total_gross = _calc_invoice_lines(lines)
        for ln in norm_lines:
            _require_account(db, book_id, ln["account_id"])

        inv = Invoice(
            book_id=book_id,
            invoice_type=invoice_type,
            status="DRAFT",
            doc_no=doc_no or "",
            doc_date=doc_date,
            due_date=due_date,
            party_id=party_id,
            currency_id=str(cur.id),
            notes=notes or "",
            total_net=total_net,
            total_tax=total_tax,
            total_gross=total_gross,
            posted_txn_id=None,
            lot_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(inv)
        db.flush()

        for ln in norm_lines:
            db.add(
                InvoiceLine(
                    invoice_id=str(inv.id),
                    line_no=ln["line_no"],
                    description=ln["description"],
                    account_id=ln["account_id"],
                    quantity=ln["quantity"],
                    unit_price=ln["unit_price"],
                    tax_rate=ln["tax_rate"],
                    amount=ln["amount"],
                    tax_amount=ln["tax_amount"],
                    memo=ln["memo"],
                )
            )
        db.flush()

        draft_id: str | None = None
        if create_draft:
            # 控制科目：沿用现有默认科目编码（后续可用 ObjectKV 做成可配置）
            if invoice_type == "AR":
                control = _require_account_by_code(db, book_id, "1122")
            elif invoice_type == "AP":
                control = _require_account_by_code(db, book_id, "2001")
            else:
                raise ValueError("invoice_type 非法")

            lot = _get_or_create_invoice_lot(db, book_id=book_id, invoice=inv, control_account_id=str(control.id))

            draft = TransactionDraft(
                book_id=book_id,
                period_id=period_id,
                currency_id=str(cur.id),
                txn_date=doc_date,
                source_type=f"INVOICE_{invoice_type}",
                source_id=str(inv.id),
                version=1,
                description=f"发票:{inv.doc_no}".strip(),
                status="DRAFT",
                created_by=actor_user_id,
                approved_by=None,
                posted_txn_id=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(draft)
            db.flush()

            def add_line(no: int, account_id: str, debit: Decimal, credit: Decimal, memo: str, aux: dict) -> None:
                db.add(
                    TransactionDraftLine(
                        draft_id=str(draft.id),
                        line_no=no,
                        account_id=account_id,
                        debit=_q2(debit),
                        credit=_q2(credit),
                        memo=memo or "",
                        aux_json=aux,
                    )
                )

            line_no = 1
            if invoice_type == "AR":
                # credit: revenue lines (net), credit: tax payable (tax), debit: AR control (gross)
                tax_payable = _require_account_by_code(db, book_id, "2221")
                total_tax2 = Decimal("0")
                total_net2 = Decimal("0")
                for ln in norm_lines:
                    total_net2 += _d(ln["amount"])
                    total_tax2 += _d(ln["tax_amount"])
                    add_line(
                        line_no,
                        ln["account_id"],
                        debit=Decimal("0"),
                        credit=_d(ln["amount"]),
                        memo=ln["memo"] or ln["description"] or "贷：收入",
                        aux={"owner": "invoice", "invoice_id": str(inv.id), "invoice_line_no": ln["line_no"], "role": "REVENUE"},
                    )
                    line_no += 1
                total_tax2 = _q2(total_tax2)
                if total_tax2 != 0:
                    add_line(
                        line_no,
                        str(tax_payable.id),
                        debit=Decimal("0"),
                        credit=total_tax2,
                        memo="贷：应交税费",
                        aux={"owner": "invoice", "invoice_id": str(inv.id), "role": "TAX"},
                    )
                    line_no += 1
                add_line(
                    line_no,
                    str(control.id),
                    debit=_q2(_d(total_net2) + _d(total_tax2)),
                    credit=Decimal("0"),
                    memo="借：应收账款",
                    aux={"owner": "invoice", "invoice_id": str(inv.id), "role": "AR", "lot_id": str(lot.id)},
                )
            else:
                # AP: debit expense/asset gross, credit AP control gross
                total_gross2 = Decimal("0")
                for ln in norm_lines:
                    gross = _q2(_d(ln["amount"]) + _d(ln["tax_amount"]))
                    total_gross2 += gross
                    add_line(
                        line_no,
                        ln["account_id"],
                        debit=gross,
                        credit=Decimal("0"),
                        memo=ln["memo"] or ln["description"] or "借：成本/费用",
                        aux={"owner": "invoice", "invoice_id": str(inv.id), "invoice_line_no": ln["line_no"], "role": "EXPENSE"},
                    )
                    line_no += 1
                add_line(
                    line_no,
                    str(control.id),
                    debit=Decimal("0"),
                    credit=_q2(total_gross2),
                    memo="贷：应付账款",
                    aux={"owner": "invoice", "invoice_id": str(inv.id), "role": "AP", "lot_id": str(lot.id)},
                )

            db.flush()
            append_revision(db, draft, action="CREATE", reason="", actor_id=actor_user_id)
            db.flush()
            draft_id = str(draft.id)

        return CreateInvoiceResult(invoice_id=str(inv.id), draft_id=draft_id)


@dataclass(frozen=True)
class CreatePaymentResult:
    payment_id: str
    draft_id: str | None


def create_payment(
    db: Session,
    *,
    book_id: str,
    period_id: str,
    payment_type: str,
    pay_date: datetime,
    party_id: str | None,
    currency_type: str,
    currency_code: str,
    amount: Decimal,
    cash_account_id: str,
    method: str,
    reference_no: str,
    notes: str,
    applications: list[dict],
    actor_user_id: str | None,
    create_draft: bool,
) -> CreatePaymentResult:
    with db.begin():
        _require_period_open(db, period_id)
        _require_book(db, book_id)
        cur = _require_commodity_by_code(db, currency_type, currency_code)

        cash = _require_account(db, book_id, cash_account_id)
        if str(cash.commodity_id) != str(cur.id):
            # 先做最小约束：现金/银行科目币种必须等于付款币种（避免复杂 FX 现金账户）
            raise ValueError("收/付款币种必须与现金/银行科目币种一致（当前版本限制）")

        apps = applications or []
        if apps:
            total_apply = _q2(sum((_d(x["amount"]) for x in apps), Decimal("0")))
            if amount and _q2(_d(amount)) != total_apply:
                raise ValueError("payment.amount 必须等于 applications 合计（当前版本限制）")
            amount = total_apply
        amount = _q2(_d(amount))
        if amount <= 0:
            raise ValueError("收/付款金额必须 > 0")

        pay = Payment(
            book_id=book_id,
            payment_type=payment_type,
            status="DRAFT",
            pay_date=pay_date,
            party_id=party_id,
            currency_id=str(cur.id),
            amount=amount,
            method=method or "",
            reference_no=reference_no or "",
            notes=notes or "",
            txn_id=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(pay)
        db.flush()

        invoice_rows: dict[str, Invoice] = {}
        for x in apps:
            inv = db.query(Invoice).filter(Invoice.id == x["invoice_id"]).one_or_none()
            if not inv:
                raise ValueError(f"发票不存在: {x['invoice_id']}")
            if str(inv.book_id) != str(book_id):
                raise ValueError("发票不属于当前账簿")
            if str(inv.currency_id) != str(cur.id):
                raise ValueError("收/付款币种必须与发票币种一致（当前版本限制）")
            if payment_type == "RECEIPT" and inv.invoice_type != "AR":
                raise ValueError("收款只能核销 AR 发票")
            if payment_type == "DISBURSEMENT" and inv.invoice_type != "AP":
                raise ValueError("付款只能核销 AP 发票")
            invoice_rows[str(inv.id)] = inv

        # 写应用关系（核销）
        for x in apps:
            inv = invoice_rows[x["invoice_id"]]
            amt = _q2(_d(x["amount"]))
            if amt <= 0:
                raise ValueError("核销金额必须 > 0")
            db.add(PaymentApplication(payment_id=str(pay.id), invoice_id=str(inv.id), amount=amt, applied_at=datetime.utcnow()))
        db.flush()

        draft_id: str | None = None
        if create_draft:
            # 控制科目：AR=1122, AP=2001
            if payment_type == "RECEIPT":
                control = _require_account_by_code(db, book_id, "1122")
            elif payment_type == "DISBURSEMENT":
                control = _require_account_by_code(db, book_id, "2001")
            else:
                raise ValueError("payment_type 非法")

            draft = TransactionDraft(
                book_id=book_id,
                period_id=period_id,
                currency_id=str(cur.id),
                txn_date=pay_date,
                source_type=f"PAYMENT_{payment_type}",
                source_id=str(pay.id),
                version=1,
                description=f"收付款:{pay.reference_no}".strip() if pay.reference_no else "收付款",
                status="DRAFT",
                created_by=actor_user_id,
                approved_by=None,
                posted_txn_id=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(draft)
            db.flush()

            def add_line(no: int, account_id: str, debit: Decimal, credit: Decimal, memo: str, aux: dict) -> None:
                db.add(
                    TransactionDraftLine(
                        draft_id=str(draft.id),
                        line_no=no,
                        account_id=account_id,
                        debit=_q2(debit),
                        credit=_q2(credit),
                        memo=memo or "",
                        aux_json=aux,
                    )
                )

            line_no = 1
            if payment_type == "RECEIPT":
                # 借：现金/银行；贷：应收（按每张发票拆行并带 lot_id）
                add_line(
                    line_no,
                    str(cash.id),
                    debit=amount,
                    credit=Decimal("0"),
                    memo="借：现金/银行",
                    aux={"owner": "payment", "payment_id": str(pay.id), "role": "CASH"},
                )
                line_no += 1
                for x in apps:
                    inv = invoice_rows[x["invoice_id"]]
                    lot = _get_or_create_invoice_lot(db, book_id=book_id, invoice=inv, control_account_id=str(control.id))
                    add_line(
                        line_no,
                        str(control.id),
                        debit=Decimal("0"),
                        credit=_q2(_d(x["amount"])),
                        memo="贷：应收账款",
                        aux={"owner": "payment", "payment_id": str(pay.id), "invoice_id": str(inv.id), "role": "AR", "lot_id": str(lot.id)},
                    )
                    line_no += 1
            else:
                # 贷：现金/银行；借：应付（按发票拆行并带 lot_id）
                add_line(
                    line_no,
                    str(cash.id),
                    debit=Decimal("0"),
                    credit=amount,
                    memo="贷：现金/银行",
                    aux={"owner": "payment", "payment_id": str(pay.id), "role": "CASH"},
                )
                line_no += 1
                for x in apps:
                    inv = invoice_rows[x["invoice_id"]]
                    lot = _get_or_create_invoice_lot(db, book_id=book_id, invoice=inv, control_account_id=str(control.id))
                    add_line(
                        line_no,
                        str(control.id),
                        debit=_q2(_d(x["amount"])),
                        credit=Decimal("0"),
                        memo="借：应付账款",
                        aux={"owner": "payment", "payment_id": str(pay.id), "invoice_id": str(inv.id), "role": "AP", "lot_id": str(lot.id)},
                    )
                    line_no += 1

            db.flush()
            append_revision(db, draft, action="CREATE", reason="", actor_id=actor_user_id)
            db.flush()
            draft_id = str(draft.id)

        return CreatePaymentResult(payment_id=str(pay.id), draft_id=draft_id)


def bucket_for_days(days_past_due: int) -> str:
    if days_past_due <= 0:
        return "CURRENT"
    if days_past_due <= 30:
        return "1-30"
    if days_past_due <= 60:
        return "31-60"
    if days_past_due <= 90:
        return "61-90"
    return "90+"


def aging_report(db: Session, *, book_id: str, as_of: date, invoice_type: str | None = None) -> list[dict]:
    # 纯查询：不显式 begin
    q = db.query(Invoice).filter(Invoice.book_id == book_id).filter(Invoice.status.in_(["POSTED", "PAID"]))
    if invoice_type:
        q = q.filter(Invoice.invoice_type == invoice_type)
    invoices = q.order_by(Invoice.doc_date.desc()).limit(500).all()
    if not invoices:
        return []

    inv_ids = [str(x.id) for x in invoices]
    apps = db.query(PaymentApplication.invoice_id, sa.func.sum(PaymentApplication.amount)).filter(PaymentApplication.invoice_id.in_(inv_ids)).group_by(PaymentApplication.invoice_id).all()  # type: ignore[name-defined]
    applied = {str(iid): _q2(_d(s or 0)) for iid, s in apps}

    # commodity code lookup
    cur_ids = list({str(x.currency_id) for x in invoices})
    curs = db.query(Commodity).filter(Commodity.id.in_(cur_ids)).all()
    cur_by_id = {str(c.id): c.code for c in curs}

    out: list[dict] = []
    for inv in invoices:
        app_amt = applied.get(str(inv.id), Decimal("0"))
        outstanding = _q2(_d(inv.total_gross) - app_amt)
        if outstanding < 0:
            outstanding = Decimal("0")
        dd = inv.due_date
        days = 0
        if dd:
            days = max(0, (as_of - dd).days)
        out.append(
            {
                "invoice_id": str(inv.id),
                "invoice_type": inv.invoice_type,
                "party_id": str(inv.party_id) if inv.party_id else None,
                "doc_no": inv.doc_no,
                "doc_date": inv.doc_date,
                "due_date": inv.due_date,
                "currency_code": cur_by_id.get(str(inv.currency_id), ""),
                "total_gross": _q2(_d(inv.total_gross)),
                "applied_amount": app_amt,
                "outstanding_amount": outstanding,
                "days_past_due": int(days),
                "bucket": bucket_for_days(int(days)),
            }
        )
    return out


