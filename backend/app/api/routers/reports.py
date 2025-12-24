from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, require_roles
from app.api.schemas.reports import (
    DrilldownResponse,
    DrilldownRegisterResponse,
    ReportExportRequest,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportSnapshotOut,
    TransactionDetailResponse,
)
from app.application.engine.accounts import build_account_children_map, collect_descendants, list_accounts
from app.application.reports.generator import generate_reports
from app.infra.db.models import (
    Account,
    AccountingPeriod,
    ReportBasis,
    ReportItem,
    ReportMapping,
    ReportSnapshot,
    Split,
    Transaction,
)
from app.application.reports.drilldown import drilldown_accounts, drilldown_register, get_transaction_detail

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate", response_model=ReportGenerateResponse)
def generate(
    body: ReportGenerateRequest,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> ReportGenerateResponse:
    try:
        r = generate_reports(db, body.book_id, body.period_id, body.basis_code, u.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ReportGenerateResponse(snapshot_id=r.snapshot_id)


@router.get("/snapshots/{snapshot_id}", response_model=ReportSnapshotOut)
def get_snapshot(
    snapshot_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> ReportSnapshotOut:
    s = db.query(ReportSnapshot).filter(ReportSnapshot.id == snapshot_id).one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="报表快照不存在")
    basis = db.query(ReportBasis).filter(ReportBasis.id == s.basis_id).one()
    return ReportSnapshotOut(
        id=str(s.id),
        book_id=str(s.book_id),
        period_id=str(s.period_id),
        basis_code=basis.code,
        generated_at=s.generated_at.isoformat(),
        is_stale=s.is_stale,
        result=s.result_json,
        log=s.log_json,
    )


@router.get("/snapshots")
def list_snapshots(
    book_id: str = Query(...),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
):
    rows = (
        db.query(ReportSnapshot)
        .filter(ReportSnapshot.book_id == book_id)
        .order_by(ReportSnapshot.generated_at.desc())
        .limit(50)
        .all()
    )
    bases = {str(b.id): b.code for b in db.query(ReportBasis).all()}
    return [
        {
            "id": str(s.id),
            "period_id": str(s.period_id),
            "basis_code": bases.get(str(s.basis_id), ""),
            "generated_at": s.generated_at.isoformat(),
            "is_stale": s.is_stale,
        }
        for s in rows
    ]


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


@router.get("/snapshots/{snapshot_id}/drilldown", response_model=DrilldownResponse)
def drilldown(
    snapshot_id: str,
    statement_type: str = Query(..., pattern="^(BS|IS|CF)$"),
    item_code: str = Query(...),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> DrilldownResponse:
    try:
        accounts_out = drilldown_accounts(db, snapshot_id, statement_type, item_code)
        return DrilldownResponse(snapshot_id=snapshot_id, statement_type=statement_type, item_code=item_code, accounts=accounts_out)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/snapshots/{snapshot_id}/drilldown/register", response_model=DrilldownRegisterResponse)
def drilldown_register_api(
    snapshot_id: str,
    statement_type: str = Query(..., pattern="^(BS|IS|CF)$"),
    item_code: str = Query(...),
    account_id: str = Query(...),
    include_children: bool = Query(default=False),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> DrilldownRegisterResponse:
    try:
        items = drilldown_register(db, snapshot_id, statement_type, item_code, account_id, include_children=include_children)
        return DrilldownRegisterResponse(
            snapshot_id=snapshot_id,
            statement_type=statement_type,
            item_code=item_code,
            account_id=account_id,
            include_children=include_children,
            items=items,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/transactions/{txn_id}", response_model=TransactionDetailResponse)
def get_transaction_detail_api(
    txn_id: str,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
) -> TransactionDetailResponse:
    try:
        d = get_transaction_detail(db, txn_id)
        return TransactionDetailResponse(
            txn_id=d.txn_id,
            num=d.num,
            txn_date=d.txn_date,
            description=d.description,
            source_type=d.source_type,
            source_id=d.source_id,
            version=d.version,
            splits=[
                {
                    "line_no": s.line_no,
                    "account_id": s.account_id,
                    "account_code": s.account_code,
                    "account_name": s.account_name,
                    "value": s.value,
                    "memo": s.memo,
                }
                for s in d.splits
            ],
            source_doc=(
                {
                    "doc_type": d.source_doc.doc_type,
                    "doc_id": d.source_doc.doc_id,
                    "doc_no": d.source_doc.doc_no,
                    "status": d.source_doc.status,
                    "doc_date": d.source_doc.doc_date,
                    "description": d.source_doc.description,
                    "revision_no": d.source_doc.revision_no,
                    "draft_id": d.source_doc.draft_id,
                }
                if d.source_doc
                else None
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/export")
def export_report(
    body: ReportExportRequest,
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant", "manager"])),
):
    snap = db.query(ReportSnapshot).filter(ReportSnapshot.id == body.snapshot_id).one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="报表快照不存在")

    statements: dict[str, list[dict[str, Any]]] = snap.result_json.get("statements", {})

    if body.format == "excel":
        wb = Workbook()
        wb.remove(wb.active)
        for st in ["BS", "IS", "CF"]:
            ws = wb.create_sheet(st)
            ws.append(["code", "name", "amount"])
            for it in statements.get(st, []):
                ws.append([it.get("code"), it.get("name"), it.get("amount")])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=report-{body.snapshot_id}.xlsx"},
        )

    if body.format == "pdf":
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        y = h - 40
        c.setFont("Helvetica", 12)
        c.drawString(40, y, f"Report Snapshot: {body.snapshot_id}")
        y -= 30
        c.setFont("Helvetica", 10)
        for st in ["BS", "IS", "CF"]:
            c.drawString(40, y, st)
            y -= 18
            for it in statements.get(st, [])[:200]:
                c.drawString(50, y, f"{it.get('code')} {it.get('name')}: {it.get('amount')}")
                y -= 14
                if y < 60:
                    c.showPage()
                    y = h - 40
                    c.setFont("Helvetica", 10)
            y -= 10
        c.showPage()
        c.save()
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report-{body.snapshot_id}.pdf"},
        )

    raise HTTPException(status_code=400, detail="不支持的导出格式")


