"""add leave grants ledger

Revision ID: f1a2b3c4d5e6
Revises: d4e8b2f8c3a1
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa


revision = 'f1a2b3c4d5e6'
down_revision = 'd4e8b2f8c3a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'leave_grants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=True),
        sa.Column('leave_type_id', sa.Integer(), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('old_total', sa.Float(), nullable=False),
        sa.Column('new_total', sa.Float(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('request_token', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['leave_type_id'], ['leave_types.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_token'),
    )
    op.create_index(
        'ix_leave_grants_company_employee_year',
        'leave_grants',
        ['company_id', 'employee_id', 'year'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_leave_grants_company_employee_year', table_name='leave_grants')
    op.drop_table('leave_grants')
