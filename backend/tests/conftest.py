from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("未设置 DATABASE_URL，跳过集成测试")
    return url


def _reset_db(engine: Engine) -> None:
    dialect = engine.dialect.name
    if dialect == "mysql":
        # 清空当前数据库所有表（用于测试）
        with engine.begin() as conn:
            conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=0;"))
            tables = conn.execute(sa.text("SHOW TABLES;")).all()
            for (t,) in tables:
                conn.execute(sa.text(f"DROP TABLE IF EXISTS `{t}`;"))
            conn.execute(sa.text("SET FOREIGN_KEY_CHECKS=1;"))
        return

    if dialect.startswith("postgres"):
        with engine.begin() as conn:
            conn.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"))
        return

    raise RuntimeError(f"tests do not support dialect: {dialect}")


@pytest.fixture(scope="session")
def migrated_db(database_url: str):
    # 安全保护：避免误删生产库
    if "localhost" not in database_url and "127.0.0.1" not in database_url:
        pytest.skip("DATABASE_URL 不像是本地/容器测试库，跳过以避免误操作")

    engine = sa.create_engine(database_url, pool_pre_ping=True)
    _reset_db(engine)

    cfg = Config("alembic.ini")
    # env.py 会读取 DATABASE_URL，这里也同步写入，避免歧义
    os.environ["DATABASE_URL"] = database_url
    command.upgrade(cfg, "head")
    yield


