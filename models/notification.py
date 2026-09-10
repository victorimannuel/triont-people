from extensions import db
from core.time_util import utcnow


class NotificationOutbox(db.Model):
    __tablename__ = 'notification_outbox'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    leave_request_id = db.Column(db.Integer, db.ForeignKey('leave_requests.id', ondelete='CASCADE'), nullable=False)
    event = db.Column(db.String(20), nullable=False)
    recipient_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending', server_default='pending')
    attempts = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    available_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    locked_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.Index('ix_notification_outbox_ready', 'status', 'available_at'),
        db.Index('ix_notification_outbox_company_request', 'company_id', 'leave_request_id'),
    )
