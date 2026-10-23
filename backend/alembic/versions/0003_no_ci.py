"""No specific CI option on changes.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('changes') as b:
        b.add_column(sa.Column('no_ci', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column('no_ci_reason', sa.String(40), nullable=True))
        b.add_column(sa.Column('no_ci_reason_other', sa.Text(), nullable=True))
        b.add_column(sa.Column('no_ci_scope', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('changes') as b:
        for c in ('no_ci', 'no_ci_reason', 'no_ci_reason_other', 'no_ci_scope'):
            b.drop_column(c)
