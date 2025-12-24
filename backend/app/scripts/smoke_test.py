from __future__ import annotations

"""
后端冒烟测试（不依赖前端）：
- alembic 迁移完成后，运行本脚本验证关键链路
- 依赖环境变量 DATABASE_URL 指向一个可安全销毁的测试库

覆盖：
1) AR 发票 -> 生成草稿 -> 审批 -> 过账
2) 收款 -> 核销发票 -> 生成草稿 -> 审批 -> 过账 -> 发票应为 PAID
3) 账龄查询返回该发票
4) 多币种：USD/CNY 价格 + USD 账户，CNY 交易过账到 USD 账户，检查 Split.amount 换算
"""

from datetime import date, datetime
from decimal import Decimal

from app.application.ar_ap.service import aging_report, create_invoice, create_payment
from app.application.gl.draft_workflow import approve_draft
from app.application.gl.posting import post_draft
from app.infra.db.models import (
    Account,
    AccountingPeriod,
    Book,
    Commodity,
    Invoice,
    Price,
    Split,
    Transaction,
    TransactionDraft,
    TransactionDraftLine,
    User,
)
from app.infra.db.session import SessionLocal
from app.scripts import init_db


def _one_time_bootstrap() -> tuple[str, str, str, str, str]:
    init_db.main()
    with SessionLocal() as db:
        book = db.query(Book).first()
        assert book
        period = db.query(AccountingPeriod).filter(AccountingPeriod.book_id == book.id).first()
        assert period
        cash = db.query(Account).filter(Account.book_id == book.id, Account.code == "1001").one()
        user = db.query(User).filter(User.username == "accountant").one()
        cny = db.query(Commodity).filter(Commodity.type == "CURRENCY", Commodity.code == "CNY").one()
        return str(book.id), str(period.id), str(cash.id), str(user.id), str(cny.id)


def main() -> None:
    now = datetime.utcnow()
    today = now.date()
    book_id, period_id, cash_id, user_id, cny_id = _one_time_bootstrap()

    # 1) AR 发票 -> 草稿 -> 审批 -> 过账
    with SessionLocal() as db:
        revenue = db.query(Account).filter(Account.book_id == book_id, Account.code == "4001").one()
    with SessionLocal() as db:
        r = create_invoice(
            db,
            book_id=book_id,
            period_id=period_id,
            invoice_type="AR",
            doc_no="AR-TEST-1",
            doc_date=now,
            due_date=today,
            party_id=None,
            currency_type="CURRENCY",
            currency_code="CNY",
            notes="smoke",
            lines=[
                {
                    "description": "收入A",
                    "account_id": str(revenue.id),
                    "quantity": Decimal("1"),
                    "unit_price": Decimal("100"),
                    "tax_rate": Decimal("0.07"),
                    "memo": "",
                }
            ],
            actor_user_id=user_id,
            create_draft=True,
        )
        assert r.draft_id
        inv_id = r.invoice_id
        inv_draft_id = r.draft_id

    with SessionLocal() as db:
        approve_draft(db, inv_draft_id, actor_id=user_id)
    with SessionLocal() as db:
        post_draft(db, inv_draft_id, actor_user_id=user_id)

    # 2) 收款核销 -> 草稿 -> 审批 -> 过账 -> 发票 PAID
    with SessionLocal() as db:
        p = create_payment(
            db,
            book_id=book_id,
            period_id=period_id,
            payment_type="RECEIPT",
            pay_date=now,
            party_id=None,
            currency_type="CURRENCY",
            currency_code="CNY",
            amount=Decimal("107"),
            cash_account_id=cash_id,
            method="BANK",
            reference_no="RCPT-1",
            notes="smoke",
            applications=[{"invoice_id": inv_id, "amount": Decimal("107")}],
            actor_user_id=user_id,
            create_draft=True,
        )
        assert p.draft_id
        pay_draft_id = p.draft_id

    with SessionLocal() as db:
        approve_draft(db, pay_draft_id, actor_id=user_id)
    with SessionLocal() as db:
        post_draft(db, pay_draft_id, actor_user_id=user_id)

    with SessionLocal() as db:
        inv = db.query(Invoice).filter(Invoice.id == inv_id).one()
        assert inv.status == "PAID", inv.status

    # 3) 账龄
    with SessionLocal() as db:
        items = aging_report(db, book_id=book_id, as_of=today, invoice_type="AR")
        assert any(x["invoice_id"] == inv_id for x in items)

    # 4) 多币种换算：USD/CNY + USD 银行账户
    fx_now = datetime.utcnow()
    fx_day = fx_now.date()
    with SessionLocal() as db:
        with db.begin():
            usd = db.query(Commodity).filter(Commodity.type == "CURRENCY", Commodity.code == "USD").one_or_none()
            if not usd:
                usd = Commodity(type="CURRENCY", code="USD", name="美元", precision=2)
                db.add(usd)
                db.flush()

            pr = (
                db.query(Price)
                .filter(
                    Price.book_id == book_id,
                    Price.commodity_id == str(usd.id),
                    Price.currency_id == cny_id,
                    Price.price_date == fx_day,
                )
                .one_or_none()
            )
            if not pr:
                pr = Price(
                    book_id=book_id,
                    commodity_id=str(usd.id),
                    currency_id=cny_id,
                    price_date=fx_day,
                    source="APP",
                    type="LAST",
                    value=Decimal("7.2"),  # 1 USD = 7.2 CNY
                )
                db.add(pr)

            usd_bank = db.query(Account).filter(Account.book_id == book_id, Account.code == "1002").one_or_none()
            if not usd_bank:
                usd_bank = Account(
                    book_id=book_id,
                    parent_id=None,
                    code="1002",
                    name="美元银行",
                    description="",
                    type="ASSET",
                    commodity_id=str(usd.id),
                    allow_post=True,
                    is_active=True,
                    is_hidden=False,
                    is_placeholder=False,
                )
                db.add(usd_bank)
                db.flush()

            d = TransactionDraft(
                book_id=book_id,
                period_id=period_id,
                currency_id=cny_id,
                txn_date=fx_now,
                source_type="MANUAL",
                source_id="fx-test-1",
                version=1,
                description="FX smoke",
                status="APPROVED",
                created_by=user_id,
                approved_by=user_id,
            )
            db.add(d)
            db.flush()
            db.add(
                TransactionDraftLine(
                    draft_id=str(d.id),
                    line_no=1,
                    account_id=str(usd_bank.id),
                    debit=Decimal("72"),
                    credit=Decimal("0"),
                    memo="借：USD银行",
                    aux_json={},
                )
            )
            db.add(
                TransactionDraftLine(
                    draft_id=str(d.id),
                    line_no=2,
                    account_id=cash_id,
                    debit=Decimal("0"),
                    credit=Decimal("72"),
                    memo="贷：现金",
                    aux_json={},
                )
            )
            fx_draft_id = str(d.id)

    # 确认 Price 已落库（否则后续换算必然失败）
    with SessionLocal() as db:
        usd = db.query(Commodity).filter(Commodity.type == "CURRENCY", Commodity.code == "USD").one()
        pr = (
            db.query(Price)
            .filter(Price.book_id == book_id, Price.commodity_id == str(usd.id), Price.currency_id == cny_id, Price.price_date <= fx_day)
            .order_by(Price.price_date.desc())
            .first()
        )
        assert pr is not None, "USD/CNY 价格未写入"

    with SessionLocal() as db:
        post_draft(db, fx_draft_id, actor_user_id=user_id)

    with SessionLocal() as db:
        txn = db.query(Transaction).filter(Transaction.source_type == "MANUAL", Transaction.source_id == "fx-test-1").one()
        sp = db.query(Split).filter(Split.txn_id == txn.id, Split.line_no == 1).one()
        assert float(sp.value) == 72.0
        # 72 CNY / 7.2 = 10 USD（precision=2 => 10.00）
        assert str(sp.amount).startswith("10"), (sp.amount, sp.value)

    print("SMOKE_OK")


if __name__ == "__main__":
    main()


