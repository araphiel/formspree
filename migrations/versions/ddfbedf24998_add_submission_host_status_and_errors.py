"""add submission host, status and errors

Revision ID: ddfbedf24998
Revises: 2a00cc678dc9
Create Date: 2019-01-31 23:29:17.041560

"""

# revision identifiers, used by Alembic.
revision = "ddfbedf24998"
down_revision = "2a00cc678dc9"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.execute("CREATE TYPE submission_status AS ENUM ('processed', 'pending')")
    op.execute(
        "ALTER TABLE submissions ADD COLUMN status submission_status NOT NULL DEFAULT 'pending'"
    )
    op.execute("UPDATE submissions SET status = 'processed'")
    op.add_column("submissions", sa.Column("errors", postgresql.JSON(), nullable=True))
    op.add_column("submissions", sa.Column("host", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("submissions", "status")
    op.drop_column("submissions", "host")
    op.drop_column("submissions", "errors")
    op.execute("DROP TYPE submission_status")
