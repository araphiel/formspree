"""indexes on crucial columns.

Revision ID: fe0f82fd48c6
Revises: b5045b9d72ee
Create Date: 2018-11-03 13:52:06.997181

"""

# revision identifiers, used by Alembic.
revision = "fe0f82fd48c6"
down_revision = "b5045b9d72ee"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index(op.f("ix_emails_owner_id"), "emails", ["owner_id"], unique=False)
    op.create_index(op.f("ix_forms_owner_id"), "forms", ["owner_id"], unique=False)
    op.create_index(
        op.f("ix_submissions_form_id"), "submissions", ["form_id"], unique=False
    )
    op.create_index(
        op.f("ix_subscriptions_form_id"), "subscriptions", ["form_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_subscriptions_form_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_submissions_form_id"), table_name="submissions")
    op.drop_index(op.f("ix_forms_owner_id"), table_name="forms")
    op.drop_index(op.f("ix_emails_owner_id"), table_name="emails")
