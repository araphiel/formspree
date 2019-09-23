"""email + normalization

Revision ID: 01a6f93d3537
Revises: c5b223503d70
Create Date: 2019-03-21 18:06:08.683947

"""

# revision identifiers, used by Alembic.
revision = "01a6f93d3537"
down_revision = "c5b223503d70"

from alembic import op

from formspree.forms.models import create_normalize_email, drop_normalize_email


def upgrade():
    op.execute(create_normalize_email)
    op.execute(
        "CREATE INDEX ix_forms_normalized_email ON forms ((normalize_email(email)))"
    )


def downgrade():
    op.execute("DROP INDEX ix_forms_normalized_email")
    op.execute(drop_normalize_email)
