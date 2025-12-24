"""draft: currency_id + txn_date (multi-currency posting support)

Revision ID: 0006_draft_currency_txndate
Revises: 0005_gnucash_ext
Create Date: 2025-12-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_draft_currency_txndate"
down_revision = "0005_gnucash_ext"
branch_labels = None
depends_on = None

ID36 = sa.String(length=36)


def _insp():
    return sa.inspect(op.get_bind())


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


def upgrade() -> None:
    if not _has_column("transaction_drafts", "currency_id"):
        op.add_column("transaction_drafts", sa.Column("currency_id", ID36, nullable=True))
    if not _has_column("transaction_drafts", "txn_date"):
        op.add_column(
            "transaction_drafts",
            sa.Column("txn_date", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not _has_index("transaction_drafts", "ix_transaction_drafts_currency_id"):
        op.create_index("ix_transaction_drafts_currency_id", "transaction_drafts", ["currency_id"], unique=False)
    if not _has_index("transaction_drafts", "ix_transaction_drafts_txn_date"):
        op.create_index("ix_transaction_drafts_txn_date", "transaction_drafts", ["txn_date"], unique=False)
    # FK：MySQL 下可能已存在同名约束（幂等困难），这里采用尝试创建
    try:
        op.create_foreign_key(
            "fk_drafts_currency_id",
            "transaction_drafts",
            "commodities",
            ["currency_id"],
            ["id"],
        )
    except Exception:
        pass


def downgrade() -> None:
    pass


