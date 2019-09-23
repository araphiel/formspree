"""apikey column on forms.

Revision ID: 96ae90768698
Revises: faa131da2b7b
Create Date: 2018-10-12 12:34:16.983074

"""

# revision identifiers, used by Alembic.
revision = "96ae90768698"
down_revision = "faa131da2b7b"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("forms", sa.Column("apikey", sa.String(), nullable=True))


def downgrade():
    op.drop_column("forms", "apikey")
