"""White-label branding: the theme columns the branding API stores.

`routers/v1/white_label.py` answers GET/PUT/POST /white-label/branding with a
contract (nauta#331) wider than white_label_configurations as 000_init created
it. The fields whose meaning an existing column already carries map onto it
with no DDL (company_name -> brand_name, company_logo_url -> logo_url,
company_favicon_url -> favicon_url, is_enabled -> is_active; see
BRANDING_FIELD_COLUMNS). This revision adds only the genuinely new data: ten
nullable columns, no default, no backfill. NULL means "not chosen" and the API
answers it as null.

Additive and catalog-only on PostgreSQL (nullable, no default: no table
rewrite). Re-entrant like 012-019 (checks `inspect()` before every change),
because production applies DDL by hand. The owner-ready SQL for production is
docs/ops/sql/020_white_label_branding_columns.sql and must stay object-for-object
identical to this revision (tests/unit/test_white_label_branding_migration.py).

Downgrade drops the ten columns (and the values stored in them).
"""

import sqlalchemy as sa

from alembic import op

revision = "020_white_label_branding_columns"
down_revision = "019_email_first_party_engagement"
branch_labels = None
depends_on = None

TABLE = "white_label_configurations"

# (column, type), in the order the owner SQL adds them.
COLUMNS = (
    ("branding_level", sa.String(20)),
    ("theme_mode", sa.String(10)),
    ("logo_dark_url", sa.String(500)),
    ("website_url", sa.String(500)),
    ("accent_color", sa.String(7)),
    ("background_color", sa.String(7)),
    ("surface_color", sa.String(7)),
    ("text_color", sa.String(7)),
    ("font_family", sa.String(255)),
    ("border_radius", sa.String(20)),
)


def upgrade():
    present = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}
    for name, type_ in COLUMNS:
        if name not in present:
            op.add_column(TABLE, sa.Column(name, type_, nullable=True))


def downgrade():
    present = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}
    for name, _type in reversed(COLUMNS):
        if name in present:
            op.drop_column(TABLE, name)
