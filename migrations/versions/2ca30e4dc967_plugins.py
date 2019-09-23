"""plugins

Revision ID: 2ca30e4dc967
Revises: fe0f82fd48c6
Create Date: 2018-11-18 00:27:11.355089

"""

# revision identifiers, used by Alembic.
revision = "2ca30e4dc967"
down_revision = "fe0f82fd48c6"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM

pluginkind = ENUM("google-sheets", "webhook", name="pluginkind", create_type=False)


def upgrade():
    pluginkind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "plugins",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("kind", pluginkind, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("form_id", sa.Integer(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=True),
        sa.Column("plugin_data", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("form_id", "kind", name="one_plugin_of_each_kind"),
    )
    op.create_index(op.f("ix_plugins_form_id"), "plugins", ["form_id"], unique=False)
    op.execute(
        """
INSERT INTO plugins (id, kind, form_id, plugin_data, enabled)
SELECT id, 'webhook', form_id, jsonb_build_object('target_url', target_url), true
  FROM subscriptions
    """
    )
    op.drop_table("subscriptions")


def downgrade():
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("target_url", sa.String(), nullable=False),
        sa.Column("form_id", sa.Integer(), nullable=False),
        sa.Column("api_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("form_id", "target_url", name="one_target_url_per_form"),
    )
    op.execute(
        """
INSERT INTO subscriptions (id, created_at, api_version, form_id, target_url)
SELECT id, now(), 0, form_id, plugin_data->>'target_url'
  FROM plugins
    """
    )

    op.drop_index(op.f("ix_plugins_form_id"), table_name="plugins")
    op.drop_table("plugins")
    op.execute("DROP TYPE pluginkind")
