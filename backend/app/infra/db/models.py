from __future__ import annotations

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import Base


def utcnow() -> datetime:
    # 为跨数据库（尤其 MySQL）兼容，统一存 UTC naive
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    username: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # admin / accountant / manager
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)


class Commodity(Base):
    __tablename__ = "commodities"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    type: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # CURRENCY / SECURITY
    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    precision: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=2)

    __table_args__ = (sa.UniqueConstraint("type", "code", name="uq_commodities_type_code"),)


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    base_currency_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("commodities.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)

    base_currency: Mapped[Commodity] = relationship(lazy="joined")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), nullable=True)
    code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    description: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    type: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    commodity_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("commodities.id"), nullable=False)
    allow_post: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    is_hidden: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    is_placeholder: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)

    parent: Mapped["Account | None"] = relationship(remote_side=[id], lazy="joined")
    commodity: Mapped[Commodity] = relationship(lazy="joined")

    __table_args__ = (
        sa.UniqueConstraint("book_id", "code", name="uq_accounts_book_code"),
        sa.Index("ix_accounts_book_parent", "book_id", "parent_id"),
    )


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    month: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # OPEN / CLOSED
    opened_at: Mapped[datetime | None] = mapped_column(sa.DateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(), nullable=True)

    __table_args__ = (sa.UniqueConstraint("book_id", "year", "month", name="uq_period_book_year_month"),)


class TransactionDraft(Base):
    __tablename__ = "transaction_drafts"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    period_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounting_periods.id"), nullable=False, index=True)
    # 多币种：草稿层就记录交易币种与交易日期，过账时写入 transactions
    currency_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("commodities.id"), nullable=True, index=True)
    txn_date: Mapped[datetime] = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    source_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="MANUAL", index=True)
    source_id: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="DRAFT")  # DRAFT/SUBMITTED/APPROVED/REJECTED/POSTED
    created_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    posted_txn_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("transactions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("book_id", "source_type", "source_id", "version", name="uq_draft_source"),
        sa.UniqueConstraint("posted_txn_id", name="uq_draft_posted_txn_id"),
    )


class TransactionDraftLine(Base):
    __tablename__ = "transaction_draft_lines"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    draft_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("transaction_drafts.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    account_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), nullable=False, index=True)
    debit: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    credit: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    memo: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    aux_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("draft_id", "line_no", name="uq_draft_line_no"),
        sa.CheckConstraint("debit >= 0", name="ck_draft_line_debit_nonneg"),
        sa.CheckConstraint("credit >= 0", name="ck_draft_line_credit_nonneg"),
    )


class VoucherSequence(Base):
    __tablename__ = "voucher_sequences"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    month: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    next_num: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (sa.UniqueConstraint("book_id", "year", "month", name="uq_vseq_book_year_month"),)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    period_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounting_periods.id"), nullable=False, index=True)
    txn_date: Mapped[datetime] = mapped_column(sa.DateTime(), nullable=False)
    # GnuCash-like: transaction currency (quote currency for split.value)
    currency_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("commodities.id"), nullable=True, index=True)
    enter_date: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    num: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    description: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    notes: Mapped[str] = mapped_column(sa.String(1024), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    idempotency_key: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    posted_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    posted_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="POSTED")  # POSTED/VOID

    __table_args__ = (
        sa.UniqueConstraint("idempotency_key", name="uq_txn_idempotency_key"),
        sa.UniqueConstraint("book_id", "source_type", "source_id", "version", name="uq_txn_source"),
        sa.UniqueConstraint("book_id", "period_id", "num", name="uq_txn_period_num"),
    )


class Split(Base):
    __tablename__ = "splits"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    txn_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("transactions.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    account_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), nullable=False, index=True)
    amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False)
    value: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False)
    memo: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    action: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="")
    reconcile_state: Mapped[str] = mapped_column(sa.String(1), nullable=False, default="n")  # n/c/y
    reconcile_date: Mapped[date | None] = mapped_column(sa.Date(), nullable=True)
    lot_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("lots.id"), nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("txn_id", "line_no", name="uq_splits_txn_line_no"),
        sa.CheckConstraint("reconcile_state in ('n','c','y')", name="ck_splits_reconcile_state"),
    )


class ScheduledTransaction(Base):
    __tablename__ = "scheduled_transactions"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    description: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    rule: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # DAILY/WEEKLY/MONTHLY
    interval: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    next_run_date: Mapped[date] = mapped_column(sa.Date(), nullable=False)
    end_date: Mapped[date | None] = mapped_column(sa.Date(), nullable=True)
    template_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("book_id", "name", name="uq_sched_book_name"),
        sa.Index("ix_sched_book_next", "book_id", "next_run_date"),
    )


class ScheduledRun(Base):
    __tablename__ = "scheduled_runs"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    sched_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("scheduled_transactions.id"), nullable=False, index=True)
    run_date: Mapped[date] = mapped_column(sa.Date(), nullable=False)
    draft_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("transaction_drafts.id"), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # OK/SKIPPED/FAILED
    error: Mapped[str] = mapped_column(sa.String(512), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)

    __table_args__ = (sa.UniqueConstraint("sched_id", "run_date", name="uq_sched_run_date"),)


class ReconcileSession(Base):
    __tablename__ = "reconcile_sessions"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), nullable=False, index=True)
    statement_date: Mapped[date] = mapped_column(sa.Date(), nullable=False)
    ending_balance: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="OPEN")  # OPEN/FINISHED
    created_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(), nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("account_id", "statement_date", name="uq_recon_account_date"),
        sa.Index("ix_recon_account_status", "account_id", "status"),
    )


class ReconcileMatch(Base):
    __tablename__ = "reconcile_matches"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("reconcile_sessions.id"), nullable=False, index=True)
    split_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("splits.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)

    __table_args__ = (sa.UniqueConstraint("session_id", "split_id", name="uq_recon_session_split"),)


class AccountBalance(Base):
    __tablename__ = "account_balances"

    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), primary_key=True)
    period_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounting_periods.id"), primary_key=True)
    account_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), primary_key=True)
    balance_value: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)
    hash_chain_prev: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    hash_chain: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)

    __table_args__ = (sa.UniqueConstraint("hash_chain", name="uq_audit_hash_chain"),)


class ReportBasis(Base):
    __tablename__ = "report_bases"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(sa.String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)


class ReportItem(Base):
    __tablename__ = "report_items"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    statement_type: Mapped[str] = mapped_column(sa.String(8), nullable=False)  # BS/IS/CF
    code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    display_order: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    calc_mode: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="BALANCE")  # BALANCE/ACTIVITY

    __table_args__ = (sa.UniqueConstraint("statement_type", "code", name="uq_report_item_type_code"),)


class ReportMapping(Base):
    __tablename__ = "report_mappings"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    basis_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("report_bases.id"), nullable=False, index=True)
    statement_type: Mapped[str] = mapped_column(sa.String(8), nullable=False)  # BS/IS/CF
    item_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("report_items.id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), nullable=False, index=True)
    include_children: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    direction: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="NET")  # NET/DEBIT/CREDIT

    __table_args__ = (
        sa.UniqueConstraint("basis_id", "item_id", "account_id", name="uq_report_map_basis_item_account"),
        sa.UniqueConstraint("basis_id", "statement_type", "account_id", name="uq_report_map_basis_type_account"),
    )


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    period_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounting_periods.id"), nullable=False, index=True)
    basis_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("report_bases.id"), nullable=False, index=True)
    params_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    generated_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    is_stale: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    result_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)
    log_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)

    __table_args__ = (sa.UniqueConstraint("book_id", "params_hash", name="uq_report_snapshot_book_params_hash"),)


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    type: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # CUSTOMER / VENDOR
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    tax_no: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="")
    credit_limit: Mapped[sa.Numeric | None] = mapped_column(sa.Numeric(18, 2), nullable=True)
    payment_term_days: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    contact_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (sa.UniqueConstraint("type", "name", name="uq_parties_type_name"),)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    owner_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(sa.String(36), nullable=True)
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(128), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    url: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    uploaded_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)

    __table_args__ = (sa.Index("ix_attachments_owner", "owner_type", "owner_id"),)


class TransactionDraftRevision(Base):
    __tablename__ = "transaction_draft_revisions"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    draft_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("transaction_drafts.id"), nullable=False, index=True)
    rev_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    action: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # CREATE/SUBMIT/APPROVE/REJECT/RESUBMIT/POST
    reason: Mapped[str] = mapped_column(sa.String(512), nullable=False, default="")
    actor_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    payload_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)

    __table_args__ = (sa.UniqueConstraint("draft_id", "rev_no", name="uq_draft_revision_no"),)


class BusinessDocument(Base):
    __tablename__ = "business_documents"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    doc_type: Mapped[str] = mapped_column(sa.String(24), nullable=False)  # PURCHASE_ORDER/SALES_ORDER/EXPENSE_CLAIM
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="DRAFT")  # DRAFT/SUBMITTED/REJECTED/APPROVED
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    period_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounting_periods.id"), nullable=False, index=True)
    doc_date: Mapped[datetime] = mapped_column(sa.DateTime(), nullable=False, default=utcnow)
    doc_no: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="")
    party_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("parties.id"), nullable=True)
    employee_id: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="")
    project: Mapped[str] = mapped_column(sa.String(128), nullable=False, default="")
    term_days: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    description: Mapped[str] = mapped_column(sa.String(512), nullable=False, default="")
    total_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    tax_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    currency_code: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="CNY")
    revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    draft_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("transaction_drafts.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("users.id"), nullable=True)
    rejected_reason: Mapped[str] = mapped_column(sa.String(512), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)

    party: Mapped[Party | None] = relationship(lazy="joined")

    __table_args__ = (sa.UniqueConstraint("doc_type", "doc_no", name="uq_business_doc_type_no"),)


class BusinessDocumentLine(Base):
    __tablename__ = "business_document_lines"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    doc_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("business_documents.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    description: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    account_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), nullable=False, index=True)
    quantity: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 4), nullable=False, default=0)
    unit_price: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 4), nullable=False, default=0)
    tax_rate: Mapped[sa.Numeric] = mapped_column(sa.Numeric(9, 6), nullable=False, default=0)
    amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    tax_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    memo: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")

    __table_args__ = (sa.UniqueConstraint("doc_id", "line_no", name="uq_business_doc_line_no"),)


class Lot(Base):
    """
    GnuCash-like lot：用于应收/应付等需要“核销/结清/部分结清”的场景。
    在本项目里，Split 可选关联到 Lot（Split.lot_id）。
    """

    __tablename__ = "lots"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    notes: Mapped[str] = mapped_column(sa.String(1024), nullable=False, default="")
    is_closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(), nullable=True)

    __table_args__ = (sa.Index("ix_lots_book_account_status", "book_id", "account_id", "is_closed"),)


class Price(Base):
    """
    价格/汇率表：用来描述 commodity -> currency 的价格（例如 USD/CNY）。
    对齐 GnuCash 的核心概念，但不引入其 GPL 实现代码。
    """

    __tablename__ = "prices"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    commodity_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("commodities.id"), nullable=False, index=True)
    currency_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("commodities.id"), nullable=False, index=True)
    price_date: Mapped[date] = mapped_column(sa.Date(), nullable=False, index=True)
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="USER")  # USER/APP/IMPORT/...
    type: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="LAST")  # LAST/AVERAGE/...
    value: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint(
            "book_id",
            "commodity_id",
            "currency_id",
            "price_date",
            "source",
            "type",
            name="uq_prices_pair_date_source_type",
        ),
        sa.Index("ix_prices_pair_date", "book_id", "commodity_id", "currency_id", "price_date"),
    )


class ObjectKV(Base):
    """
    通用 Key-Value 扩展表：用于存放各类对象的扩展字段/元数据。
    - owner_type: 字符串（如 'book'/'account'/'txn'/'invoice'）
    - owner_id: 对应对象的 id（一般为 36 字符 UUID）
    - key/value_json: 可扩展内容
    """

    __tablename__ = "object_kv"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    owner_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    owner_id: Mapped[str] = mapped_column(sa.String(36), nullable=False, index=True)
    key: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    value_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("owner_type", "owner_id", "key", name="uq_object_kv_owner_key"),
        sa.Index("ix_object_kv_owner", "owner_type", "owner_id"),
    )


class Invoice(Base):
    """
    AR/AP 发票（骨架）：为后续“收/付款 + 核销 + 账龄”等功能提供标准落库结构。
    目前项目已有的 SALES_ORDER/PURCHASE_ORDER 仍保留（不破坏既有 UC001-UC005）。
    """

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    invoice_type: Mapped[str] = mapped_column(sa.String(8), nullable=False, index=True)  # AR/AP
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="DRAFT", index=True)  # DRAFT/POSTED/PAID/VOID

    doc_no: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="", index=True)
    doc_date: Mapped[datetime] = mapped_column(sa.DateTime(), nullable=False, default=utcnow, index=True)
    due_date: Mapped[date | None] = mapped_column(sa.Date(), nullable=True, index=True)

    party_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("parties.id"), nullable=True, index=True)
    currency_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("commodities.id"), nullable=False, index=True)

    notes: Mapped[str] = mapped_column(sa.String(1024), nullable=False, default="")
    total_net: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    total_tax: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    total_gross: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)

    posted_txn_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("transactions.id"), nullable=True, index=True)
    lot_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("lots.id"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (sa.UniqueConstraint("book_id", "invoice_type", "doc_no", name="uq_invoices_book_type_no"),)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    invoice_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("invoices.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    description: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")
    account_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("accounts.id"), nullable=False, index=True)
    quantity: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 4), nullable=False, default=0)
    unit_price: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 4), nullable=False, default=0)
    tax_rate: Mapped[sa.Numeric] = mapped_column(sa.Numeric(9, 6), nullable=False, default=0)
    amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    tax_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    memo: Mapped[str] = mapped_column(sa.String(256), nullable=False, default="")

    __table_args__ = (sa.UniqueConstraint("invoice_id", "line_no", name="uq_invoice_line_no"),)


class Payment(Base):
    """
    收/付款（骨架）：可关联到一笔总账 Transaction（txn_id），并通过 PaymentApplication 应用到发票（核销）。
    """

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("books.id"), nullable=False, index=True)
    payment_type: Mapped[str] = mapped_column(sa.String(16), nullable=False, index=True)  # RECEIPT/DISBURSEMENT
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="DRAFT", index=True)  # DRAFT/POSTED/VOID

    pay_date: Mapped[datetime] = mapped_column(sa.DateTime(), nullable=False, default=utcnow, index=True)
    party_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("parties.id"), nullable=True, index=True)
    currency_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("commodities.id"), nullable=False, index=True)
    amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)

    method: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="")
    reference_no: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="")
    notes: Mapped[str] = mapped_column(sa.String(512), nullable=False, default="")

    txn_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("transactions.id"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, onupdate=utcnow, nullable=False)


class PaymentApplication(Base):
    __tablename__ = "payment_applications"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=uuid_str)
    payment_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("payments.id"), nullable=False, index=True)
    invoice_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("invoices.id"), nullable=False, index=True)
    amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(18, 2), nullable=False, default=0)
    applied_at: Mapped[datetime] = mapped_column(sa.DateTime(), default=utcnow, nullable=False)

    __table_args__ = (sa.UniqueConstraint("payment_id", "invoice_id", name="uq_payment_invoice"),)
