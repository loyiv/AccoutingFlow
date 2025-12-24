from __future__ import annotations

from app.application.reports.drilldown import drilldown_accounts, drilldown_register, get_transaction_detail
from app.application.reports.generator import generate_reports
from app.infra.db.models import TransactionDraft
from app.infra.db.session import SessionLocal
from app.scripts.init_db import main as seed_main
from app.application.gl.posting import post_draft
from app.application.gl.draft_workflow import approve_draft


def test_uc005_drilldown_clickthrough(migrated_db):
    seed_main()
    with SessionLocal() as db:
        # 先过账 seed-1，确保有账可报
        draft = db.query(TransactionDraft).filter(TransactionDraft.source_id == "seed-1").one()
        approve_draft(db, str(draft.id), actor_id=None)
        post_draft(db, str(draft.id), actor_user_id=None)

        snap = generate_reports(db, book_id=str(draft.book_id), period_id=str(draft.period_id), basis_code="LEGAL", actor_user_id=None)
        snapshot_id = snap.snapshot_id

        # 报表行 -> 科目
        accs = drilldown_accounts(db, snapshot_id, "BS", "BS_ASSETS")
        assert isinstance(accs, list)
        assert len(accs) >= 1

        # 科目 -> 凭证
        reg = drilldown_register(db, snapshot_id, "BS", "BS_ASSETS", accs[0].account_id, include_children=False)
        assert isinstance(reg, list)
        assert len(reg) >= 1

        # 凭证 -> 来源单据（至少能返回 txn detail）
        tx = get_transaction_detail(db, reg[0].txn_id)
        assert tx.txn_id
        assert tx.num
        assert len(tx.splits) >= 2


