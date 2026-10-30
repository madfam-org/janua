"""Organization authentication policy and session assurance (additive, re-entrant).

Upgrade the schema before rolling out the application. Legacy sessions receive
empty methods and no assurance timestamps; a refresh cannot invent MFA proof.
Source rollback retains the additive schema/journal, and downgrade is refused
while any organization still requires MFA.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "020_org_authentication_policy"
down_revision = "019_email_first_party_engagement"
branch_labels = None
depends_on = None

POLICIES = "organization_authentication_policies"
CHANGES = "organization_authentication_policy_changes"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    columns = {column["name"] for column in inspector.get_columns("sessions")}
    additions = [
        sa.Column(
            "authentication_methods",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("authenticated_at", sa.DateTime(), nullable=True),
        sa.Column("mfa_verified_at", sa.DateTime(), nullable=True),
    ]
    for column in additions:
        if column.name not in columns:
            op.add_column("sessions", column)
    if POLICIES not in tables:
        op.create_table(
            POLICIES,
            sa.Column(
                "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), primary_key=True
            ),
            sa.Column("mfa_mode", sa.String(16), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint(
                "mfa_mode IN ('optional', 'required')", name="ck_org_auth_policy_mfa_mode"
            ),
            sa.CheckConstraint("version >= 1", name="ck_org_auth_policy_version"),
        )
    if CHANGES not in tables:
        op.create_table(
            CHANGES,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False
            ),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("previous_mode", sa.String(16), nullable=False),
            sa.Column("mfa_mode", sa.String(16), nullable=False),
            sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("reason", sa.String(300), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "organization_id", "version", name="uq_org_auth_policy_change_version"
            ),
            sa.CheckConstraint(
                "mfa_mode IN ('optional', 'required')", name="ck_org_auth_change_mfa_mode"
            ),
            sa.CheckConstraint(
                "previous_mode IN ('optional', 'required')", name="ck_org_auth_change_previous_mode"
            ),
        )


def downgrade():
    bind = op.get_bind()
    if POLICIES in sa.inspect(bind).get_table_names():
        required = bind.execute(
            sa.text(
                "SELECT 1 FROM organization_authentication_policies WHERE mfa_mode = 'required' LIMIT 1"
            )
        ).first()
        if required:
            raise RuntimeError("Refuse downgrade while an organization requires MFA")
    # Retain additive columns, policies and audit history on an authorized
    # source rollback. Dropping the journal is not a routine rollback action.
