from datetime import timedelta

from sqlalchemy import or_

from core.time_util import utcnow
from extensions import db
from models.company import Company
from models.leave import LeaveRequest
from models.notification import NotificationOutbox
from services.notification_service import _dispatch_email, send_notification


def queue_notification(company, event, leave_request, recipient_scope='all', force=False):
    """Store one durable outbox row per recipient without contacting SMTP."""
    if not company or not leave_request:
        return []

    queued = []

    def collect(_company, recipient_email, subject, body):
        queued.append(NotificationOutbox(
            company_id=company.id,
            leave_request_id=leave_request.id,
            event=event,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
        ))
        return True

    send_notification(
        company,
        event,
        leave_request,
        dispatcher=collect,
        recipient_scope=recipient_scope,
        force=force,
    )
    db.session.add_all(queued)
    return queued


def _retry_at(attempts, now):
    delay_seconds = min(3600, 5 * (2 ** max(0, attempts - 1)))
    return now + timedelta(seconds=delay_seconds)


def process_next_notification():
    """Send one due email. Returns True when a row was processed."""
    now = utcnow()
    stale_lock = now - timedelta(minutes=5)
    item = NotificationOutbox.query.filter(
        or_(
            db.and_(NotificationOutbox.status.in_(('pending', 'retry')), NotificationOutbox.available_at <= now),
            db.and_(NotificationOutbox.status == 'processing', NotificationOutbox.locked_at <= stale_lock),
        )
    ).order_by(NotificationOutbox.available_at, NotificationOutbox.id).with_for_update(skip_locked=True).first()
    if not item:
        return False

    item.status = 'processing'
    item.locked_at = now
    item.attempts += 1
    db.session.commit()

    item_id = item.id
    company = db.session.get(Company, item.company_id)
    delivered = bool(company) and _dispatch_email(company, item.recipient_email, item.subject, item.body)
    item = db.session.get(NotificationOutbox, item_id)
    if delivered:
        item.status = 'sent'
        item.sent_at = utcnow()
        item.last_error = None
    else:
        item.status = 'retry'
        item.available_at = _retry_at(item.attempts, utcnow())
        item.last_error = 'SMTP delivery failed or is no longer configured.'
    item.locked_at = None
    db.session.commit()
    return True
