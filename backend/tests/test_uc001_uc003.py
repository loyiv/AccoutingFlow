from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.application.business.service import create_expense_claim, create_purchase_order, create_sales_order, resubmit_document
from app.application.gl.draft_workflow import approve_draft, reject_draft
from app.application.gl.posting import post_draft, precheck_draft
from app.infra.db.models import Account, BusinessDocument, Party, TransactionDraft
from app.infra.db.session import SessionLocal
from app.scripts.init_db import main as seed_main


def test_uc001_purchase_order_generates_draft_and_can_post(migrated_db):
    seed_main()
    with SessionLocal() as db:
        book_id = str(db.query(Account).filter(Account.code == "1000").one().book_id)
        period_id = str(db.query(TransactionDraft).filter(TransactionDraft.source_id == "seed-1").one().period_id)
        vendor = db.query(Party).filter(Party.type == "VENDOR").first()
        exp = db.query(Account).filter(Account.book_id == book_id, Account.code == "5001").one()

        r = create_purchase_order(
            db,
            book_id=book_id,
            period_id=period_id,
            doc_no="PO-001",
            doc_date=datetime.utcnow(),
            vendor_id=str(vendor.id),
            project="P1",
            term_days=None,
            description="采购测试",
            lines=[{"description": "办公用品", "account_id": str(exp.id), "quantity": Decimal("2"), "unit_price": Decimal("100"), "tax_rate": Decimal("0.07")}],
            attachment_ids=[],
            actor_user_id=None,
        )
        d = db.query(TransactionDraft).filter(TransactionDraft.id == r.draft_id).one()
        pre = precheck_draft(db, str(d.id))
        assert pre.ok is True

        approve_draft(db, str(d.id), actor_id=None)
        post = post_draft(db, str(d.id), actor_user_id=None)
        assert post.voucher_num


def test_uc002_sales_order_credit_check_and_post(migrated_db):
    seed_main()
    with SessionLocal() as db:
        book_id = str(db.query(Account).filter(Account.code == "1000").one().book_id)
        period_id = str(db.query(TransactionDraft).filter(TransactionDraft.source_id == "seed-1").one().period_id)
        cust = db.query(Party).filter(Party.type == "CUSTOMER").first()
        revenue = db.query(Account).filter(Account.book_id == book_id, Account.code == "4001").one()

        r = create_sales_order(
            db,
            book_id=book_id,
            period_id=period_id,
            doc_no="SO-001",
            doc_date=datetime.utcnow(),
            customer_id=str(cust.id),
            project="P2",
            term_days=None,
            description="销售测试",
            lines=[{"description": "软件服务", "account_id": str(revenue.id), "quantity": Decimal("1"), "unit_price": Decimal("1000"), "tax_rate": Decimal("0.13")}],
            attachment_ids=[],
            actor_user_id=None,
        )
        d = db.query(TransactionDraft).filter(TransactionDraft.id == r.draft_id).one()
        approve_draft(db, str(d.id), actor_id=None)
        post = post_draft(db, str(d.id), actor_user_id=None)
        assert post.voucher_num


def test_uc003_expense_claim_reject_and_resubmit_creates_new_version(migrated_db):
    seed_main()
    with SessionLocal() as db:
        book_id = str(db.query(Account).filter(Account.code == "1000").one().book_id)
        period_id = str(db.query(TransactionDraft).filter(TransactionDraft.source_id == "seed-1").one().period_id)
        exp = db.query(Account).filter(Account.book_id == book_id, Account.code == "5001").one()

        r1 = create_expense_claim(
            db,
            book_id=book_id,
            period_id=period_id,
            doc_no="EC-001",
            doc_date=datetime.utcnow(),
            employee_id="E001",
            project="D1",
            description="报销测试",
            lines=[{"description": "差旅", "account_id": str(exp.id), "quantity": Decimal("1"), "unit_price": Decimal("100"), "tax_rate": Decimal("0.07")}],
            attachment_ids=[],
            actor_user_id=None,
        )
        d1 = db.query(TransactionDraft).filter(TransactionDraft.id == r1.draft_id).one()
        reject_draft(db, str(d1.id), actor_id=None, reason="票据不合规")

        doc = db.query(BusinessDocument).filter(BusinessDocument.id == r1.doc_id).one()
        assert doc.status == "REJECTED"
        assert doc.rejected_reason

        r2 = resubmit_document(
            db,
            doc_id=str(doc.id),
            patch={"description": "补充说明", "lines": [{"description": "差旅(修正)", "account_id": str(exp.id), "quantity": Decimal("1"), "unit_price": Decimal("120"), "tax_rate": Decimal("0.07")}]},
            actor_user_id=None,
        )
        assert r2.draft_id != r1.draft_id
        doc2 = db.query(BusinessDocument).filter(BusinessDocument.id == r1.doc_id).one()
        assert doc2.status == "SUBMITTED"
        assert doc2.revision_no >= 2


