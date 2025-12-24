from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.application.gl.draft_workflow import append_revision
from app.infra.db.models import (
    Account,
    AccountingPeriod,
    Attachment,
    BusinessDocument,
    BusinessDocumentLine,
    Party,
    TransactionDraft,
    TransactionDraftLine,
)


def _d(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _require_period_open(db: Session, period_id: str) -> AccountingPeriod:
    p = db.query(AccountingPeriod).filter(AccountingPeriod.id == period_id).one_or_none()
    if not p or p.status != "OPEN":
        raise ValueError("会计期间未开放/不存在")
    return p


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
    if not a.allow_post or not a.is_active:
        raise ValueError(f"科目不可用(code={code})")
    return a


def _attach_to_owner(db: Session, attachment_ids: list[str], owner_type: str, owner_id: str) -> list[str]:
    if not attachment_ids:
        return []
    rows = db.query(Attachment).filter(Attachment.id.in_(attachment_ids)).all()
    by_id = {str(a.id): a for a in rows}
    missing = [aid for aid in attachment_ids if aid not in by_id]
    if missing:
        raise ValueError(f"附件不存在: {missing[:3]}")
    for a in rows:
        a.owner_type = owner_type
        a.owner_id = owner_id
    return attachment_ids


def _auto_doc_no(doc_type: str) -> str:
    # 最小实现：用 UTC 时间生成可读编号，避免 doc_no 为空触发唯一约束
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S%f")
    prefix = {"PURCHASE_ORDER": "PO", "SALES_ORDER": "SO", "EXPENSE_CLAIM": "EC"}.get(doc_type, "DOC")
    return f"{prefix}-{stamp}"


def _calc_lines(lines: list[dict], default_tax_rate: Decimal) -> tuple[list[dict], Decimal, Decimal]:
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
        tax_rate = ln.get("tax_rate", None)
        rate = _d(tax_rate) if tax_rate is not None else default_tax_rate
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
    return out, total_gross, total_tax


def _create_draft_for_doc(
    db: Session,
    *,
    doc: BusinessDocument,
    lines: list[dict],
    actor_user_id: str | None,
) -> TransactionDraft:
    draft = TransactionDraft(
        book_id=doc.book_id,
        period_id=doc.period_id,
        source_type=doc.doc_type,
        source_id=str(doc.id),
        version=doc.revision_no,
        description=f"{doc.doc_type}:{doc.doc_no} {doc.description}".strip(),
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
                draft_id=draft.id,
                line_no=no,
                account_id=account_id,
                debit=_q2(debit),
                credit=_q2(credit),
                memo=memo or "",
                aux_json=aux,
            )
        )

    # 生成分录草稿
    if doc.doc_type == "PURCHASE_ORDER":
        ap = _require_account_by_code(db, doc.book_id, "2001")
        line_no = 1
        total_gross = Decimal("0")
        for ln in lines:
            gross = _q2(_d(ln["amount"]) + _d(ln["tax_amount"]))
            total_gross += gross
            _require_account(db, doc.book_id, ln["account_id"])
            add_line(
                line_no,
                ln["account_id"],
                debit=gross,
                credit=Decimal("0"),
                memo=ln.get("memo", "") or ln.get("description", ""),
                aux={"doc_type": doc.doc_type, "doc_id": str(doc.id), "doc_line_no": ln["line_no"]},
            )
            line_no += 1
        add_line(
            line_no,
            str(ap.id),
            debit=Decimal("0"),
            credit=_q2(total_gross),
            memo="贷：应付账款",
            aux={"doc_type": doc.doc_type, "doc_id": str(doc.id), "role": "AP"},
        )

    elif doc.doc_type == "SALES_ORDER":
        ar = _require_account_by_code(db, doc.book_id, "1122")
        tax_payable = _require_account_by_code(db, doc.book_id, "2221")
        line_no = 1
        total_gross = Decimal("0")
        total_tax = Decimal("0")
        for ln in lines:
            net = _d(ln["amount"])
            tax = _d(ln["tax_amount"])
            gross = _q2(net + tax)
            total_gross += gross
            total_tax += tax
            _require_account(db, doc.book_id, ln["account_id"])
            add_line(
                line_no,
                ln["account_id"],
                debit=Decimal("0"),
                credit=_q2(net),
                memo=ln.get("memo", "") or ln.get("description", "") or "贷：收入",
                aux={"doc_type": doc.doc_type, "doc_id": str(doc.id), "doc_line_no": ln["line_no"], "role": "REVENUE"},
            )
            line_no += 1
        if _q2(total_tax) != 0:
            add_line(
                line_no,
                str(tax_payable.id),
                debit=Decimal("0"),
                credit=_q2(total_tax),
                memo="贷：应交税费",
                aux={"doc_type": doc.doc_type, "doc_id": str(doc.id), "role": "TAX"},
            )
            line_no += 1
        add_line(
            line_no,
            str(ar.id),
            debit=_q2(total_gross),
            credit=Decimal("0"),
            memo="借：应收账款",
            aux={"doc_type": doc.doc_type, "doc_id": str(doc.id), "role": "AR"},
        )

    elif doc.doc_type == "EXPENSE_CLAIM":
        payroll = _require_account_by_code(db, doc.book_id, "2211")
        line_no = 1
        total_gross = Decimal("0")
        for ln in lines:
            gross = _q2(_d(ln["amount"]) + _d(ln["tax_amount"]))
            total_gross += gross
            _require_account(db, doc.book_id, ln["account_id"])
            add_line(
                line_no,
                ln["account_id"],
                debit=gross,
                credit=Decimal("0"),
                memo=ln.get("memo", "") or ln.get("description", ""),
                aux={"doc_type": doc.doc_type, "doc_id": str(doc.id), "doc_line_no": ln["line_no"], "role": "EXPENSE"},
            )
            line_no += 1
        add_line(
            line_no,
            str(payroll.id),
            debit=Decimal("0"),
            credit=_q2(total_gross),
            memo="贷：应付职工薪酬",
            aux={"doc_type": doc.doc_type, "doc_id": str(doc.id), "role": "PAYROLL"},
        )
    else:
        raise ValueError("未知单据类型")

    db.flush()
    append_revision(db, draft, action="CREATE", reason="", actor_id=actor_user_id)
    return draft


@dataclass(frozen=True)
class CreateDocResult:
    doc_id: str
    draft_id: str


def create_purchase_order(
    db: Session,
    *,
    book_id: str,
    period_id: str,
    doc_no: str,
    doc_date: datetime,
    vendor_id: str,
    project: str,
    term_days: int | None,
    description: str,
    lines: list[dict],
    attachment_ids: list[str],
    actor_user_id: str | None,
) -> CreateDocResult:
    with db.begin():
        _require_period_open(db, period_id)
        vendor = db.query(Party).filter(Party.id == vendor_id, Party.type == "VENDOR").one_or_none()
        if not vendor:
            raise ValueError("供应商不存在")
        max_term = vendor.payment_term_days or (60 if (vendor.contact_json or {}).get("annual_purchase_over_10m") else 30)
        if term_days is None:
            term_days = max_term
        if term_days > max_term:
            raise ValueError("账期超限")

        calc_lines, total_amount, tax_amount = _calc_lines(lines, default_tax_rate=Decimal("0.07"))

        doc = BusinessDocument(
            doc_type="PURCHASE_ORDER",
            status="SUBMITTED",
            book_id=book_id,
            period_id=period_id,
            doc_date=doc_date,
            doc_no=doc_no or _auto_doc_no("PURCHASE_ORDER"),
            party_id=vendor_id,
            employee_id="",
            project=project or "",
            term_days=term_days,
            description=description or "",
            total_amount=total_amount,
            tax_amount=tax_amount,
            currency_code="CNY",
            revision_no=1,
            draft_id=None,
            created_by=actor_user_id,
            approved_by=None,
            rejected_by=None,
            rejected_reason="",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(doc)
        db.flush()

        for ln in calc_lines:
            db.add(
                BusinessDocumentLine(
                    doc_id=doc.id,
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

        draft = _create_draft_for_doc(db, doc=doc, lines=calc_lines, actor_user_id=actor_user_id)
        doc.draft_id = draft.id
        _attach_to_owner(db, attachment_ids, owner_type="business_document", owner_id=str(doc.id))
        db.flush()

        return CreateDocResult(doc_id=str(doc.id), draft_id=str(draft.id))


def create_sales_order(
    db: Session,
    *,
    book_id: str,
    period_id: str,
    doc_no: str,
    doc_date: datetime,
    customer_id: str,
    project: str,
    term_days: int | None,
    description: str,
    lines: list[dict],
    attachment_ids: list[str],
    actor_user_id: str | None,
) -> CreateDocResult:
    with db.begin():
        _require_period_open(db, period_id)
        cust = db.query(Party).filter(Party.id == customer_id, Party.type == "CUSTOMER").one_or_none()
        if not cust:
            raise ValueError("客户不存在")
        grade = (cust.contact_json or {}).get("grade")
        max_term = cust.payment_term_days or (60 if grade == "A" else 30)
        if term_days is None:
            term_days = max_term
        if term_days > max_term:
            raise ValueError("账期超限")

        calc_lines, total_amount, tax_amount = _calc_lines(lines, default_tax_rate=Decimal("0.13"))
        # 信用额度校验（最小实现）
        if cust.credit_limit is not None and _d(total_amount) > _d(cust.credit_limit):
            raise ValueError("客户信用额度不足")

        doc = BusinessDocument(
            doc_type="SALES_ORDER",
            status="SUBMITTED",
            book_id=book_id,
            period_id=period_id,
            doc_date=doc_date,
            doc_no=doc_no or _auto_doc_no("SALES_ORDER"),
            party_id=customer_id,
            employee_id="",
            project=project or "",
            term_days=term_days,
            description=description or "",
            total_amount=total_amount,
            tax_amount=tax_amount,
            currency_code="CNY",
            revision_no=1,
            draft_id=None,
            created_by=actor_user_id,
            approved_by=None,
            rejected_by=None,
            rejected_reason="",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(doc)
        db.flush()

        for ln in calc_lines:
            db.add(
                BusinessDocumentLine(
                    doc_id=doc.id,
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

        draft = _create_draft_for_doc(db, doc=doc, lines=calc_lines, actor_user_id=actor_user_id)
        doc.draft_id = draft.id
        _attach_to_owner(db, attachment_ids, owner_type="business_document", owner_id=str(doc.id))
        db.flush()

        return CreateDocResult(doc_id=str(doc.id), draft_id=str(draft.id))


def create_expense_claim(
    db: Session,
    *,
    book_id: str,
    period_id: str,
    doc_no: str,
    doc_date: datetime,
    employee_id: str,
    project: str,
    description: str,
    lines: list[dict],
    attachment_ids: list[str],
    actor_user_id: str | None,
) -> CreateDocResult:
    with db.begin():
        _require_period_open(db, period_id)
        calc_lines, total_amount, tax_amount = _calc_lines(lines, default_tax_rate=Decimal("0.07"))

        doc = BusinessDocument(
            doc_type="EXPENSE_CLAIM",
            status="SUBMITTED",
            book_id=book_id,
            period_id=period_id,
            doc_date=doc_date,
            doc_no=doc_no or _auto_doc_no("EXPENSE_CLAIM"),
            party_id=None,
            employee_id=employee_id or "",
            project=project or "",
            term_days=None,
            description=description or "",
            total_amount=total_amount,
            tax_amount=tax_amount,
            currency_code="CNY",
            revision_no=1,
            draft_id=None,
            created_by=actor_user_id,
            approved_by=None,
            rejected_by=None,
            rejected_reason="",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(doc)
        db.flush()

        for ln in calc_lines:
            db.add(
                BusinessDocumentLine(
                    doc_id=doc.id,
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

        draft = _create_draft_for_doc(db, doc=doc, lines=calc_lines, actor_user_id=actor_user_id)
        doc.draft_id = draft.id
        _attach_to_owner(db, attachment_ids, owner_type="business_document", owner_id=str(doc.id))
        db.flush()

        return CreateDocResult(doc_id=str(doc.id), draft_id=str(draft.id))


def resubmit_document(
    db: Session,
    *,
    doc_id: str,
    patch: dict,
    actor_user_id: str | None,
) -> CreateDocResult:
    """
    退回后重新提交：保留历史版本（revision_no + 新 draft version）
    """
    with db.begin():
        doc = db.query(BusinessDocument).filter(BusinessDocument.id == doc_id).with_for_update().one_or_none()
        if not doc:
            raise ValueError("单据不存在")
        if doc.status != "REJECTED":
            raise ValueError("仅 REJECTED 单据允许重新提交")
        _require_period_open(db, str(doc.period_id))

        # 更新字段
        if patch.get("doc_date") is not None:
            doc.doc_date = patch["doc_date"]
        if patch.get("project") is not None:
            doc.project = patch["project"] or ""
        if patch.get("term_days") is not None:
            doc.term_days = patch["term_days"]
        if patch.get("description") is not None:
            doc.description = patch["description"] or ""

        new_lines = patch.get("lines")
        if new_lines is None:
            # 若未传 lines：沿用原 lines
            old = (
                db.query(BusinessDocumentLine)
                .filter(BusinessDocumentLine.doc_id == doc.id)
                .order_by(BusinessDocumentLine.line_no.asc())
                .all()
            )
            new_lines = [
                {
                    "description": x.description,
                    "account_id": str(x.account_id),
                    "quantity": x.quantity,
                    "unit_price": x.unit_price,
                    "tax_rate": x.tax_rate,
                    "memo": x.memo,
                }
                for x in old
            ]

        default_tax = Decimal("0.07") if doc.doc_type in ("PURCHASE_ORDER", "EXPENSE_CLAIM") else Decimal("0.13")
        calc_lines, total_amount, tax_amount = _calc_lines(new_lines, default_tax_rate=default_tax)
        doc.total_amount = total_amount
        doc.tax_amount = tax_amount

        # 账期/信用额度（最小实现）
        if doc.doc_type in ("PURCHASE_ORDER", "SALES_ORDER") and doc.party_id:
            p = db.query(Party).filter(Party.id == doc.party_id).one_or_none()
            if not p:
                raise ValueError("往来单位不存在")
            if doc.doc_type == "PURCHASE_ORDER":
                max_term = p.payment_term_days or (60 if (p.contact_json or {}).get("annual_purchase_over_10m") else 30)
                if doc.term_days is None:
                    doc.term_days = max_term
                if doc.term_days and doc.term_days > max_term:
                    raise ValueError("账期超限")
            if doc.doc_type == "SALES_ORDER":
                grade = (p.contact_json or {}).get("grade")
                max_term = p.payment_term_days or (60 if grade == "A" else 30)
                if doc.term_days is None:
                    doc.term_days = max_term
                if doc.term_days and doc.term_days > max_term:
                    raise ValueError("账期超限")
                if p.credit_limit is not None and _d(total_amount) > _d(p.credit_limit):
                    raise ValueError("客户信用额度不足")

        # 清理旧 lines，重建（最小实现：保留历史靠 draft revisions + version）
        db.query(BusinessDocumentLine).filter(BusinessDocumentLine.doc_id == doc.id).delete()
        for ln in calc_lines:
            db.add(
                BusinessDocumentLine(
                    doc_id=doc.id,
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

        doc.revision_no += 1
        doc.status = "SUBMITTED"
        doc.rejected_reason = ""
        doc.rejected_by = None
        doc.updated_at = datetime.utcnow()
        db.flush()

        draft = _create_draft_for_doc(db, doc=doc, lines=calc_lines, actor_user_id=actor_user_id)
        draft.status = "DRAFT"
        append_revision(db, draft, action="RESUBMIT", reason="", actor_id=actor_user_id)
        doc.draft_id = draft.id

        attachment_ids = patch.get("attachment_ids")
        if attachment_ids is not None:
            _attach_to_owner(db, attachment_ids, owner_type="business_document", owner_id=str(doc.id))

        db.flush()
        return CreateDocResult(doc_id=str(doc.id), draft_id=str(draft.id))


def list_parties(db: Session, *, type_: str) -> list[Party]:
    return db.query(Party).filter(Party.type == type_).order_by(Party.created_at.desc()).limit(200).all()


def create_party(db: Session, *, type_: str, payload: dict) -> Party:
    with db.begin():
        existed = db.query(Party).filter(Party.type == type_, Party.name == payload["name"]).one_or_none()
        if existed:
            return existed
        p = Party(
            type=type_,
            name=payload["name"],
            tax_no=payload.get("tax_no") or "",
            credit_limit=payload.get("credit_limit"),
            payment_term_days=payload.get("payment_term_days"),
            contact_json=payload.get("contact_json"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(p)
        db.flush()
        return p


def get_document(db: Session, doc_id: str) -> BusinessDocument | None:
    return db.query(BusinessDocument).filter(BusinessDocument.id == doc_id).one_or_none()


def list_documents(db: Session, *, doc_type: str, status: str | None = None) -> list[BusinessDocument]:
    q = db.query(BusinessDocument).filter(BusinessDocument.doc_type == doc_type)
    if status:
        q = q.filter(BusinessDocument.status == status)
    return q.order_by(BusinessDocument.created_at.desc()).limit(200).all()


