"""empty message

Revision ID: f99d5e2ab036
Revises: 745fe4b160a3
Create Date: 2017-02-10 17:43:31.532821

"""

# revision identifiers, used by Alembic.
revision = "f99d5e2ab036"
down_revision = "745fe4b160a3"

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column("forms", sa.Column("uses_ajax", sa.Boolean(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("forms", "uses_ajax")
    ### end Alembic commands ###
