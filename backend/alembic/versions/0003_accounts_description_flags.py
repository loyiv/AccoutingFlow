"""accounts: description + flags (gnucash-like ui fields)

Revision ID: 0003_accounts_description_flags
Revises: 0002_business_attachments_revisions
Create Date: 2025-12-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_accounts_description_flags"
down_revision = "0002_business"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("accounts")}
    if "description" not in cols:
        op.add_column("accounts", sa.Column("description", sa.String(length=256), nullable=False, server_default=""))
    if "is_hidden" not in cols:
        op.add_column("accounts", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    if "is_placeholder" not in cols:
        op.add_column("accounts", sa.Column("is_placeholder", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("accounts", "is_placeholder")
    op.drop_column("accounts", "is_hidden")
    op.drop_column("accounts", "description")


