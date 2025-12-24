from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.application.engine.accounts import build_account_children_map, collect_descendants, list_accounts
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


def _params_hash(params: dict) -> str:
    body = json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


_CREDIT_TYPES = {"LIABILITY", "EQUITY", "INCOME", "AP"}
_CASH_TYPES = {"CASH", "BANK"}


@dataclass(frozen=True)
class GenerateResult:
    snapshot_id: str


def generate_reports(db: Session, book_id: str, period_id: str, basis_code: str, actor_user_id: str | None) -> GenerateResult:
    # 该函数包含写快照，统一用一个事务（避免“session 已隐式开启事务”导致 begin 嵌套错误）
    with db.begin():
        period = (
            db.query(AccountingPeriod)
            .filter(AccountingPeriod.id == period_id, AccountingPeriod.book_id == book_id)
            .one()
        )
        basis = db.query(ReportBasis).filter(ReportBasis.code == basis_code).one_or_none()
        if not basis:
            raise ValueError(f"报表口径不存在：{basis_code}")

        params = {"book_id": book_id, "period_id": period_id, "basis_code": basis_code}
        ph = _params_hash(params)

        existing = (
            db.query(ReportSnapshot)
            .filter(ReportSnapshot.book_id == book_id, ReportSnapshot.params_hash == ph)
            .one_or_none()
        )
        if existing and not existing.is_stale:
            return GenerateResult(snapshot_id=str(existing.id))

        # 计算：按“科目→报表项目映射”
        accounts = list_accounts(db, book_id)
        children_map = build_account_children_map(accounts)

        items = db.query(ReportItem).order_by(ReportItem.statement_type.asc(), ReportItem.display_order.asc()).all()
        item_by_id = {str(i.id): i for i in items}

        mappings = db.query(ReportMapping).filter(ReportMapping.basis_id == basis.id).all()
        if not mappings:
            raise ValueError("该口径未配置任何科目映射，无法生成报表")

        # 1) 展开映射 account set（处理 include_children）
        expanded: dict[tuple[str, str], set[str]] = {}  # (statement_type, item_code) -> set(account_id)
        overlap_errors: list[dict] = []
        per_statement_used: dict[str, set[str]] = {"BS": set(), "IS": set(), "CF": set()}

        for m in mappings:
            item = item_by_id.get(str(m.item_id))
            if not item:
                continue
            stmt = item.statement_type
            key = (stmt, item.code)
            rid = str(m.account_id)
            acc_set: set[str] = collect_descendants(children_map, rid) if m.include_children else {rid}

            overlap = per_statement_used[stmt] & acc_set
            if overlap:
                overlap_errors.append(
                    {
                        "statement_type": stmt,
                        "item_code": item.code,
                        "overlap_account_ids": sorted(list(overlap))[:50],
                        "message": "同一科目在同一口径下被重复计入（违反映射规则）",
                    }
                )
            per_statement_used[stmt] |= acc_set
            expanded[key] = expanded.get(key, set()) | acc_set

        if overlap_errors:
            raise ValueError("映射规则冲突：存在重复计入科目，无法生成报表")

        all_accounts: set[str] = set()
        for s in expanded.values():
            all_accounts |= s
        if not all_accounts:
            raise ValueError("映射展开后无任何科目，无法生成报表")

        # period key，用于“截至本期”的累计
        pkey = int(period.year) * 100 + int(period.month)

        acc_tbl = Account.__table__
        sp_tbl = Split.__table__
        tx_tbl = Transaction.__table__
        pe_tbl = AccountingPeriod.__table__

        norm_value = sa.case(
            (acc_tbl.c.type.in_(list(_CREDIT_TYPES)), -sp_tbl.c.value),
            else_=sp_tbl.c.value,
        )

        q_balance = (
            sa.select(sp_tbl.c.account_id, sa.func.coalesce(sa.func.sum(norm_value), 0).label("amt"))
            .select_from(
                sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id)
                .join(pe_tbl, tx_tbl.c.period_id == pe_tbl.c.id)
                .join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id)
            )
            .where(acc_tbl.c.book_id == sa.bindparam("book_id"))
            .where(sp_tbl.c.account_id.in_(sa.bindparam("acc_ids", expanding=True)))
            .where((pe_tbl.c.year * 100 + pe_tbl.c.month) <= sa.bindparam("pkey"))
            .group_by(sp_tbl.c.account_id)
        )

        q_activity = (
            sa.select(sp_tbl.c.account_id, sa.func.coalesce(sa.func.sum(norm_value), 0).label("amt"))
            .select_from(sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id).join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id))
            .where(acc_tbl.c.book_id == sa.bindparam("book_id"))
            .where(tx_tbl.c.period_id == sa.bindparam("period_id"))
            .where(sp_tbl.c.account_id.in_(sa.bindparam("acc_ids", expanding=True)))
            .group_by(sp_tbl.c.account_id)
        )

        balance_rows = db.execute(q_balance, {"book_id": book_id, "pkey": pkey, "acc_ids": list(all_accounts)}).all()
        activity_rows = db.execute(q_activity, {"book_id": book_id, "period_id": period_id, "acc_ids": list(all_accounts)}).all()
        balance_by_acc = {str(r[0]): _decimal(r[1]) for r in balance_rows}
        activity_by_acc = {str(r[0]): _decimal(r[1]) for r in activity_rows}

        def item_amount(stmt: str, item_code: str) -> Decimal:
            accs = expanded.get((stmt, item_code), set())
            item = next((i for i in items if i.statement_type == stmt and i.code == item_code), None)
            if not item:
                return Decimal("0")
            src = balance_by_acc if item.calc_mode == "BALANCE" else activity_by_acc
            return sum((src.get(aid, Decimal("0")) for aid in accs), start=Decimal("0"))

        out: dict[str, list[dict]] = {"BS": [], "IS": [], "CF": []}
        for it in items:
            amt = item_amount(it.statement_type, it.code)
            out[it.statement_type].append({"code": it.code, "name": it.name, "amount": str(amt)})

        # 4) 公式项（避免“同一科目重复计入”）：总计由明细项计算，不做重复映射
        def _set_or_append(stmt: str, code: str, name: str, amt: Decimal):
            for x in out[stmt]:
                if x["code"] == code:
                    x["name"] = name
                    x["amount"] = str(amt)
                    return
            out[stmt].append({"code": code, "name": name, "amount": str(amt)})

        bs_assets = item_amount("BS", "BS_ASSETS")
        bs_liab = item_amount("BS", "BS_LIABILITIES")
        bs_equity = item_amount("BS", "BS_EQUITY")
        bs_assets_total = bs_assets
        bs_le_total = bs_liab + bs_equity

        _set_or_append("BS", "BS_ASSETS_TOTAL", "资产合计", bs_assets_total)
        _set_or_append("BS", "BS_LIAB_EQUITY_TOTAL", "负债与所有者权益合计", bs_le_total)

        is_rev = item_amount("IS", "IS_REVENUE")
        is_exp = item_amount("IS", "IS_EXPENSE")
        is_profit = is_rev - is_exp
        _set_or_append("IS", "IS_NET_PROFIT", "净利润", is_profit)

        tol = Decimal("0.5")
        bs_ok = abs(bs_assets_total - bs_le_total) <= tol

        cash_ids = [
            str(r[0])
            for r in db.query(Account.id).filter(Account.book_id == book_id, Account.type.in_(list(_CASH_TYPES))).all()
        ]
        cash_begin = Decimal("0")
        cash_end = Decimal("0")
        cash_net = Decimal("0")
        if cash_ids:
            q_cash_end = (
                sa.select(sa.func.coalesce(sa.func.sum(norm_value), 0))
                .select_from(
                    sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id)
                    .join(pe_tbl, tx_tbl.c.period_id == pe_tbl.c.id)
                    .join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id)
                )
                .where(acc_tbl.c.book_id == book_id)
                .where(sp_tbl.c.account_id.in_(cash_ids))
                .where((pe_tbl.c.year * 100 + pe_tbl.c.month) <= pkey)
            )
            q_cash_begin = (
                sa.select(sa.func.coalesce(sa.func.sum(norm_value), 0))
                .select_from(
                    sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id)
                    .join(pe_tbl, tx_tbl.c.period_id == pe_tbl.c.id)
                    .join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id)
                )
                .where(acc_tbl.c.book_id == book_id)
                .where(sp_tbl.c.account_id.in_(cash_ids))
                .where((pe_tbl.c.year * 100 + pe_tbl.c.month) < pkey)
            )
            q_cash_net = (
                sa.select(sa.func.coalesce(sa.func.sum(norm_value), 0))
                .select_from(sp_tbl.join(tx_tbl, sp_tbl.c.txn_id == tx_tbl.c.id).join(acc_tbl, sp_tbl.c.account_id == acc_tbl.c.id))
                .where(acc_tbl.c.book_id == book_id)
                .where(tx_tbl.c.period_id == period_id)
                .where(sp_tbl.c.account_id.in_(cash_ids))
            )
            cash_end = _decimal(db.execute(q_cash_end).scalar_one())
            cash_begin = _decimal(db.execute(q_cash_begin).scalar_one())
            cash_net = _decimal(db.execute(q_cash_net).scalar_one())

        for x in out["CF"]:
            if x["code"] == "CF_BEGIN_CASH":
                x["amount"] = str(cash_begin)
            if x["code"] == "CF_NET_CASH":
                x["amount"] = str(cash_net)
            if x["code"] == "CF_END_CASH":
                x["amount"] = str(cash_end)

        log = {
            "mapping": {"basis_code": basis_code, "expanded_account_count": len(all_accounts)},
            "checks": {
                "BS_BALANCE_OK": bs_ok,
                "BS_ASSETS_TOTAL": str(bs_assets_total),
                "BS_LIAB_EQUITY_TOTAL": str(bs_le_total),
                "tolerance": str(tol),
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
        result = {"statements": out, "checks": log["checks"], "params": params}

        if existing:
            existing.period_id = period_id
            existing.basis_id = basis.id
            existing.generated_by = actor_user_id if actor_user_id else None
            existing.generated_at = datetime.utcnow()
            existing.is_stale = False
            existing.result_json = result
            existing.log_json = log
            db.flush()
            sid = str(existing.id)
        else:
            snap = ReportSnapshot(
                book_id=book_id,
                period_id=period_id,
                basis_id=basis.id,
                params_hash=ph,
                generated_by=actor_user_id if actor_user_id else None,
                generated_at=datetime.utcnow(),
                is_stale=False,
                result_json=result,
                log_json=log,
            )
            db.add(snap)
            db.flush()
            sid = str(snap.id)

    return GenerateResult(snapshot_id=sid)


