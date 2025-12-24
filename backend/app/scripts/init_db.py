from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.infra.db.models import (
    Account,
    AccountingPeriod,
    BusinessDocument,
    BusinessDocumentLine,
    Book,
    Commodity,
    ObjectKV,
    Price,
    Party,
    ReportBasis,
    ReportItem,
    ReportMapping,
    ScheduledTransaction,
    TransactionDraft,
    TransactionDraftLine,
    User,
)
from app.infra.db.session import SessionLocal


def _now() -> datetime:
    return datetime.utcnow()


def _get_or_create_user(db: Session, username: str, password: str, role: str) -> User:
    u = db.query(User).filter(User.username == username).one_or_none()
    if u:
        return u
    u = User(username=username, password_hash=hash_password(password), role=role, created_at=_now())
    db.add(u)
    db.flush()
    return u


def _get_or_create_commodity(db: Session, type_: str, code: str, name: str, precision: int) -> Commodity:
    c = db.query(Commodity).filter(Commodity.type == type_, Commodity.code == code).one_or_none()
    if c:
        return c
    c = Commodity(type=type_, code=code, name=name, precision=precision)
    db.add(c)
    db.flush()
    return c


def _get_or_create_book(db: Session, name: str, base_currency_id: str) -> Book:
    b = db.query(Book).filter(Book.name == name).one_or_none()
    if b:
        return b
    b = Book(name=name, base_currency_id=base_currency_id, created_at=_now())
    db.add(b)
    db.flush()
    return b


def _get_or_create_account(
    db: Session,
    *,
    book_id: str,
    parent_id: str | None,
    code: str,
    name: str,
    type_: str,
    commodity_id: str,
    allow_post: bool,
    is_active: bool = True,
) -> Account:
    a = db.query(Account).filter(Account.book_id == book_id, Account.code == code).one_or_none()
    if a:
        return a
    a = Account(
        book_id=book_id,
        parent_id=parent_id,
        code=code,
        name=name,
        type=type_,
        commodity_id=commodity_id,
        allow_post=allow_post,
        is_active=is_active,
    )
    db.add(a)
    db.flush()
    return a


def _get_or_create_period(db: Session, book_id: str, year: int, month: int) -> AccountingPeriod:
    p = db.query(AccountingPeriod).filter(AccountingPeriod.book_id == book_id, AccountingPeriod.year == year, AccountingPeriod.month == month).one_or_none()
    if p:
        return p
    p = AccountingPeriod(book_id=book_id, year=year, month=month, status="OPEN", opened_at=_now(), closed_at=None)
    db.add(p)
    db.flush()
    return p


def _get_or_create_basis(db: Session, code: str, name: str) -> ReportBasis:
    b = db.query(ReportBasis).filter(ReportBasis.code == code).one_or_none()
    if b:
        return b
    b = ReportBasis(code=code, name=name)
    db.add(b)
    db.flush()
    return b


def _get_or_create_item(db: Session, statement_type: str, code: str, name: str, display_order: int, calc_mode: str) -> ReportItem:
    it = db.query(ReportItem).filter(ReportItem.statement_type == statement_type, ReportItem.code == code).one_or_none()
    if it:
        it.name = name
        it.display_order = display_order
        it.calc_mode = calc_mode
        db.flush()
        return it
    it = ReportItem(statement_type=statement_type, code=code, name=name, display_order=display_order, calc_mode=calc_mode)
    db.add(it)
    db.flush()
    return it


def _get_or_create_mapping(db: Session, *, basis_id: str, item: ReportItem, account_id: str, include_children: bool = True) -> ReportMapping:
    m = (
        db.query(ReportMapping)
        .filter(
            ReportMapping.basis_id == basis_id,
            ReportMapping.item_id == item.id,
            ReportMapping.account_id == account_id,
        )
        .one_or_none()
    )
    if m:
        return m
    m = ReportMapping(
        basis_id=basis_id,
        statement_type=item.statement_type,
        item_id=item.id,
        account_id=account_id,
        include_children=include_children,
        direction="NET",
    )
    db.add(m)
    db.flush()
    return m


def _get_or_create_object_kv(db: Session, *, owner_type: str, owner_id: str, key: str, value_json: dict) -> ObjectKV:
    row = (
        db.query(ObjectKV)
        .filter(ObjectKV.owner_type == owner_type, ObjectKV.owner_id == owner_id, ObjectKV.key == key)
        .one_or_none()
    )
    if row:
        row.value_json = value_json
        db.flush()
        return row
    row = ObjectKV(owner_type=owner_type, owner_id=owner_id, key=key, value_json=value_json, updated_at=_now())
    db.add(row)
    db.flush()
    return row


def _get_or_create_price(
    db: Session,
    *,
    book_id: str,
    commodity_id: str,
    currency_id: str,
    price_date,
    value,
    source: str = "USER",
    type_: str = "LAST",
) -> Price:
    row = (
        db.query(Price)
        .filter(
            Price.book_id == book_id,
            Price.commodity_id == commodity_id,
            Price.currency_id == currency_id,
            Price.price_date == price_date,
            Price.source == source,
            Price.type == type_,
        )
        .one_or_none()
    )
    if row:
        row.value = value
        db.flush()
        return row
    row = Price(
        book_id=book_id,
        commodity_id=commodity_id,
        currency_id=currency_id,
        price_date=price_date,
        source=source,
        type=type_,
        value=value,
        created_at=_now(),
    )
    db.add(row)
    db.flush()
    return row


def main() -> None:
    now = _now()
    year, month = now.year, now.month

    with SessionLocal() as db:
        with db.begin():
            admin = _get_or_create_user(db, settings.seed_admin_username, settings.seed_admin_password, "admin")
            accountant = _get_or_create_user(db, settings.seed_accountant_username, settings.seed_accountant_password, "accountant")
            manager = _get_or_create_user(db, settings.seed_manager_username, settings.seed_manager_password, "manager")

            cny = _get_or_create_commodity(db, "CURRENCY", "CNY", "人民币", 2)
            book = _get_or_create_book(db, "默认账簿", cny.id)

            # 通用配置（ObjectKV）：先放最小默认值，后续前端/接口可做可视化配置
            _get_or_create_object_kv(
                db,
                owner_type="book",
                owner_id=str(book.id),
                key="base_currency",
                value_json={"type": "CURRENCY", "code": "CNY"},
            )
            _get_or_create_object_kv(
                db,
                owner_type="book",
                owner_id=str(book.id),
                key="default_tax_rate",
                value_json={"rate": "0.07"},
            )
            _get_or_create_object_kv(
                db,
                owner_type="book",
                owner_id=str(book.id),
                key="default_payment_term_days",
                value_json={"days": 30},
            )

            # 价格/汇率（Price）：最小 seed（CNY/CNY = 1）
            _get_or_create_price(
                db,
                book_id=str(book.id),
                commodity_id=str(cny.id),
                currency_id=str(cny.id),
                price_date=now.date(),
                value=1,
                source="APP",
                type_="LAST",
            )

            # 科目树（最小闭环）
            assets = _get_or_create_account(db, book_id=book.id, parent_id=None, code="1000", name="资产", type_="ASSET", commodity_id=cny.id, allow_post=False)
            assets.description = "资产类汇总科目"
            assets.is_placeholder = True
            cash = _get_or_create_account(db, book_id=book.id, parent_id=assets.id, code="1001", name="库存现金", type_="CASH", commodity_id=cny.id, allow_post=True)
            cash.description = "现金"
            bank = _get_or_create_account(db, book_id=book.id, parent_id=assets.id, code="1002", name="银行存款", type_="BANK", commodity_id=cny.id, allow_post=True)
            bank.description = "银行"
            ar = _get_or_create_account(db, book_id=book.id, parent_id=assets.id, code="1122", name="应收账款", type_="AR", commodity_id=cny.id, allow_post=True)
            ar.description = "应收"

            liab = _get_or_create_account(db, book_id=book.id, parent_id=None, code="2000", name="负债", type_="LIABILITY", commodity_id=cny.id, allow_post=False)
            liab.description = "负债类汇总科目"
            liab.is_placeholder = True
            ap = _get_or_create_account(db, book_id=book.id, parent_id=liab.id, code="2001", name="应付账款", type_="AP", commodity_id=cny.id, allow_post=True)
            ap.description = "应付"
            tax_payable = _get_or_create_account(db, book_id=book.id, parent_id=liab.id, code="2221", name="应交税费", type_="LIABILITY", commodity_id=cny.id, allow_post=True)
            tax_payable.description = "税费"
            payroll_payable = _get_or_create_account(db, book_id=book.id, parent_id=liab.id, code="2211", name="应付职工薪酬", type_="LIABILITY", commodity_id=cny.id, allow_post=True)
            payroll_payable.description = "薪酬"

            equity = _get_or_create_account(db, book_id=book.id, parent_id=None, code="3000", name="所有者权益", type_="EQUITY", commodity_id=cny.id, allow_post=False)
            equity.description = "权益类汇总科目"
            equity.is_placeholder = True
            capital = _get_or_create_account(db, book_id=book.id, parent_id=equity.id, code="3001", name="实收资本", type_="EQUITY", commodity_id=cny.id, allow_post=True)
            capital.description = "资本"

            income = _get_or_create_account(db, book_id=book.id, parent_id=None, code="4000", name="收入", type_="INCOME", commodity_id=cny.id, allow_post=False)
            income.description = "收入类汇总科目"
            income.is_placeholder = True
            revenue = _get_or_create_account(db, book_id=book.id, parent_id=income.id, code="4001", name="主营业务收入", type_="INCOME", commodity_id=cny.id, allow_post=True)
            revenue.description = "主营业务收入"

            expense = _get_or_create_account(db, book_id=book.id, parent_id=None, code="5000", name="费用", type_="EXPENSE", commodity_id=cny.id, allow_post=False)
            expense.description = "费用类汇总科目"
            expense.is_placeholder = True
            fee = _get_or_create_account(db, book_id=book.id, parent_id=expense.id, code="5001", name="管理费用", type_="EXPENSE", commodity_id=cny.id, allow_post=True)
            fee.description = "管理费用"

            period = _get_or_create_period(db, book.id, year, month)

            # 报表口径与映射（LEGAL / MGMT 先同构）
            legal = _get_or_create_basis(db, "LEGAL", "法定口径")
            mgmt = _get_or_create_basis(db, "MGMT", "管理口径")

            # Balance Sheet
            bs_assets = _get_or_create_item(db, "BS", "BS_ASSETS", "资产", 10, "BALANCE")
            bs_liab = _get_or_create_item(db, "BS", "BS_LIABILITIES", "负债", 20, "BALANCE")
            bs_eq = _get_or_create_item(db, "BS", "BS_EQUITY", "所有者权益", 30, "BALANCE")
            _get_or_create_item(db, "BS", "BS_ASSETS_TOTAL", "资产合计", 90, "BALANCE")
            _get_or_create_item(db, "BS", "BS_LIAB_EQUITY_TOTAL", "负债与所有者权益合计", 91, "BALANCE")

            # Income Statement
            is_rev = _get_or_create_item(db, "IS", "IS_REVENUE", "收入", 10, "ACTIVITY")
            is_exp = _get_or_create_item(db, "IS", "IS_EXPENSE", "费用", 20, "ACTIVITY")
            _get_or_create_item(db, "IS", "IS_NET_PROFIT", "净利润", 90, "ACTIVITY")

            # Cash Flow (minimal)
            _get_or_create_item(db, "CF", "CF_BEGIN_CASH", "期初现金", 10, "BALANCE")
            _get_or_create_item(db, "CF", "CF_NET_CASH", "本期现金净增加额", 20, "ACTIVITY")
            _get_or_create_item(db, "CF", "CF_END_CASH", "期末现金", 90, "BALANCE")

            for basis in [legal, mgmt]:
                _get_or_create_mapping(db, basis_id=basis.id, item=bs_assets, account_id=assets.id, include_children=True)
                _get_or_create_mapping(db, basis_id=basis.id, item=bs_liab, account_id=liab.id, include_children=True)
                _get_or_create_mapping(db, basis_id=basis.id, item=bs_eq, account_id=equity.id, include_children=True)
                _get_or_create_mapping(db, basis_id=basis.id, item=is_rev, account_id=income.id, include_children=True)
                _get_or_create_mapping(db, basis_id=basis.id, item=is_exp, account_id=expense.id, include_children=True)

            # seed 客户/供应商（用于后续 UC001/UC002/UC003）
            if not db.query(Party).filter(Party.type == "CUSTOMER", Party.name == "示例客户").one_or_none():
                db.add(
                    Party(
                        type="CUSTOMER",
                        name="示例客户",
                        tax_no="",
                        credit_limit=50000,
                        payment_term_days=30,
                        contact_json={"grade": "A"},
                        created_at=_now(),
                        updated_at=_now(),
                    )
                )
            if not db.query(Party).filter(Party.type == "VENDOR", Party.name == "示例供应商").one_or_none():
                db.add(
                    Party(
                        type="VENDOR",
                        name="示例供应商",
                        tax_no="",
                        credit_limit=None,
                        payment_term_days=30,
                        contact_json={"annual_purchase_over_10m": False},
                        created_at=_now(),
                        updated_at=_now(),
                    )
                )

            # 预置一条定期交易（用于 UC006：定期交易 -> 生成草稿 -> 审批 -> 过账）
            if not db.query(ScheduledTransaction).filter(ScheduledTransaction.book_id == book.id, ScheduledTransaction.name == "示例：每月房租").one_or_none():
                db.add(
                    ScheduledTransaction(
                        book_id=str(book.id),
                        name="示例：每月房租",
                        description="每月房租 2000（借：管理费用；贷：库存现金）",
                        enabled=True,
                        rule="MONTHLY",
                        interval=1,
                        next_run_date=now.date(),
                        end_date=None,
                        template_json={
                            "description": "示例：每月房租（借：管理费用；贷：库存现金）",
                            "lines": [
                                {"account_id": str(fee.id), "debit": 2000, "credit": 0, "memo": "借：管理费用", "aux_json": {"role": "RENT_EXPENSE"}},
                                {"account_id": str(cash.id), "debit": 0, "credit": 2000, "memo": "贷：库存现金", "aux_json": {"role": "CASH"}},
                            ],
                        },
                        created_by=admin.id,
                        created_at=now,
                        updated_at=now,
                    )
                )

            # 示例草稿（APPROVED）：用于直接跑 UC004/UC005
            draft = (
                db.query(TransactionDraft)
                .filter(TransactionDraft.book_id == book.id, TransactionDraft.source_type == "MANUAL", TransactionDraft.source_id == "seed-1", TransactionDraft.version == 1)
                .one_or_none()
            )
            if not draft:
                draft = TransactionDraft(
                    book_id=book.id,
                    period_id=period.id,
                    source_type="MANUAL",
                    source_id="seed-1",
                    version=1,
                    description="示例草稿：投入资本 100 元（借：库存现金；贷：实收资本）",
                    status="APPROVED",
                    created_by=accountant.id,
                    approved_by=accountant.id,
                )
                db.add(draft)
                db.flush()

                db.add_all(
                    [
                        TransactionDraftLine(draft_id=draft.id, line_no=1, account_id=cash.id, debit=100, credit=0, memo="借：库存现金"),
                        TransactionDraftLine(draft_id=draft.id, line_no=2, account_id=capital.id, debit=0, credit=100, memo="贷：实收资本"),
                    ]
                )
                db.flush()

            # 示例业务单据（UC001/UC002）：采购/销售 -> 生成分录草稿
            vendor = db.query(Party).filter(Party.type == "VENDOR", Party.name == "示例供应商").one_or_none()
            customer = db.query(Party).filter(Party.type == "CUSTOMER", Party.name == "示例客户").one_or_none()

            seed_po = (
                db.query(BusinessDocument)
                .filter(BusinessDocument.doc_type == "PURCHASE_ORDER", BusinessDocument.doc_no == "PO-SEED-1")
                .one_or_none()
            )
            if not seed_po and vendor:
                seed_po = BusinessDocument(
                    doc_type="PURCHASE_ORDER",
                    status="SUBMITTED",
                    book_id=book.id,
                    period_id=period.id,
                    doc_date=now,
                    doc_no="PO-SEED-1",
                    party_id=vendor.id,
                    employee_id="",
                    project="行政部",
                    term_days=30,
                    description="示例采购：办公用品（含税）",
                    total_amount=214,
                    tax_amount=14,
                    currency_code="CNY",
                    revision_no=1,
                    draft_id=None,
                    created_by=admin.id,
                    approved_by=None,
                    rejected_by=None,
                    rejected_reason="",
                    created_at=now,
                    updated_at=now,
                )
                db.add(seed_po)
                db.flush()
                db.add(
                    BusinessDocumentLine(
                        doc_id=seed_po.id,
                        line_no=1,
                        description="办公用品",
                        account_id=fee.id,
                        quantity=1,
                        unit_price=200,
                        tax_rate=0.07,
                        amount=200,
                        tax_amount=14,
                        memo="办公用品",
                    )
                )
                db.flush()
                d_po = TransactionDraft(
                    book_id=book.id,
                    period_id=period.id,
                    source_type="PURCHASE_ORDER",
                    source_id=str(seed_po.id),
                    version=1,
                    description="示例采购：办公用品（借：管理费用；贷：应付账款）",
                    status="DRAFT",
                    created_by=admin.id,
                    approved_by=None,
                )
                db.add(d_po)
                db.flush()
                db.add_all(
                    [
                        TransactionDraftLine(
                            draft_id=d_po.id,
                            line_no=1,
                            account_id=fee.id,
                            debit=214,
                            credit=0,
                            memo="借：管理费用",
                            aux_json={"doc_type": "PURCHASE_ORDER", "doc_id": str(seed_po.id), "doc_line_no": 1, "role": "EXPENSE"},
                        ),
                        TransactionDraftLine(
                            draft_id=d_po.id,
                            line_no=2,
                            account_id=ap.id,
                            debit=0,
                            credit=214,
                            memo="贷：应付账款",
                            aux_json={"doc_type": "PURCHASE_ORDER", "doc_id": str(seed_po.id), "role": "AP"},
                        ),
                    ]
                )
                db.flush()
                seed_po.draft_id = d_po.id
                db.flush()

            seed_so = (
                db.query(BusinessDocument)
                .filter(BusinessDocument.doc_type == "SALES_ORDER", BusinessDocument.doc_no == "SO-SEED-1")
                .one_or_none()
            )
            if not seed_so and customer:
                seed_so = BusinessDocument(
                    doc_type="SALES_ORDER",
                    status="SUBMITTED",
                    book_id=book.id,
                    period_id=period.id,
                    doc_date=now,
                    doc_no="SO-SEED-1",
                    party_id=customer.id,
                    employee_id="",
                    project="销售部",
                    term_days=30,
                    description="示例销售：咨询服务（含税）",
                    total_amount=1130,
                    tax_amount=130,
                    currency_code="CNY",
                    revision_no=1,
                    draft_id=None,
                    created_by=admin.id,
                    approved_by=None,
                    rejected_by=None,
                    rejected_reason="",
                    created_at=now,
                    updated_at=now,
                )
                db.add(seed_so)
                db.flush()
                db.add(
                    BusinessDocumentLine(
                        doc_id=seed_so.id,
                        line_no=1,
                        description="咨询服务",
                        account_id=revenue.id,
                        quantity=1,
                        unit_price=1000,
                        tax_rate=0.13,
                        amount=1000,
                        tax_amount=130,
                        memo="咨询服务收入",
                    )
                )
                db.flush()
                d_so = TransactionDraft(
                    book_id=book.id,
                    period_id=period.id,
                    source_type="SALES_ORDER",
                    source_id=str(seed_so.id),
                    version=1,
                    description="示例销售：咨询服务（借：应收账款；贷：收入/税费）",
                    status="DRAFT",
                    created_by=admin.id,
                    approved_by=None,
                )
                db.add(d_so)
                db.flush()
                db.add_all(
                    [
                        TransactionDraftLine(
                            draft_id=d_so.id,
                            line_no=1,
                            account_id=revenue.id,
                            debit=0,
                            credit=1000,
                            memo="贷：主营业务收入",
                            aux_json={"doc_type": "SALES_ORDER", "doc_id": str(seed_so.id), "doc_line_no": 1, "role": "REVENUE"},
                        ),
                        TransactionDraftLine(
                            draft_id=d_so.id,
                            line_no=2,
                            account_id=tax_payable.id,
                            debit=0,
                            credit=130,
                            memo="贷：应交税费",
                            aux_json={"doc_type": "SALES_ORDER", "doc_id": str(seed_so.id), "role": "TAX"},
                        ),
                        TransactionDraftLine(
                            draft_id=d_so.id,
                            line_no=3,
                            account_id=ar.id,
                            debit=1130,
                            credit=0,
                            memo="借：应收账款",
                            aux_json={"doc_type": "SALES_ORDER", "doc_id": str(seed_so.id), "role": "AR"},
                        ),
                    ]
                )
                db.flush()
                seed_so.draft_id = d_so.id
                db.flush()

            # 示例业务单据（UC003）：报销单 -> 分录草稿（待审核/待过账）
            seed_ec = (
                db.query(BusinessDocument)
                .filter(BusinessDocument.doc_type == "EXPENSE_CLAIM", BusinessDocument.doc_no == "EC-SEED-1")
                .one_or_none()
            )
            if not seed_ec:
                seed_ec = BusinessDocument(
                    doc_type="EXPENSE_CLAIM",
                    status="SUBMITTED",
                    book_id=book.id,
                    period_id=period.id,
                    doc_date=now,
                    doc_no="EC-SEED-1",
                    party_id=None,
                    employee_id="E001",
                    project="示例部门",
                    term_days=None,
                    description="示例报销：差旅（含税）",
                    total_amount=107,
                    tax_amount=7,
                    currency_code="CNY",
                    revision_no=1,
                    draft_id=None,
                    created_by=admin.id,
                    approved_by=None,
                    rejected_by=None,
                    rejected_reason="",
                    created_at=now,
                    updated_at=now,
                )
                db.add(seed_ec)
                db.flush()
                db.add(
                    BusinessDocumentLine(
                        doc_id=seed_ec.id,
                        line_no=1,
                        description="差旅",
                        account_id=fee.id,
                        quantity=1,
                        unit_price=100,
                        tax_rate=0.07,
                        amount=100,
                        tax_amount=7,
                        memo="差旅费",
                    )
                )
                db.flush()

                # 对应分录草稿：借 107 管理费用；贷 107 应付职工薪酬
                d2 = TransactionDraft(
                    book_id=book.id,
                    period_id=period.id,
                    source_type="EXPENSE_CLAIM",
                    source_id=str(seed_ec.id),
                    version=1,
                    description="示例报销：差旅（借：管理费用；贷：应付职工薪酬）",
                    status="DRAFT",
                    created_by=admin.id,
                    approved_by=None,
                )
                db.add(d2)
                db.flush()
                db.add_all(
                    [
                        TransactionDraftLine(
                            draft_id=d2.id,
                            line_no=1,
                            account_id=fee.id,
                            debit=107,
                            credit=0,
                            memo="借：管理费用",
                            aux_json={"doc_type": "EXPENSE_CLAIM", "doc_id": str(seed_ec.id), "doc_line_no": 1},
                        ),
                        TransactionDraftLine(
                            draft_id=d2.id,
                            line_no=2,
                            account_id=payroll_payable.id,
                            debit=0,
                            credit=107,
                            memo="贷：应付职工薪酬",
                            aux_json={"doc_type": "EXPENSE_CLAIM", "doc_id": str(seed_ec.id), "role": "PAYROLL"},
                        ),
                    ]
                )
                db.flush()
                seed_ec.draft_id = d2.id
                db.flush()


if __name__ == "__main__":
    main()


