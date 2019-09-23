"""allow null fields on template

Revision ID: 0d62aefafa13
Revises: e035b5454c02
Create Date: 2019-01-08 22:09:25.635683

"""

# revision identifiers, used by Alembic.
revision = '0d62aefafa13'
down_revision = 'e035b5454c02'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('email_templates', 'body',
               existing_type=sa.TEXT(),
               nullable=True)
    op.alter_column('email_templates', 'from_name',
               existing_type=sa.TEXT(),
               nullable=True)
    op.alter_column('email_templates', 'style',
               existing_type=sa.TEXT(),
               nullable=True)
    op.alter_column('email_templates', 'subject',
               existing_type=sa.TEXT(),
               nullable=True)
    op.create_unique_constraint('one_plugin_of_each_kind', 'plugins', ['form_id', 'kind'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('one_plugin_of_each_kind', 'plugins', type_='unique')
    op.alter_column('email_templates', 'subject',
               existing_type=sa.TEXT(),
               nullable=False)
    op.alter_column('email_templates', 'style',
               existing_type=sa.TEXT(),
               nullable=False)
    op.alter_column('email_templates', 'from_name',
               existing_type=sa.TEXT(),
               nullable=False)
    op.alter_column('email_templates', 'body',
               existing_type=sa.TEXT(),
               nullable=False)
    # ### end Alembic commands ###
