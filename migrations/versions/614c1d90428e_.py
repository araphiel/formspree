"""empty message

Revision ID: 614c1d90428e
Revises: ee9b6bc06d8a
Create Date: 2016-03-17 15:44:36.274317

"""

# revision identifiers, used by Alembic.
revision = "614c1d90428e"
down_revision = "ee9b6bc06d8a"

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column("forms", sa.Column("disabled", sa.Boolean(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("forms", "disabled")
    ### end Alembic commands ###
