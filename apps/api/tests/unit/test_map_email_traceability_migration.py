"""The additive migration replays without deleting existing evidence."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_is_additive_reentrant_and_retains_evidence():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/021_map_email_traceability.py"
    spec = importlib.util.spec_from_file_location("map_mail_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        metadata = sa.MetaData()
        sa.Table("magic_links", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
        sa.Table("password_resets", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
        sa.Table("email_events", metadata, sa.Column("id", sa.Integer(), primary_key=True))
        sa.Table("payment_mail_dispatches", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
        metadata.create_all(connection)
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        columns = {column["name"] for column in sa.inspect(connection).get_columns("email_events")}
        assert {
            "mail_audit_id",
            "map_audit_id",
            "message_kind",
            "trigger_kind",
            "command_id",
        } <= columns
        connection.execute(
            sa.text(
                "INSERT INTO email_send_audits(id,source_app,message_kind,trigger_kind,provenance,state,created_at) VALUES(:id,'crea-map','magic_login','map_login_request','registered_map_login','pending',CURRENT_TIMESTAMP)"
            ),
            {"id": "00000000000040008000000000000001"},
        )
        migration.downgrade()
        assert connection.scalar(sa.text("SELECT count(*) FROM email_send_audits")) == 1
    engine.dispose()
