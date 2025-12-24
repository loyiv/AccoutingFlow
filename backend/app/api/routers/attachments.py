from __future__ import annotations

import os
import re
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, get_current_user
from app.api.schemas.attachments import AttachmentOut
from app.core.config import settings
from app.infra.db.models import Attachment

router = APIRouter(prefix="/attachments", tags=["attachments"])


_FILENAME_SAFE = re.compile(r"[^a-zA-Z0-9._\-\u4e00-\u9fff]+")


def _safe_filename(name: str) -> str:
    name = name.strip().replace("\\", "_").replace("/", "_")
    name = _FILENAME_SAFE.sub("_", name)
    return name[:180] or "file"


@router.post("/upload", response_model=AttachmentOut)
async def upload(
    file: UploadFile = File(...),
    owner_type: str = "unlinked",
    owner_id: str | None = None,
    db: Session = Depends(db_session),
    u: CurrentUser = Depends(get_current_user),
) -> AttachmentOut:
    # 存储到本地 ./storage（后续可替换为对象存储）
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少文件名")
    safe = _safe_filename(file.filename)
    day = datetime.utcnow().strftime("%Y%m%d")
    subdir = os.path.join("uploads", day)
    abs_dir = os.path.join(settings.storage_dir, subdir)
    os.makedirs(abs_dir, exist_ok=True)

    # 避免覆盖：用时间戳+pid
    stamp = datetime.utcnow().strftime("%H%M%S%f")
    rel_path = os.path.join(subdir, f"{stamp}_{safe}")
    abs_path = os.path.join(settings.storage_dir, rel_path)
    rel_path_norm = rel_path.replace("\\", "/")

    data = await file.read()
    with open(abs_path, "wb") as f:
        f.write(data)

    with db.begin():
        row = Attachment(
            owner_type=owner_type or "unlinked",
            owner_id=owner_id,
            filename=file.filename,
            content_type=file.content_type or "",
            size_bytes=len(data),
            storage_path=rel_path_norm,
            url=f"/storage/{rel_path_norm}",
            uploaded_by=u.id,
            uploaded_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
        return AttachmentOut(
            id=str(row.id),
            owner_type=row.owner_type,
            owner_id=str(row.owner_id) if row.owner_id else None,
            filename=row.filename,
            content_type=row.content_type,
            size_bytes=int(row.size_bytes),
            url=row.url,
            uploaded_at=row.uploaded_at.isoformat(),
        )


