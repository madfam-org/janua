"""The entitlement source column maps to the PostgreSQL type migration 007 created.

Production (verified 2026-11-15) has the type `entitlement_source` with the lowercase values. With SQLAlchemy's
defaults the model looked for `entitlementsource` and sent the member names, so every grant failed with
`type "entitlementsource" does not exist` (503 on product invitations; zero rows ever written).
"""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import EntitlementSource, UserEntitlement

MIGRATION = Path(__file__).resolve().parents[3] / "alembic" / "versions" / "007_add_user_entitlements.py"


def _migration_values() -> tuple[str, ...]:
    spec = importlib.util.spec_from_file_location("migration_007", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module._ENTITLEMENT_SOURCE_VALUES


def test_type_name_and_values_match_migration_007():
    column_type = UserEntitlement.__table__.c.source.type
    assert column_type.name == "entitlement_source"
    assert tuple(column_type.enums) == _migration_values()


def test_postgres_ddl_and_binds_use_the_lowercase_values():
    ddl = str(CreateTable(UserEntitlement.__table__).compile(dialect=postgresql.dialect()))
    assert "source entitlement_source NOT NULL" in ddl
    assert "entitlementsource" not in ddl
    bound = sa.literal(EntitlementSource.ADMIN_GRANT, type_=UserEntitlement.__table__.c.source.type)
    sql = str(bound.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "'admin_grant'" in sql
    assert "ADMIN_GRANT" not in sql


def test_values_read_back_as_members():
    column_type = UserEntitlement.__table__.c.source.type
    process = column_type.result_processor(postgresql.dialect(), None)
    read = process("admin_grant") if process else column_type._object_value_for_elem("admin_grant")
    assert read is EntitlementSource.ADMIN_GRANT
