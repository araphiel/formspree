"""form name and created_at

Revision ID: db871b5702c8
Revises: 2ca30e4dc967
Create Date: 2018-11-21 15:52:36.070984

"""

# revision identifiers, used by Alembic.
revision = "db871b5702c8"
down_revision = "2ca30e4dc967"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("forms", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("forms", sa.Column("name", sa.String(), nullable=True))


def downgrade():
    op.drop_column("forms", "name")
    op.drop_column("forms", "created_at")
