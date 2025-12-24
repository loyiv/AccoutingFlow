"""gnucash-like extensions: lots/prices/object_kv + AR/AP skeleton (invoices/payments)

Revision ID: 0005_gnucash_ext
Revises: 0004_sched_recon
Create Date: 2025-12-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_gnucash_ext"
down_revision = "0004_sched_recon"
branch_labels = None
depends_on = None

ID36 = sa.String(length=36)


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def _has_column(table: str, col: str) -> bool:
    try:
        cols = {c["name"] for c in _insp().get_columns(table)}
    except Exception:
        return False
    return col in cols


def _has_index(table: str, index_name: str) -> bool:
    try:
        idx = _insp().get_indexes(table)
    except Exception:
        return False
    return any(i.get("name") == index_name for i in idx)


def _has_fk(table: str, fk_name: str) -> bool:
    try:
        fks = _insp().get_foreign_keys(table)
    except Exception:
        return False
    return any((fk.get("name") or "") == fk_name for fk in fks)


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    # 1) lots
    if not _has_table("lots"):
        op.create_table(
            "lots",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("book_id", ID36, sa.ForeignKey("books.id"), nullable=False),
            sa.Column("account_id", ID36, sa.ForeignKey("accounts.id"), nullable=False),
            sa.Column("title", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("notes", sa.String(length=1024), nullable=False, server_default=""),
            sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("opened_at", sa.DateTime(), nullable=False),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
        )
    if not _has_index("lots", "ix_lots_book_id"):
        op.create_index("ix_lots_book_id", "lots", ["book_id"], unique=False)
    if not _has_index("lots", "ix_lots_account_id"):
        op.create_index("ix_lots_account_id", "lots", ["account_id"], unique=False)
    if not _has_index("lots", "ix_lots_book_account_status"):
        op.create_index("ix_lots_book_account_status", "lots", ["book_id", "account_id", "is_closed"], unique=False)

    # 2) prices (exchange rates / commodity prices)
    if not _has_table("prices"):
        op.create_table(
            "prices",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("book_id", ID36, sa.ForeignKey("books.id"), nullable=False),
            sa.Column("commodity_id", ID36, sa.ForeignKey("commodities.id"), nullable=False),
            sa.Column("currency_id", ID36, sa.ForeignKey("commodities.id"), nullable=False),
            sa.Column("price_date", sa.Date(), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="USER"),
            sa.Column("type", sa.String(length=32), nullable=False, server_default="LAST"),
            sa.Column("value", sa.Numeric(18, 8), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "book_id",
                "commodity_id",
                "currency_id",
                "price_date",
                "source",
                "type",
                name="uq_prices_pair_date_source_type",
            ),
        )
    if not _has_index("prices", "ix_prices_pair_date"):
        op.create_index("ix_prices_pair_date", "prices", ["book_id", "commodity_id", "currency_id", "price_date"], unique=False)
    if not _has_index("prices", "ix_prices_price_date"):
        op.create_index("ix_prices_price_date", "prices", ["price_date"], unique=False)

    # 3) object_kv (generic metadata / extension fields)
    if not _has_table("object_kv"):
        op.create_table(
            "object_kv",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("owner_type", sa.String(length=32), nullable=False),
            sa.Column("owner_id", ID36, nullable=False),
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("value_json", sa.JSON(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("owner_type", "owner_id", "key", name="uq_object_kv_owner_key"),
        )
    if not _has_index("object_kv", "ix_object_kv_owner"):
        op.create_index("ix_object_kv_owner", "object_kv", ["owner_type", "owner_id"], unique=False)
    if not _has_index("object_kv", "ix_object_kv_owner_id"):
        op.create_index("ix_object_kv_owner_id", "object_kv", ["owner_id"], unique=False)

    # 4) invoices / invoice_lines (AR/AP skeleton)
    if not _has_table("invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("book_id", ID36, sa.ForeignKey("books.id"), nullable=False),
            sa.Column("invoice_type", sa.String(length=8), nullable=False),  # AR/AP
            sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
            sa.Column("doc_no", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("doc_date", sa.DateTime(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("party_id", ID36, sa.ForeignKey("parties.id"), nullable=True),
            sa.Column("currency_id", ID36, sa.ForeignKey("commodities.id"), nullable=False),
            sa.Column("notes", sa.String(length=1024), nullable=False, server_default=""),
            sa.Column("total_net", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("total_tax", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("total_gross", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("posted_txn_id", ID36, sa.ForeignKey("transactions.id"), nullable=True),
            sa.Column("lot_id", ID36, sa.ForeignKey("lots.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("book_id", "invoice_type", "doc_no", name="uq_invoices_book_type_no"),
        )
    if not _has_index("invoices", "ix_invoices_book_id"):
        op.create_index("ix_invoices_book_id", "invoices", ["book_id"], unique=False)
    if not _has_index("invoices", "ix_invoices_type_status"):
        op.create_index("ix_invoices_type_status", "invoices", ["invoice_type", "status"], unique=False)
    if not _has_index("invoices", "ix_invoices_doc_date"):
        op.create_index("ix_invoices_doc_date", "invoices", ["doc_date"], unique=False)

    if not _has_table("invoice_lines"):
        op.create_table(
            "invoice_lines",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("invoice_id", ID36, sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("line_no", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("account_id", ID36, sa.ForeignKey("accounts.id"), nullable=False),
            sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("tax_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("memo", sa.String(length=256), nullable=False, server_default=""),
            sa.UniqueConstraint("invoice_id", "line_no", name="uq_invoice_line_no"),
        )
    if not _has_index("invoice_lines", "ix_invoice_lines_invoice_id"):
        op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"], unique=False)

    # 5) payments / applications (settlement skeleton)
    if not _has_table("payments"):
        op.create_table(
            "payments",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("book_id", ID36, sa.ForeignKey("books.id"), nullable=False),
            sa.Column("payment_type", sa.String(length=16), nullable=False),  # RECEIPT/DISBURSEMENT
            sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
            sa.Column("pay_date", sa.DateTime(), nullable=False),
            sa.Column("party_id", ID36, sa.ForeignKey("parties.id"), nullable=True),
            sa.Column("currency_id", ID36, sa.ForeignKey("commodities.id"), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("method", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("reference_no", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("notes", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("txn_id", ID36, sa.ForeignKey("transactions.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if not _has_index("payments", "ix_payments_book_id"):
        op.create_index("ix_payments_book_id", "payments", ["book_id"], unique=False)
    if not _has_index("payments", "ix_payments_type_status"):
        op.create_index("ix_payments_type_status", "payments", ["payment_type", "status"], unique=False)
    if not _has_index("payments", "ix_payments_pay_date"):
        op.create_index("ix_payments_pay_date", "payments", ["pay_date"], unique=False)

    if not _has_table("payment_applications"):
        op.create_table(
            "payment_applications",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("payment_id", ID36, sa.ForeignKey("payments.id"), nullable=False),
            sa.Column("invoice_id", ID36, sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("applied_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("payment_id", "invoice_id", name="uq_payment_invoice"),
        )
    if not _has_index("payment_applications", "ix_payment_apps_payment_id"):
        op.create_index("ix_payment_apps_payment_id", "payment_applications", ["payment_id"], unique=False)
    if not _has_index("payment_applications", "ix_payment_apps_invoice_id"):
        op.create_index("ix_payment_apps_invoice_id", "payment_applications", ["invoice_id"], unique=False)

    # 6) extend transactions/splits for gnucash-like fields
    if _has_table("transactions"):
        if not _has_column("transactions", "currency_id"):
            op.add_column("transactions", sa.Column("currency_id", ID36, nullable=True))
        if not _has_column("transactions", "enter_date"):
            op.add_column(
                "transactions",
                sa.Column("enter_date", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            )
        if not _has_column("transactions", "notes"):
            op.add_column("transactions", sa.Column("notes", sa.String(length=1024), nullable=False, server_default=""))
        if not _has_index("transactions", "ix_transactions_currency_id"):
            op.create_index("ix_transactions_currency_id", "transactions", ["currency_id"], unique=False)
        if not _has_fk("transactions", "fk_transactions_currency_id"):
            # SQLite 不支持 ALTER TABLE ADD CONSTRAINT；用 batch_alter_table
            if dialect == "sqlite":
                with op.batch_alter_table("transactions") as batch_op:
                    batch_op.create_foreign_key("fk_transactions_currency_id", "commodities", ["currency_id"], ["id"])
            else:
                op.create_foreign_key("fk_transactions_currency_id", "transactions", "commodities", ["currency_id"], ["id"])

    if _has_table("splits"):
        if not _has_column("splits", "action"):
            op.add_column("splits", sa.Column("action", sa.String(length=32), nullable=False, server_default=""))
        if not _has_column("splits", "reconcile_date"):
            op.add_column("splits", sa.Column("reconcile_date", sa.Date(), nullable=True))
        if not _has_index("splits", "ix_splits_lot_id"):
            op.create_index("ix_splits_lot_id", "splits", ["lot_id"], unique=False)
        if not _has_fk("splits", "fk_splits_lot_id"):
            # 旧表里 lot_id 已存在，这里补 FK 约束
            if dialect == "sqlite":
                with op.batch_alter_table("splits") as batch_op:
                    batch_op.create_foreign_key("fk_splits_lot_id", "lots", ["lot_id"], ["id"])
            else:
                op.create_foreign_key("fk_splits_lot_id", "splits", "lots", ["lot_id"], ["id"])


def downgrade() -> None:
    # 保守：生产环境不建议 drop；这里保持空实现
    pass


