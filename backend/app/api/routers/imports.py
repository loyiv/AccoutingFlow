from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, require_roles
from app.api.schemas.imports import AccountImportCommitResponse, AccountImportPreviewResponse, AccountImportPreviewRow
from app.infra.db.models import Account, Book

router = APIRouter(prefix="/imports", tags=["imports"])


_BOOL_TRUE = {"1", "true", "t", "yes", "y", "是", "对", "启用", "允许"}
_BOOL_FALSE = {"0", "false", "f", "no", "n", "否", "错", "禁用", "不允许"}


def _parse_bool(v: Any, default: bool) -> bool:
    if v is None:
        return default
    s = str(v).strip().lower()
    if s == "":
        return default
    if s in _BOOL_TRUE:
        return True
    if s in _BOOL_FALSE:
        return False
    return default


def _detect_delimiter(sample: str) -> str:
    # 简单启发式：逗号/制表/分号
    c = sample.count(",")
    t = sample.count("\t")
    s = sample.count(";")
    if t >= c and t >= s and t > 0:
        return "\t"
    if s >= c and s > 0:
        return ";"
    return ","


def _read_csv(upload: UploadFile) -> str:
    raw = upload.file.read()
    # 优先 utf-8-sig（兼容 Excel BOM）
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _normalize_headers(h: str) -> str:
    return (h or "").strip().lower().replace(" ", "").replace("-", "_")


_HEADER_ALIASES = {
    "code": {"code", "account_code", "科目代码", "科目编码"},
    "name": {"name", "account_name", "科目名称"},
    "parent_code": {"parent_code", "parent", "父科目代码", "父级代码", "父科目"},
    "description": {"description", "desc", "备注", "描述"},
    "type": {"type", "account_type", "科目类型"},
    "allow_post": {"allow_post", "allowpost", "允许记账"},
    "is_active": {"is_active", "active", "启用", "是否启用"},
    "is_hidden": {"is_hidden", "hidden", "隐藏", "是否隐藏"},
    "is_placeholder": {"is_placeholder", "placeholder", "占位科目", "是否占位"},
}


def _pick_column(headers: list[str], key: str) -> str | None:
    aliases = _HEADER_ALIASES.get(key, set())
    norm = {h: _normalize_headers(h) for h in headers}
    for h, nh in norm.items():
        if h in aliases or nh in {a.lower().replace(" ", "").replace("-", "_") for a in aliases}:
            return h
    # 直接按 key 命中
    for h, nh in norm.items():
        if nh == key:
            return h
    return None


@router.post("/accounts/preview", response_model=AccountImportPreviewResponse)
async def preview_accounts_csv(
    book_id: str = Form(...),
    file: UploadFile = File(...),
    delimiter: str | None = Form(default=None),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> AccountImportPreviewResponse:
    if not db.query(Book).filter(Book.id == book_id).one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="账簿不存在")

    text = _read_csv(file)
    sample = "\n".join(text.splitlines()[:5])
    detected = delimiter if delimiter else _detect_delimiter(sample)

    reader = csv.DictReader(io.StringIO(text), delimiter=detected)
    headers = reader.fieldnames or []
    rows: list[AccountImportPreviewRow] = []
    warnings: list[str] = []
    if not headers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV 未检测到表头")

    code_col = _pick_column(headers, "code")
    name_col = _pick_column(headers, "name")
    if not code_col or not name_col:
        warnings.append("未识别到必填列：code/name（建议表头包含 code,name,parent_code,description,type,allow_post,is_active,is_hidden,is_placeholder）")

    for i, r in enumerate(reader, start=2):  # header is row 1
        if len(rows) >= 20:
            break
        rows.append(AccountImportPreviewRow(row_no=i, data=r))

    return AccountImportPreviewResponse(book_id=book_id, detected_delimiter=detected, headers=headers, rows=rows, warnings=warnings)


@router.post("/accounts/commit", response_model=AccountImportCommitResponse)
async def commit_accounts_csv(
    book_id: str = Form(...),
    file: UploadFile = File(...),
    delimiter: str | None = Form(default=None),
    update_existing: bool = Form(default=True),
    db: Session = Depends(db_session),
    _u: CurrentUser = Depends(require_roles(["admin", "accountant"])),
) -> AccountImportCommitResponse:
    book = db.query(Book).filter(Book.id == book_id).one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="账簿不存在")

    text = _read_csv(file)
    sample = "\n".join(text.splitlines()[:5])
    detected = delimiter if delimiter else _detect_delimiter(sample)

    reader = csv.DictReader(io.StringIO(text), delimiter=detected)
    headers = reader.fieldnames or []
    if not headers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV 未检测到表头")

    col_code = _pick_column(headers, "code")
    col_name = _pick_column(headers, "name")
    col_parent_code = _pick_column(headers, "parent_code")
    col_desc = _pick_column(headers, "description")
    col_type = _pick_column(headers, "type")
    col_allow_post = _pick_column(headers, "allow_post")
    col_active = _pick_column(headers, "is_active")
    col_hidden = _pick_column(headers, "is_hidden")
    col_placeholder = _pick_column(headers, "is_placeholder")

    if not col_code or not col_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV 必须包含 code 与 name 列（可用中文表头：科目代码/科目名称）")

    # 先收集行数据
    items: list[dict[str, Any]] = []
    for r in reader:
        code = (r.get(col_code) or "").strip()
        name = (r.get(col_name) or "").strip()
        if not code or not name:
            continue
        parent_code = (r.get(col_parent_code) or "").strip() if col_parent_code else ""
        items.append(
            {
                "code": code,
                "name": name,
                "parent_code": parent_code,
                "description": (r.get(col_desc) or "").strip() if col_desc else "",
                "type": (r.get(col_type) or "").strip() if col_type else "",
                "allow_post": _parse_bool(r.get(col_allow_post), True) if col_allow_post else True,
                "is_active": _parse_bool(r.get(col_active), True) if col_active else True,
                "is_hidden": _parse_bool(r.get(col_hidden), False) if col_hidden else False,
                "is_placeholder": _parse_bool(r.get(col_placeholder), False) if col_placeholder else False,
            }
        )

    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV 没有可导入的有效行")

    # 现有科目映射
    existing = db.query(Account).filter(Account.book_id == book_id).all()
    by_code = {a.code: a for a in existing}

    # 根据 parent_code 做拓扑排序（允许父科目出现在文件后面）
    remaining = {it["code"]: it for it in items}
    ordered: list[dict[str, Any]] = []
    guard = 0
    while remaining and guard < 100000:
        guard += 1
        progressed = False
        for code in list(remaining.keys()):
            it = remaining[code]
            pc = it["parent_code"]
            if not pc:
                ordered.append(it)
                remaining.pop(code, None)
                progressed = True
                continue
            if pc in by_code or pc in {x["code"] for x in ordered}:
                ordered.append(it)
                remaining.pop(code, None)
                progressed = True
        if not progressed:
            break

    warnings: list[str] = []
    if remaining:
        missing_parents = sorted({remaining[c]["parent_code"] for c in remaining if remaining[c]["parent_code"] and remaining[c]["parent_code"] not in by_code})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"存在无法解析的父科目代码（请先导入父科目或修正 parent_code）：{missing_parents[:10]}",
        )

    created = 0
    updated = 0
    skipped = 0

    with db.begin():
        for it in ordered:
            pc = it["parent_code"]
            parent_id = None
            if pc:
                p = by_code.get(pc) or db.query(Account).filter(Account.book_id == book_id, Account.code == pc).one_or_none()
                if not p:
                    raise HTTPException(status_code=400, detail=f"父科目不存在：{pc}")
                parent_id = p.id

            # placeholder 强制不允许记账
            allow_post = bool(it["allow_post"]) and (not bool(it["is_placeholder"]))
            acc_type = it["type"] or "ASSET"

            if it["code"] in by_code:
                if not update_existing:
                    skipped += 1
                    continue
                a = by_code[it["code"]]
                a.parent_id = parent_id
                a.name = it["name"]
                a.description = it["description"]
                a.type = acc_type
                a.allow_post = allow_post
                a.is_active = bool(it["is_active"])
                a.is_hidden = bool(it["is_hidden"])
                a.is_placeholder = bool(it["is_placeholder"])
                if a.is_placeholder:
                    a.allow_post = False
                updated += 1
            else:
                a = Account(
                    book_id=book_id,
                    parent_id=parent_id,
                    code=it["code"],
                    name=it["name"],
                    description=it["description"],
                    type=acc_type,
                    commodity_id=str(book.base_currency_id),
                    allow_post=allow_post,
                    is_active=bool(it["is_active"]),
                    is_hidden=bool(it["is_hidden"]),
                    is_placeholder=bool(it["is_placeholder"]),
                )
                if a.is_placeholder:
                    a.allow_post = False
                db.add(a)
                db.flush()
                by_code[a.code] = a
                created += 1

    return AccountImportCommitResponse(book_id=book_id, created=created, updated=updated, skipped=skipped, warnings=warnings)


