from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.api.routers import accounts, ar_ap, attachments, auth, books, business, gl_drafts, imports, periods, reconcile, reports, scheduled
from app.core.config import settings
from app.infra.db.session import engine

# 说明：FastAPI 默认 Swagger UI 依赖外网 CDN，在部分网络环境会白屏。
# 我们禁用默认 docs，并提供一个“离线可用 docs 首页”（见 /docs）。
app = FastAPI(title="AccountingFlow API", version="0.1.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex_str,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.storage_dir, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.storage_dir), name="storage")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/health/db")
def health_db():
    # 用于确认：数据库连通 + 迁移已执行（至少能 select 1）
    with engine.connect() as conn:
        v = conn.execute(text("SELECT 1")).scalar_one()
    return {"ok": True, "db": True, "select_1": v}


@app.get("/health/schema")
def health_schema():
    # 用于确认：关键表已由 Alembic 迁移创建
    required = {
        "users",
        "commodities",
        "books",
        "accounts",
        "accounting_periods",
        "transaction_drafts",
        "transaction_draft_lines",
        "transactions",
        "splits",
        "account_balances",
        "audit_logs",
        "report_bases",
        "report_items",
        "report_mappings",
        "report_snapshots",
        "voucher_sequences",
        "parties",
        "attachments",
        "transaction_draft_revisions",
        "business_documents",
        "business_document_lines",
        "scheduled_transactions",
        "scheduled_runs",
        "reconcile_sessions",
        "reconcile_matches",
        "lots",
        "prices",
        "object_kv",
        "invoices",
        "invoice_lines",
        "payments",
        "payment_applications",
    }
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    missing = sorted(list(required - tables))
    return {"ok": True, "table_count": len(tables), "missing": missing}


@app.get("/docs", include_in_schema=False)
def docs_home():
    # 离线可用：不依赖任何外部 CDN
    html = f"""
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>AccountingFlow API Docs</title>
    <style>
      body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; }}
      code {{ background: #f2f4f7; padding: 2px 6px; border-radius: 6px; }}
      .card {{ border: 1px solid #eee; border-radius: 12px; padding: 14px 16px; max-width: 920px; }}
      a {{ color: #175cd3; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
      .muted {{ color: #666; font-size: 13px; }}
      ul {{ margin: 8px 0 0 18px; }}
    </style>
  </head>
  <body>
    <h2>AccountingFlow API 文档</h2>
    <div class="card">
      <p>你的网络环境可能无法加载默认 Swagger UI（外网 CDN），因此这里提供一个离线可用的文档入口。</p>
      <ul>
        <li><a href="{app.openapi_url}">OpenAPI JSON</a>（给 Postman/Apifox/Swagger Editor 用）</li>
        <li><a href="/health">健康检查</a></li>
        <li><a href="/health/db">数据库连通检查</a></li>
      </ul>
      <p class="muted">如需 Swagger UI 交互页面：建议使用本地工具（Apifox/Postman），或我后续再把 Swagger 静态资源打包进后端。</p>
      <p class="muted">当前 OpenAPI URL: <code>{app.openapi_url}</code></p>
    </div>
  </body>
</html>
"""
    return HTMLResponse(
        html,
        headers={
            # 防止浏览器/代理缓存旧的 Swagger HTML，导致你一直看到白屏
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


app.include_router(auth.router)
app.include_router(books.router)
app.include_router(periods.router)
app.include_router(accounts.router)
app.include_router(gl_drafts.router)
app.include_router(reports.router)
app.include_router(business.router)
app.include_router(ar_ap.router)
app.include_router(attachments.router)
app.include_router(imports.router)
app.include_router(scheduled.router)
app.include_router(reconcile.router)


