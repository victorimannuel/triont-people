"""add sort order to leave types

Revision ID: c7d8e9f0a1b2
Revises: b2c3d4e5f6a7
Create Date: 2026-08-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c7d8e9f0a1b2'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def _has_column(table_name, column_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col['name'] == column_name for col in inspector.get_columns(table_name))


def upgrade():
    if not _has_column('leave_types', 'sort_order'):
        with op.batch_alter_table('leave_types') as batch_op:
            batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
    op.execute('UPDATE leave_types SET sort_order = id WHERE sort_order IS NULL OR sort_order = 0')


def downgrade():
    if _has_column('leave_types', 'sort_order'):
        with op.batch_alter_table('leave_types') as batch_op:
            batch_op.drop_column('sort_order')
