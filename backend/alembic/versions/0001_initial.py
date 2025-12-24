"""initial schema (MySQL compatible) - M1 UC004/UC005 minimal loop

Revision ID: 0001_initial
Revises:
Create Date: 2025-12-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


ID36 = sa.String(length=36)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "commodities",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("precision", sa.Integer(), nullable=False, server_default="2"),
        sa.UniqueConstraint("type", "code", name="uq_commodities_type_code"),
    )
    op.create_index("ix_commodities_code", "commodities", ["code"], unique=False)

    op.create_table(
        "books",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("base_currency_id", ID36, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["base_currency_id"], ["commodities.id"]),
    )

    op.create_table(
        "accounts",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("book_id", ID36, nullable=False),
        sa.Column("parent_id", ID36, nullable=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=24), nullable=False),
        sa.Column("commodity_id", ID36, nullable=False),
        sa.Column("allow_post", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"]),
        sa.UniqueConstraint("book_id", "code", name="uq_accounts_book_code"),
    )
    op.create_index("ix_accounts_book_id", "accounts", ["book_id"], unique=False)
    op.create_index("ix_accounts_book_parent", "accounts", ["book_id", "parent_id"], unique=False)

    op.create_table(
        "accounting_periods",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("book_id", ID36, nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.UniqueConstraint("book_id", "year", "month", name="uq_period_book_year_month"),
    )
    op.create_index("ix_accounting_periods_book_id", "accounting_periods", ["book_id"], unique=False)

    op.create_table(
        "voucher_sequences",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("book_id", ID36, nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("next_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.UniqueConstraint("book_id", "year", "month", name="uq_vseq_book_year_month"),
    )
    op.create_index("ix_voucher_sequences_book_id", "voucher_sequences", ["book_id"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("book_id", ID36, nullable=False),
        sa.Column("period_id", ID36, nullable=False),
        sa.Column("txn_date", sa.DateTime(), nullable=False),
        sa.Column("num", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("posted_by", ID36, nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="POSTED"),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["accounting_periods.id"]),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"]),
        sa.UniqueConstraint("book_id", "period_id", "num", name="uq_txn_period_num"),
        sa.UniqueConstraint("book_id", "source_type", "source_id", "version", name="uq_txn_source"),
        sa.UniqueConstraint("idempotency_key", name="uq_txn_idempotency_key"),
    )
    op.create_index("ix_transactions_book_id", "transactions", ["book_id"], unique=False)
    op.create_index("ix_transactions_period_id", "transactions", ["period_id"], unique=False)

    op.create_table(
        "transaction_drafts",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("book_id", ID36, nullable=False),
        sa.Column("period_id", ID36, nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="MANUAL"),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", ID36, nullable=True),
        sa.Column("approved_by", ID36, nullable=True),
        sa.Column("posted_txn_id", ID36, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["accounting_periods.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["posted_txn_id"], ["transactions.id"]),
        sa.UniqueConstraint("book_id", "source_type", "source_id", "version", name="uq_draft_source"),
        sa.UniqueConstraint("posted_txn_id", name="uq_draft_posted_txn_id"),
    )
    op.create_index("ix_transaction_drafts_book_id", "transaction_drafts", ["book_id"], unique=False)
    op.create_index("ix_transaction_drafts_period_id", "transaction_drafts", ["period_id"], unique=False)
    op.create_index("ix_transaction_drafts_source_type", "transaction_drafts", ["source_type"], unique=False)
    op.create_index("ix_transaction_drafts_source_id", "transaction_drafts", ["source_id"], unique=False)

    op.create_table(
        "transaction_draft_lines",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("draft_id", ID36, nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("account_id", ID36, nullable=False),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("memo", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("aux_json", sa.JSON(), nullable=True),
        sa.CheckConstraint("debit >= 0", name="ck_draft_line_debit_nonneg"),
        sa.CheckConstraint("credit >= 0", name="ck_draft_line_credit_nonneg"),
        sa.ForeignKeyConstraint(["draft_id"], ["transaction_drafts.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.UniqueConstraint("draft_id", "line_no", name="uq_draft_line_no"),
    )
    op.create_index("ix_transaction_draft_lines_draft_id", "transaction_draft_lines", ["draft_id"], unique=False)
    op.create_index("ix_transaction_draft_lines_account_id", "transaction_draft_lines", ["account_id"], unique=False)

    op.create_table(
        "splits",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("txn_id", ID36, nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("account_id", ID36, nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("value", sa.Numeric(18, 2), nullable=False),
        sa.Column("memo", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("reconcile_state", sa.String(length=1), nullable=False, server_default="n"),
        sa.Column("lot_id", ID36, nullable=True),
        sa.CheckConstraint("reconcile_state in ('n','c','y')", name="ck_splits_reconcile_state"),
        sa.ForeignKeyConstraint(["txn_id"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.UniqueConstraint("txn_id", "line_no", name="uq_splits_txn_line_no"),
    )
    op.create_index("ix_splits_txn_id", "splits", ["txn_id"], unique=False)
    op.create_index("ix_splits_account_id", "splits", ["account_id"], unique=False)

    op.create_table(
        "account_balances",
        sa.Column("book_id", ID36, nullable=False),
        sa.Column("period_id", ID36, nullable=False),
        sa.Column("account_id", ID36, nullable=False),
        sa.Column("balance_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["accounting_periods.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("book_id", "period_id", "account_id", name="pk_account_balances"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("actor_id", ID36, nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("hash_chain_prev", sa.String(length=64), nullable=True),
        sa.Column("hash_chain", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.UniqueConstraint("hash_chain", name="uq_audit_hash_chain"),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"], unique=False)
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"], unique=False)
    op.create_index("ix_audit_logs_at", "audit_logs", ["at"], unique=False)
    op.create_index("ix_audit_logs_hash_chain", "audit_logs", ["hash_chain"], unique=False)

    op.create_table(
        "report_bases",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("code", name="uq_report_bases_code"),
    )

    op.create_table(
        "report_items",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("statement_type", sa.String(length=8), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calc_mode", sa.String(length=16), nullable=False, server_default="BALANCE"),
        sa.UniqueConstraint("statement_type", "code", name="uq_report_item_type_code"),
    )

    op.create_table(
        "report_mappings",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("basis_id", ID36, nullable=False),
        sa.Column("statement_type", sa.String(length=8), nullable=False),
        sa.Column("item_id", ID36, nullable=False),
        sa.Column("account_id", ID36, nullable=False),
        sa.Column("include_children", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="NET"),
        sa.ForeignKeyConstraint(["basis_id"], ["report_bases.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["report_items.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.UniqueConstraint("basis_id", "item_id", "account_id", name="uq_report_map_basis_item_account"),
        sa.UniqueConstraint("basis_id", "statement_type", "account_id", name="uq_report_map_basis_type_account"),
    )
    op.create_index("ix_report_mappings_basis_id", "report_mappings", ["basis_id"], unique=False)
    op.create_index("ix_report_mappings_item_id", "report_mappings", ["item_id"], unique=False)
    op.create_index("ix_report_mappings_account_id", "report_mappings", ["account_id"], unique=False)

    op.create_table(
        "report_snapshots",
        sa.Column("id", ID36, primary_key=True),
        sa.Column("book_id", ID36, nullable=False),
        sa.Column("period_id", ID36, nullable=False),
        sa.Column("basis_id", ID36, nullable=False),
        sa.Column("params_hash", sa.String(length=64), nullable=False),
        sa.Column("generated_by", ID36, nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("log_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["accounting_periods.id"]),
        sa.ForeignKeyConstraint(["basis_id"], ["report_bases.id"]),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"]),
        sa.UniqueConstraint("book_id", "params_hash", name="uq_report_snapshot_book_params_hash"),
    )
    op.create_index("ix_report_snapshots_book_id", "report_snapshots", ["book_id"], unique=False)
    op.create_index("ix_report_snapshots_period_id", "report_snapshots", ["period_id"], unique=False)
    op.create_index("ix_report_snapshots_basis_id", "report_snapshots", ["basis_id"], unique=False)


def downgrade() -> None:
    op.drop_table("report_snapshots")
    op.drop_table("report_mappings")
    op.drop_table("report_items")
    op.drop_table("report_bases")
    op.drop_table("audit_logs")
    op.drop_table("account_balances")
    op.drop_table("splits")
    op.drop_table("transaction_draft_lines")
    op.drop_table("transaction_drafts")
    op.drop_table("transactions")
    op.drop_table("voucher_sequences")
    op.drop_table("accounting_periods")
    op.drop_table("accounts")
    op.drop_table("books")
    op.drop_table("commodities")
    op.drop_table("users")


