"""subscriptions (webhooks)

Revision ID: b5045b9d72ee
Revises: 96ae90768698
Create Date: 2018-10-25 13:28:04.486156

"""

# revision identifiers, used by Alembic.
revision = "b5045b9d72ee"
down_revision = "96ae90768698"

from alembic import op
import sqlalchemy as sa


def upgrade():
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


def downgrade():
    op.drop_table("subscriptions")
