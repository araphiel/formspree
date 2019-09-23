"""old 'gold' should be in the enum.

Revision ID: faa131da2b7b
Revises: 6a84a8877ef5
Create Date: 2018-10-23 20:39:17.116790

"""

# revision identifiers, used by Alembic.
revision = "faa131da2b7b"
down_revision = "6a84a8877ef5"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute("ALTER TYPE plans RENAME TO plans_previous")
    op.execute(
        "CREATE TYPE plans AS ENUM ('gold', 'v1_free', 'v1_gold', 'v1_gold_yearly', 'v1_platinum', 'v1_platinum_yearly')"
    )
    op.execute("ALTER TABLE users RENAME COLUMN plan TO plan_previous")
    op.execute("ALTER TABLE users ADD COLUMN plan plans NOT NULL DEFAULT 'v1_free'")
    op.execute("UPDATE users SET plan = plan_previous::text::plans")
    op.execute("ALTER TABLE users DROP COLUMN plan_previous")
    op.execute("DROP TYPE plans_previous")

    # old gold customers aren't 'v1_gold', they're simply 'gold', as that is the
    # name of their plan on stripe.
    op.execute("UPDATE users SET plan = 'gold' WHERE plan = 'v1_gold'")


def downgrade():
    pass
