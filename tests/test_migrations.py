from __future__ import annotations

import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint

from app.db import Base

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
INITIAL_REVISION = "20261108_0001"
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost/test"

_CREATE_TABLE = re.compile(r"CREATE TABLE (\w+) \((.*?)\n\);", re.DOTALL)
_CONSTRAINT = re.compile(r"CONSTRAINT (\w+)")


@pytest.fixture
def alembic_config(monkeypatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return config


def _render_sql(config: Config, direction: str, capsys) -> str:
    if direction == "upgrade":
        command.upgrade(config, "head", sql=True)
    else:
        command.downgrade(config, "head:base", sql=True)
    return capsys.readouterr().out


def _created_tables(sql: str) -> dict[str, str]:
    return {
        table: body
        for table, body in _CREATE_TABLE.findall(sql)
        if table != "alembic_version"
    }


def _column_names(table_sql: str) -> set[str]:
    columns = set()
    for line in table_sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("CONSTRAINT"):
            continue
        columns.add(stripped.split()[0].rstrip(","))
    return columns


def _check_constraint_names(metadata) -> set[str]:
    return {
        constraint.name
        for table in metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _migration_check_constraint_names(sql: str) -> set[str]:
    return {
        name
        for name in _CONSTRAINT.findall(sql)
        if name.startswith("ck_")
    }


def test_alembic_ini_has_no_database_url() -> None:
    content = ALEMBIC_INI.read_text(encoding="utf-8")

    assert "sqlalchemy.url =\n" in content
    assert TEST_DATABASE_URL not in content


def test_revision_has_single_base_and_head(alembic_config: Config) -> None:
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(alembic_config)

    assert script.get_heads() == [INITIAL_REVISION]
    assert script.get_bases() == [INITIAL_REVISION]

    revision = script.get_revision(INITIAL_REVISION)
    assert revision is not None
    assert revision.down_revision is None


def test_upgrade_creates_all_model_tables(alembic_config: Config, capsys) -> None:
    sql = _render_sql(alembic_config, "upgrade", capsys)
    tables = _created_tables(sql)

    assert set(tables) == set(Base.metadata.tables)

    for table_name, table_sql in tables.items():
        expected = set(Base.metadata.tables[table_name].columns.keys())
        assert _column_names(table_sql) == expected


def test_upgrade_creates_model_check_constraints(
    alembic_config: Config,
    capsys,
) -> None:
    sql = _render_sql(alembic_config, "upgrade", capsys)

    assert _migration_check_constraint_names(sql) == _check_constraint_names(
        Base.metadata
    )
    assert "ck_ck_" not in sql


def test_upgrade_adds_cyclic_foreign_key_last(
    alembic_config: Config,
    capsys,
) -> None:
    sql = _render_sql(alembic_config, "upgrade", capsys)

    constraint = "ALTER TABLE users ADD CONSTRAINT fk_users_cir_id_circles"
    assert constraint in sql
    assert sql.index(constraint) > sql.index("CREATE TABLE circles (")
    assert sql.index(constraint) > sql.index("CREATE TABLE settings (")


def test_downgrade_removes_foreign_key_before_tables(
    alembic_config: Config,
    capsys,
) -> None:
    sql = _render_sql(alembic_config, "downgrade", capsys)

    drop_constraint = "ALTER TABLE users DROP CONSTRAINT fk_users_cir_id_circles"
    assert drop_constraint in sql
    assert sql.index(drop_constraint) < sql.index("DROP TABLE circles;")

    order = [
        sql.index("DROP TABLE settings;"),
        sql.index("DROP TABLE mailing;"),
        sql.index("DROP TABLE circles;"),
        sql.index("DROP TABLE users;"),
    ]
    assert order == sorted(order)
