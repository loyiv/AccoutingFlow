"""scheduled transactions + reconciliation (GnuCash-like main features)

Revision ID: 0004_sched_recon
Revises: 0003_accounts_description_flags
Create Date: 2025-12-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_sched_recon"
down_revision = "0003_accounts_description_flags"
branch_labels = None
depends_on = None

ID36 = sa.String(length=36)


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_index(table: str, index_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        idx = insp.get_indexes(table)
    except Exception:
        return False
    return any(i.get("name") == index_name for i in idx)


def upgrade() -> None:
    if not _has_table("scheduled_transactions"):
        op.create_table(
            "scheduled_transactions",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("book_id", ID36, sa.ForeignKey("books.id"), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("rule", sa.String(length=16), nullable=False),  # DAILY/WEEKLY/MONTHLY
            sa.Column("interval", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("next_run_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("template_json", sa.JSON(), nullable=False),  # our own format (no gnucash code)
            sa.Column("created_by", ID36, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("book_id", "name", name="uq_sched_book_name"),
        )
    if not _has_index("scheduled_transactions", "ix_sched_book_next"):
        op.create_index("ix_sched_book_next", "scheduled_transactions", ["book_id", "next_run_date"], unique=False)

    if not _has_table("scheduled_runs"):
        op.create_table(
            "scheduled_runs",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("sched_id", ID36, sa.ForeignKey("scheduled_transactions.id"), nullable=False),
            sa.Column("run_date", sa.Date(), nullable=False),
            sa.Column("draft_id", ID36, sa.ForeignKey("transaction_drafts.id"), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),  # OK/SKIPPED/FAILED
            sa.Column("error", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("sched_id", "run_date", name="uq_sched_run_date"),
        )
    if not _has_index("scheduled_runs", "ix_sched_runs_sched"):
        op.create_index("ix_sched_runs_sched", "scheduled_runs", ["sched_id"], unique=False)

    if not _has_table("reconcile_sessions"):
        op.create_table(
            "reconcile_sessions",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("book_id", ID36, sa.ForeignKey("books.id"), nullable=False),
            sa.Column("account_id", ID36, sa.ForeignKey("accounts.id"), nullable=False),
            sa.Column("statement_date", sa.Date(), nullable=False),
            sa.Column("ending_balance", sa.Numeric(18, 2), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),  # OPEN/FINISHED
            sa.Column("created_by", ID36, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("account_id", "statement_date", name="uq_recon_account_date"),
        )
    if not _has_index("reconcile_sessions", "ix_recon_account_status"):
        op.create_index("ix_recon_account_status", "reconcile_sessions", ["account_id", "status"], unique=False)

    if not _has_table("reconcile_matches"):
        op.create_table(
            "reconcile_matches",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("session_id", ID36, sa.ForeignKey("reconcile_sessions.id"), nullable=False),
            sa.Column("split_id", ID36, sa.ForeignKey("splits.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("session_id", "split_id", name="uq_recon_session_split"),
        )
    if not _has_index("reconcile_matches", "ix_recon_matches_session"):
        op.create_index("ix_recon_matches_session", "reconcile_matches", ["session_id"], unique=False)


def downgrade() -> None:
    # 保守：生产环境不建议 drop；这里保持空实现
    pass


