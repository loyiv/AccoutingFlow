"""business docs + attachments + draft revisions (UC001-UC003 support)

Revision ID: 0002_business
Revises: 0001_initial
Create Date: 2025-12-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_business"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

ID36 = sa.String(length=36)

def _has_table(name: str) -> bool:
    # MySQL 下 DDL 非事务，迁移失败可能已创建部分表；这里做幂等保护
    return sa.inspect(op.get_bind()).has_table(name)


def _has_index(table: str, index_name: str) -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        idx = insp.get_indexes(table)
    except Exception:
        return False
    return any(i.get("name") == index_name for i in idx)


def upgrade() -> None:
    if not _has_table("parties"):
        op.create_table(
            "parties",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("type", sa.String(length=16), nullable=False),  # CUSTOMER/VENDOR
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("tax_no", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("credit_limit", sa.Numeric(18, 2), nullable=True),
            sa.Column("payment_term_days", sa.Integer(), nullable=True),
            sa.Column("contact_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("type", "name", name="uq_parties_type_name"),
        )
    if not _has_index("parties", "ix_parties_type"):
        op.create_index("ix_parties_type", "parties", ["type"], unique=False)

    if not _has_table("attachments"):
        op.create_table(
            "attachments",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("owner_type", sa.String(length=32), nullable=False),  # business_doc/draft/other
            sa.Column("owner_id", ID36, nullable=True),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("storage_path", sa.String(length=512), nullable=False),
            sa.Column("url", sa.String(length=512), nullable=False),
            sa.Column("uploaded_by", ID36, nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        )
    if not _has_index("attachments", "ix_attachments_owner"):
        op.create_index("ix_attachments_owner", "attachments", ["owner_type", "owner_id"], unique=False)

    if not _has_table("transaction_draft_revisions"):
        op.create_table(
            "transaction_draft_revisions",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("draft_id", ID36, nullable=False),
            sa.Column("rev_no", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),  # CREATE/SUBMIT/APPROVE/REJECT/RESUBMIT/POST
            sa.Column("reason", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("actor_id", ID36, nullable=True),
            sa.Column("at", sa.DateTime(), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(["draft_id"], ["transaction_drafts.id"]),
            sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
            sa.UniqueConstraint("draft_id", "rev_no", name="uq_draft_revision_no"),
        )
    if not _has_index("transaction_draft_revisions", "ix_draft_revisions_draft_id"):
        op.create_index("ix_draft_revisions_draft_id", "transaction_draft_revisions", ["draft_id"], unique=False)

    if not _has_table("business_documents"):
        op.create_table(
            "business_documents",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("doc_type", sa.String(length=24), nullable=False),  # PURCHASE_ORDER/SALES_ORDER/EXPENSE_CLAIM
            sa.Column("status", sa.String(length=24), nullable=False),  # DRAFT/SUBMITTED/REJECTED/APPROVED
            sa.Column("book_id", ID36, nullable=False),
            sa.Column("period_id", ID36, nullable=False),
            sa.Column("doc_date", sa.DateTime(), nullable=False),
            sa.Column("doc_no", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("party_id", ID36, nullable=True),
            sa.Column("employee_id", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("project", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("term_days", sa.Integer(), nullable=True),
            sa.Column("description", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("currency_code", sa.String(length=16), nullable=False, server_default="CNY"),
            sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("draft_id", ID36, nullable=True),
            sa.Column("created_by", ID36, nullable=True),
            sa.Column("approved_by", ID36, nullable=True),
            sa.Column("rejected_by", ID36, nullable=True),
            sa.Column("rejected_reason", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
            sa.ForeignKeyConstraint(["period_id"], ["accounting_periods.id"]),
            sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
            sa.ForeignKeyConstraint(["draft_id"], ["transaction_drafts.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["rejected_by"], ["users.id"]),
            sa.UniqueConstraint("doc_type", "doc_no", name="uq_business_doc_type_no"),
        )
    if not _has_index("business_documents", "ix_business_docs_book_period"):
        op.create_index("ix_business_docs_book_period", "business_documents", ["book_id", "period_id"], unique=False)
    if not _has_index("business_documents", "ix_business_docs_type_status"):
        op.create_index("ix_business_docs_type_status", "business_documents", ["doc_type", "status"], unique=False)

    if not _has_table("business_document_lines"):
        op.create_table(
            "business_document_lines",
            sa.Column("id", ID36, primary_key=True),
            sa.Column("doc_id", ID36, nullable=False),
            sa.Column("line_no", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(length=256), nullable=False, server_default=""),
            sa.Column("account_id", ID36, nullable=False),
            sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("unit_price", sa.Numeric(18, 4), nullable=False, server_default="0"),
            sa.Column("tax_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
            sa.Column("memo", sa.String(length=256), nullable=False, server_default=""),
            sa.ForeignKeyConstraint(["doc_id"], ["business_documents.id"]),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
            sa.UniqueConstraint("doc_id", "line_no", name="uq_business_doc_line_no"),
        )
    if not _has_index("business_document_lines", "ix_business_doc_lines_doc_id"):
        op.create_index("ix_business_doc_lines_doc_id", "business_document_lines", ["doc_id"], unique=False)


def downgrade() -> None:
    op.drop_table("business_document_lines")
    op.drop_table("business_documents")
    op.drop_table("transaction_draft_revisions")
    op.drop_table("attachments")
    op.drop_table("parties")


