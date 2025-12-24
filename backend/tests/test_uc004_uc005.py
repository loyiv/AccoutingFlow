from __future__ import annotations

from app.application.gl.posting import post_draft, precheck_draft
from app.application.reports.generator import generate_reports
from app.infra.db.models import TransactionDraft
from app.infra.db.session import SessionLocal
from app.scripts.init_db import main as seed_main


def test_uc004_uc005_min_loop(migrated_db):
    # seed
    seed_main()

    with SessionLocal() as db:
        draft = db.query(TransactionDraft).filter(TransactionDraft.source_id == "seed-1").one()

        pre = precheck_draft(db, str(draft.id))
        assert pre.ok is True

        r1 = post_draft(db, str(draft.id), actor_user_id=None)
        assert r1.voucher_num

        # 幂等：重复过账应返回同一 txn
        r2 = post_draft(db, str(draft.id), actor_user_id=None)
        assert r2.txn_id == r1.txn_id
        assert r2.voucher_num == r1.voucher_num

        # UC005：生成报表快照
        snap = generate_reports(db, book_id=str(draft.book_id), period_id=str(draft.period_id), basis_code="LEGAL", actor_user_id=None)
        assert snap.snapshot_id


