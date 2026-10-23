"""Retrospective emergency changes: implement first, mandatory ECAB/CAB retrospective review before closing.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

TEXT = ["verbal_auth_notes", "retro_why_emergency", "retro_business_impact", "retro_actions_taken", "retro_timeline", "retro_outcome",
        "retro_root_cause", "retro_preventive_actions", "retro_info_request", "retro_decision_notes"]


def upgrade():
    with op.batch_alter_table('changes') as b:
        b.add_column(sa.Column('retrospective', sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column('verbal_auth_by', sa.String(200), nullable=True))
        b.add_column(sa.Column('retro_status', sa.String(30), nullable=True))
        for c in TEXT:
            b.add_column(sa.Column(c, sa.Text(), nullable=True))
        b.add_column(sa.Column('retro_submitted_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('retro_decided_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('retro_decided_by_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_changes_retro_decided_by', 'users', ['retro_decided_by_id'], ['id'])


def downgrade():
    with op.batch_alter_table('changes') as b:
        b.drop_constraint('fk_changes_retro_decided_by', type_='foreignkey')
        for c in ['retrospective', 'verbal_auth_by', 'retro_status', 'retro_submitted_at', 'retro_decided_at', 'retro_decided_by_id'] + TEXT:
            b.drop_column(c)
