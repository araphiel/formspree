"""normalization function and indexes.

Revision ID: 4ad28343f1c4
Revises: 0d62aefafa13
Create Date: 2019-01-24 23:51:04.757810

"""

# revision identifiers, used by Alembic.
revision = "4ad28343f1c4"
down_revision = "0d62aefafa13"

from alembic import op
import sqlalchemy as sa

from formspree.forms.models import create_normalize_host, drop_normalize_host


def upgrade():
    op.create_index(op.f("ix_forms_email"), "forms", ["email"], unique=False)
    op.create_index(op.f("ix_forms_host"), "forms", ["host"], unique=False)
    op.execute(create_normalize_host)
    op.execute(
        "CREATE INDEX ix_forms_normalized_host ON forms ((normalize_host(host)))"
    )


def downgrade():
    op.drop_index(op.f("ix_forms_host"), table_name="forms")
    op.drop_index(op.f("ix_forms_email"), table_name="forms")
    op.execute("DROP INDEX ix_forms_normalized_host")
    op.execute(drop_normalize_host)
