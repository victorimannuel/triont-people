"""add notification outbox

Revision ID: e9f0a1b2c3d4
Revises: c7d8e9f0a1b2
Create Date: 2026-09-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'e9f0a1b2c3d4'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notification_outbox',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('leave_request_id', sa.Integer(), sa.ForeignKey('leave_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event', sa.String(length=20), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('available_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_notification_outbox_ready', 'notification_outbox', ['status', 'available_at'])
    op.create_index('ix_notification_outbox_company_request', 'notification_outbox', ['company_id', 'leave_request_id'])


def downgrade():
    op.drop_index('ix_notification_outbox_company_request', table_name='notification_outbox')
    op.drop_index('ix_notification_outbox_ready', table_name='notification_outbox')
    op.drop_table('notification_outbox')
