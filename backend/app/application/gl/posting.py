from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import (
    Account,
    AccountingPeriod,
    AuditLog,
    AccountBalance,
    Book,
    BusinessDocument,
    Commodity,
    Invoice,
    Lot,
    Payment,
    PaymentApplication,
    Price,
    ReportSnapshot,
    Split,
    Transaction,
    TransactionDraft,
    TransactionDraftLine,
    VoucherSequence,
)
from app.application.gl.draft_workflow import append_revision


@dataclass(frozen=True)
class PrecheckResult:
    ok: bool
    checks: list[dict]


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def precheck_draft(db: Session, draft_id: str) -> PrecheckResult:
    draft = db.query(TransactionDraft).filter(TransactionDraft.id == draft_id).one_or_none()
    if not draft:
        return PrecheckResult(ok=False, checks=[{"code": "DRAFT_EXISTS", "passed": False, "message": "草稿不存在", "details": {}}])

    lines = (
        db.query(TransactionDraftLine)
        .filter(TransactionDraftLine.draft_id == draft.id)
        .order_by(TransactionDraftLine.line_no.asc())
        .all()
    )

    checks: list[dict] = []

    # 0) 结构校验：至少两行
    checks.append(
        {
            "code": "MIN_SPLITS",
            "passed": len(lines) >= 2,
            "message": "至少包含 2 条分录行" if len(lines) >= 2 else "分录行不足 2 条",
            "details": {"line_count": len(lines)},
        }
    )

    # 1) 借贷平衡（sum(value)=0）
    total = Decimal("0")
    bad_lines: list[dict] = []
    for ln in lines:
        debit = _decimal(ln.debit)
        credit = _decimal(ln.credit)
        if debit != 0 and credit != 0:
            bad_lines.append({"line_no": ln.line_no, "reason": "借贷不可同时填写", "debit": str(debit), "credit": str(credit)})
        if debit == 0 and credit == 0:
            bad_lines.append({"line_no": ln.line_no, "reason": "借贷不可同时为 0", "debit": str(debit), "credit": str(credit)})
        total += debit - credit
    checks.append(
        {
            "code": "BALANCE_VALUE_ZERO",
            "passed": total == 0,
            "message": "借贷平衡（sum(value)=0）" if total == 0 else "借贷不平衡（sum(value)≠0）",
            "details": {"sum_value": str(total), "line_issues": bad_lines},
        }
    )

    # 2) 期间开放
    period = db.query(AccountingPeriod).filter(AccountingPeriod.id == draft.period_id).one_or_none()
    checks.append(
        {
            "code": "PERIOD_OPEN",
            "passed": bool(period and period.status == "OPEN"),
            "message": "会计期间已开放" if period and period.status == "OPEN" else "会计期间未开放/不存在",
            "details": {"period_id": str(draft.period_id), "status": period.status if period else None},
        }
    )

    # 3) 科目允许记账/启用
    account_ids = {l.account_id for l in lines}
    acc_rows = (
        db.query(Account)
        .filter(Account.id.in_(list(account_ids)))
        .all()
    )
    by_id = {str(a.id): a for a in acc_rows}
    bad_accounts: list[dict] = []
    for aid in account_ids:
        a = by_id.get(str(aid))
        if not a:
            bad_accounts.append({"account_id": str(aid), "reason": "科目不存在"})
            continue
        if str(a.book_id) != str(draft.book_id):
            bad_accounts.append({"account_id": str(aid), "reason": "科目不属于当前账簿"})
        if not a.is_active:
            bad_accounts.append({"account_id": str(aid), "reason": "科目已停用"})
        if not a.allow_post:
            bad_accounts.append({"account_id": str(aid), "reason": "科目不允许记账"})
    checks.append(
        {
            "code": "ACCOUNT_ALLOW_POST",
            "passed": len(bad_accounts) == 0,
            "message": "科目可用且允许记账" if len(bad_accounts) == 0 else "存在不可记账/无效科目",
            "details": {"bad_accounts": bad_accounts},
        }
    )

    # 4) 幂等（source_type+source_id+version 不可重复过账）
    idem = f"{draft.source_type}:{draft.source_id}:{draft.version}"
    existed = (
        db.query(Transaction)
        .filter(Transaction.book_id == draft.book_id)
        .filter(Transaction.source_type == draft.source_type)
        .filter(Transaction.source_id == draft.source_id)
        .filter(Transaction.version == draft.version)
        .one_or_none()
    )
    checks.append(
        {
            "code": "IDEMPOTENCY",
            "passed": existed is None,
            "message": "来源单据未重复过账" if existed is None else "检测到重复过账（幂等冲突）",
            "details": {"idempotency_key": idem, "existing_txn_id": str(existed.id) if existed else None},
        }
    )

    ok = all(c["passed"] for c in checks)
    return PrecheckResult(ok=ok, checks=checks)


def _next_voucher_num(db: Session, book_id: str, year: int, month: int) -> str:
    # 为兼容 MySQL：使用行级锁 + insert/update（不依赖 ON CONFLICT/RETURNING）
    row = (
        db.query(VoucherSequence)
        .filter(VoucherSequence.book_id == book_id, VoucherSequence.year == year, VoucherSequence.month == month)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        row = VoucherSequence(book_id=book_id, year=year, month=month, next_num=1)
        db.add(row)
        db.flush()
        seq = row.next_num
    else:
        row.next_num += 1
        db.flush()
        seq = row.next_num

    return f"{year}{month:02d}-{int(seq):06d}"


def _audit_hash(prev_hash: str | None, payload: dict) -> str:
    prev = prev_hash or ""
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PostResult:
    txn_id: str
    voucher_num: str


def _q(v: Decimal, places: str) -> Decimal:
    # ROUND_HALF_UP for accounting
    return v.quantize(Decimal(places))


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


def _get_latest_price_value(
    db: Session,
    *,
    book_id: str,
    commodity_id: str,
    currency_id: str,
    as_of: date,
) -> Decimal | None:
    row = (
        db.query(Price)
        .filter(
            Price.book_id == book_id,
            Price.commodity_id == commodity_id,
            Price.currency_id == currency_id,
            Price.price_date <= as_of,
        )
        .order_by(Price.price_date.desc())
        .first()
    )
    return _decimal(row.value) if row else None


def _convert_value_to_amount(
    db: Session,
    *,
    book_id: str,
    as_of: date,
    value_in_txn_currency: Decimal,
    account_commodity: Commodity,
    txn_currency: Commodity,
) -> Decimal:
    # GnuCash-like:
    # - Split.value: transaction currency
    # - Split.amount: account commodity
    if str(account_commodity.id) == str(txn_currency.id):
        return value_in_txn_currency

    # price: 1 account_commodity = price.value txn_currency
    direct = _get_latest_price_value(
        db,
        book_id=book_id,
        commodity_id=str(account_commodity.id),
        currency_id=str(txn_currency.id),
        as_of=as_of,
    )
    if direct and direct != 0:
        amt = value_in_txn_currency / direct
    else:
        # reverse: 1 txn_currency = price.value account_commodity
        rev = _get_latest_price_value(
            db,
            book_id=book_id,
            commodity_id=str(txn_currency.id),
            currency_id=str(account_commodity.id),
            as_of=as_of,
        )
        if not rev or rev == 0:
            raise ValueError("缺少汇率/价格（Price），无法进行多币种换算")
        amt = value_in_txn_currency * rev

    # round by commodity precision
    prec = int(account_commodity.precision or 2)
    places = "0." + ("0" * (prec - 1)) + "1" if prec > 0 else "1"
    return amt.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def post_draft(db: Session, draft_id: str, actor_user_id: str | None) -> PostResult:
    """
    UC004 过账：
    - 事务化（ACID）
    - 幂等（source_type+source_id+version 唯一）
    - 并发安全凭证号
    - 写 transactions/splits + 更新余额 + 审计日志 + 报表快照置 stale
    """
    with db.begin():
        # 锁草稿，防止并发重复过账
        draft = (
            db.query(TransactionDraft)
            .filter(TransactionDraft.id == draft_id)
            .with_for_update()
            .one_or_none()
        )
        if not draft:
            raise ValueError("草稿不存在")

        # 已过账：直接幂等返回
        if draft.posted_txn_id:
            txn = db.query(Transaction).filter(Transaction.id == draft.posted_txn_id).one()
            return PostResult(txn_id=str(txn.id), voucher_num=txn.num)

        if draft.status != "APPROVED":
            raise ValueError("草稿状态不是 APPROVED，禁止过账")

        # 幂等：事务层再查一次（并锁定冲突行由唯一约束兜底）
        existed = (
            db.query(Transaction)
            .filter(Transaction.book_id == draft.book_id)
            .filter(Transaction.source_type == draft.source_type)
            .filter(Transaction.source_id == draft.source_id)
            .filter(Transaction.version == draft.version)
            .one_or_none()
        )
        if existed:
            draft.posted_txn_id = existed.id
            draft.status = "POSTED"
            db.flush()
            return PostResult(txn_id=str(existed.id), voucher_num=existed.num)

        pre = precheck_draft(db, str(draft.id))
        if not pre.ok:
            raise ValueError("预校验未通过")

        period = db.query(AccountingPeriod).filter(AccountingPeriod.id == draft.period_id).one()
        voucher_num = _next_voucher_num(db, str(draft.book_id), period.year, period.month)

        lines = (
            db.query(TransactionDraftLine)
            .filter(TransactionDraftLine.draft_id == draft.id)
            .order_by(TransactionDraftLine.line_no.asc())
            .all()
        )

        # 交易币种：draft.currency_id -> book.base_currency_id
        book = db.query(Book).filter(Book.id == draft.book_id).one()
        txn_currency_id = str(draft.currency_id) if getattr(draft, "currency_id", None) else str(book.base_currency_id)
        txn_currency = db.query(Commodity).filter(Commodity.id == txn_currency_id).one()
        txn_date = draft.txn_date if getattr(draft, "txn_date", None) else datetime.utcnow()

        idempotency_key = f"{draft.source_type}:{draft.source_id}:{draft.version}"
        txn = Transaction(
            book_id=draft.book_id,
            period_id=draft.period_id,
            txn_date=txn_date,
            currency_id=txn_currency_id,
            num=voucher_num,
            description=draft.description,
            source_type=draft.source_type,
            source_id=draft.source_id,
            version=draft.version,
            idempotency_key=idempotency_key,
            posted_by=actor_user_id if actor_user_id else None,
            posted_at=datetime.utcnow(),
            status="POSTED",
        )
        db.add(txn)
        try:
            db.flush()
        except IntegrityError as e:
            # 幂等冲突兜底：回查返回
            existed = (
                db.query(Transaction)
                .filter(Transaction.book_id == draft.book_id)
                .filter(Transaction.source_type == draft.source_type)
                .filter(Transaction.source_id == draft.source_id)
                .filter(Transaction.version == draft.version)
                .one()
            )
            draft.posted_txn_id = existed.id
            draft.status = "POSTED"
            db.flush()
            return PostResult(txn_id=str(existed.id), voucher_num=existed.num)

        # 写 splits + 更新余额（余额用 account commodity 的 amount 口径）
        deltas: dict[str, Decimal] = {}
        for ln in lines:
            v = _decimal(ln.debit) - _decimal(ln.credit)  # value in txn currency
            acc = db.query(Account).filter(Account.id == ln.account_id).one()
            acc_commodity = db.query(Commodity).filter(Commodity.id == acc.commodity_id).one()
            amt = _convert_value_to_amount(
                db,
                book_id=str(draft.book_id),
                as_of=txn_date.date(),
                value_in_txn_currency=v,
                account_commodity=acc_commodity,
                txn_currency=txn_currency,
            )
            aux = ln.aux_json or {}
            sp = Split(
                txn_id=txn.id,
                line_no=ln.line_no,
                account_id=ln.account_id,
                amount=amt,
                value=v,
                memo=ln.memo,
                action=str(aux.get("action") or ""),
                reconcile_state="n",
                reconcile_date=None,
                lot_id=str(aux.get("lot_id")) if aux.get("lot_id") else None,
            )
            db.add(sp)
            deltas[str(ln.account_id)] = deltas.get(str(ln.account_id), Decimal("0")) + amt
        db.flush()

        # balance cache：对本期间做增量更新（MySQL 兼容：行锁 + insert/update）
        for account_id, delta in deltas.items():
            bal = (
                db.query(AccountBalance)
                .filter(
                    AccountBalance.book_id == draft.book_id,
                    AccountBalance.period_id == draft.period_id,
                    AccountBalance.account_id == account_id,
                )
                .with_for_update()
                .one_or_none()
            )
            if bal is None:
                bal = AccountBalance(book_id=draft.book_id, period_id=draft.period_id, account_id=account_id, balance_value=delta)
                db.add(bal)
            else:
                bal.balance_value = _decimal(bal.balance_value) + delta
            db.flush()

        # 草稿锁定
        draft.status = "POSTED"
        draft.posted_txn_id = txn.id
        # 若来源是业务单据：同步为 POSTED
        if draft.source_type in ("PURCHASE_ORDER", "SALES_ORDER", "EXPENSE_CLAIM"):
            doc = db.query(BusinessDocument).filter(BusinessDocument.id == draft.source_id).one_or_none()
            if doc:
                doc.status = "POSTED"
                doc.updated_at = datetime.utcnow()
        # 若来源是发票：写回 posted_txn_id + 状态
        if draft.source_type in ("INVOICE_AR", "INVOICE_AP"):
            inv = db.query(Invoice).filter(Invoice.id == draft.source_id).one_or_none()
            if inv:
                inv.posted_txn_id = txn.id
                inv.status = "POSTED"
                inv.updated_at = datetime.utcnow()
                # 若没有 lot，则补创建（容错）
                if not inv.lot_id:
                    # 控制科目：AR=1122 AP=2001（同 init_db）
                    code = "1122" if inv.invoice_type == "AR" else "2001"
                    ctrl = db.query(Account).filter(Account.book_id == inv.book_id, Account.code == code).one()
                    lot = Lot(
                        book_id=str(inv.book_id),
                        account_id=str(ctrl.id),
                        title=f"{inv.invoice_type} 发票 {inv.doc_no}".strip(),
                        notes="",
                        is_closed=False,
                        opened_at=datetime.utcnow(),
                        closed_at=None,
                    )
                    db.add(lot)
                    db.flush()
                    inv.lot_id = lot.id
                    db.flush()
        # 若来源是收付款：写回 txn_id + 状态，并尝试更新发票是否已结清/lot 是否关闭
        if draft.source_type in ("PAYMENT_RECEIPT", "PAYMENT_DISBURSEMENT"):
            pay = db.query(Payment).filter(Payment.id == draft.source_id).one_or_none()
            if pay:
                pay.txn_id = txn.id
                pay.status = "POSTED"
                pay.updated_at = datetime.utcnow()
                # 结清判断：同币种限制下，按 payment_applications 汇总
                apps = db.query(PaymentApplication).filter(PaymentApplication.payment_id == pay.id).all()
                inv_ids = list({str(x.invoice_id) for x in apps})
                if inv_ids:
                    sums = (
                        db.query(PaymentApplication.invoice_id, sa.func.sum(PaymentApplication.amount))
                        .filter(PaymentApplication.invoice_id.in_(inv_ids))
                        .group_by(PaymentApplication.invoice_id)
                        .all()
                    )
                    paid_by_inv = {str(iid): _decimal(s or 0) for iid, s in sums}
                    invs = db.query(Invoice).filter(Invoice.id.in_(inv_ids)).all()
                    for inv in invs:
                        paid = paid_by_inv.get(str(inv.id), Decimal("0"))
                        if paid >= _decimal(inv.total_gross):
                            inv.status = "PAID"
                            inv.updated_at = datetime.utcnow()
                            if inv.lot_id:
                                lot = db.query(Lot).filter(Lot.id == inv.lot_id).one_or_none()
                                if lot and not lot.is_closed:
                                    lot.is_closed = True
                                    lot.closed_at = datetime.utcnow()
                                    db.flush()
        append_revision(db, draft, action="POST", reason="", actor_id=actor_user_id)
        db.flush()

        # 审计日志（append-only）
        last = db.query(AuditLog).order_by(AuditLog.at.desc()).limit(1).one_or_none()
        prev_hash = last.hash_chain if last else None
        payload = {
            "action": "UC004_POST_DRAFT",
            "draft_id": str(draft.id),
            "txn_id": str(txn.id),
            "voucher_num": voucher_num,
            "source": {"type": draft.source_type, "id": draft.source_id, "version": draft.version},
            "at": datetime.utcnow().isoformat(),
        }
        h = _audit_hash(prev_hash, payload)
        log = AuditLog(
            actor_id=actor_user_id if actor_user_id else None,
            action="UC004_POST_DRAFT",
            entity_type="transaction",
            entity_id=str(txn.id),
            at=datetime.utcnow(),
            payload_json=payload,
            hash_chain_prev=prev_hash,
            hash_chain=h,
        )
        db.add(log)

        # 报表缓存置 stale（简单策略：该账簿所有快照失效）
        db.query(ReportSnapshot).filter(ReportSnapshot.book_id == draft.book_id).update({ReportSnapshot.is_stale: True})

    return PostResult(txn_id=str(txn.id), voucher_num=voucher_num)


