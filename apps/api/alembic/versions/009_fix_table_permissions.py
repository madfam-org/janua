"""fix table permissions for janua user

Revision ID: 009
Revises: 008
Create Date: 2025-12-05 10:00:00.000000

This migration grants full CRUD permissions (SELECT, INSERT, UPDATE, DELETE)
to the 'janua' database user for all public tables.

Critical Fix: Addresses InsufficientPrivilegeError when accessing organization_members,
webhook_endpoints, and other tables that were missing proper grants.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Grant full permissions on all public tables to janua user.

    This ensures the application database user has proper access to all tables.
    Uses GRANT ALL which includes SELECT, INSERT, UPDATE, DELETE, TRUNCATE,
    REFERENCES, and TRIGGER permissions.
    """
    # Grant permissions on all existing tables in public schema
    op.execute("""
        DO $$
        DECLARE
            tbl RECORD;
        BEGIN
            FOR tbl IN
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            LOOP
                EXECUTE format('GRANT ALL PRIVILEGES ON TABLE %I TO janua', tbl.table_name);
            END LOOP;
        END $$;
    """)

    # Grant permissions on all sequences (for auto-increment columns)
    op.execute("""
        DO $$
        DECLARE
            seq RECORD;
        BEGIN
            FOR seq IN
                SELECT sequence_name
                FROM information_schema.sequences
                WHERE sequence_schema = 'public'
            LOOP
                EXECUTE format('GRANT ALL PRIVILEGES ON SEQUENCE %I TO janua', seq.sequence_name);
            END LOOP;
        END $$;
    """)

    # Grant default privileges for future tables and sequences
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO janua;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO janua;")


def downgrade() -> None:
    """Revoke permissions from janua user.

    Note: This is destructive and will break the application.
    Only use if rolling back to a state where a different user is used.
    """
    # Revoke default privileges
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL PRIVILEGES ON TABLES FROM janua;")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL PRIVILEGES ON SEQUENCES FROM janua;")

    # Note: We don't revoke individual table grants as that would break the app
    # and the original state is unknown. If needed, this should be done manually.
