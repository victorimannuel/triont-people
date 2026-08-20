"""add delegate enabled to companies

Revision ID: d4e8b2f8c3a1
Revises: be25b0205cd1
Create Date: 2026-08-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e8b2f8c3a1'
down_revision = 'be25b0205cd1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('companies', sa.Column('delegate_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    if op.get_bind().dialect.name != 'sqlite':
        op.alter_column('companies', 'delegate_enabled', server_default=None)


def downgrade():
    op.drop_column('companies', 'delegate_enabled')
