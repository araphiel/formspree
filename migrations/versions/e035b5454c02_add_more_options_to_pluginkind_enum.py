"""add more options to pluginkind enum

Revision ID: e035b5454c02
Revises: 2ca30e4dc967
Create Date: 2018-12-05 01:59:44.099814

"""

# revision identifiers, used by Alembic.
revision = "e035b5454c02"
down_revision = "508ea801e1c0"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("ALTER TYPE pluginkind RENAME TO pluginkind_previous")
    op.execute(
        "CREATE TYPE pluginkind AS ENUM ('google-sheets', 'webhook', 'trello', 'mailchimp', 'sms', 'google-calendar', 'slack', 'auto-response', 'telegram')"
    )
    op.execute("ALTER TABLE plugins RENAME COLUMN kind TO pluginkind_previous")
    op.execute("ALTER TABLE plugins ADD COLUMN kind pluginkind")
    op.execute("UPDATE plugins SET kind = pluginkind_previous::text::pluginkind")
    op.execute("ALTER TABLE plugins ALTER COLUMN kind SET NOT NULL")
    op.execute("ALTER TABLE plugins DROP COLUMN pluginkind_previous")
    op.execute("DROP TYPE pluginkind_previous")


def downgrade():
    op.execute(
        "DELETE FROM plugins WHERE kind != ANY('{google-sheets, webhook}'::pluginkind[])"
    )
    op.execute("ALTER TYPE pluginkind RENAME TO pluginkind_previous")
    op.execute("CREATE TYPE pluginkind AS ENUM ('')")
    op.execute("ALTER TABLE plugins RENAME COLUMN kind TO pluginkind_previous")
    op.execute("ALTER TABLE plugins ADD COLUMN kind pluginkind")
    op.execute("UPDATE plugins SET kind = pluginkind_previous::text::pluginkind")
    op.execute("ALTER TABLE plugins ALTER COLUMN kind SET NOT NULL")
    op.execute("ALTER TABLE plugins DROP COLUMN pluginkind_previous")
    op.execute("DROP TYPE pluginkind_previous")
