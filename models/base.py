from datetime import datetime
from flask import has_request_context
from flask_login import current_user
from sqlalchemy import event
from extensions import db
from core.time_util import utcnow

class AuditMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def created_at_formatted(self):
        if not self.created_at:
            return '-'
        from core.time_util import format_user_datetime
        return format_user_datetime(self.created_at, '%d/%m/%Y %H:%M')

    @property
    def updated_at_formatted(self):
        if not self.updated_at:
            return self.created_at_formatted
        from core.time_util import format_user_datetime
        return format_user_datetime(self.updated_at, '%d/%m/%Y %H:%M')

    @property
    def creator_name(self):
        if not self.created_by_id:
            return 'Sistem'
        from models.user import User
        u = db.session.get(User, self.created_by_id)
        return u.name if u else 'Sistem'

    @property
    def updater_name(self):
        if not self.updated_by_id:
            return self.creator_name
        from models.user import User
        u = db.session.get(User, self.updated_by_id)
        return u.name if u else self.creator_name

def _get_current_actor_id():
    if has_request_context():
        try:
            if current_user and current_user.is_authenticated:
                return current_user.id
        except Exception:
            return None
    return None

def init_audit_events():
    @event.listens_for(db.session, 'before_flush')
    def auto_populate_audit_fields(session, flush_context, instances):
        actor_id = _get_current_actor_id()
        now = utcnow()
        for obj in session.new:
            if isinstance(obj, AuditMixin):
                if getattr(obj, 'created_at', None) is None:
                    obj.created_at = now
                if getattr(obj, 'updated_at', None) is None:
                    obj.updated_at = now
                if actor_id is not None and getattr(obj, 'created_by_id', None) is None:
                    obj.created_by_id = actor_id
                if actor_id is not None and getattr(obj, 'updated_by_id', None) is None:
                    obj.updated_by_id = actor_id

        for obj in session.dirty:
            if isinstance(obj, AuditMixin):
                obj.updated_at = now
                if actor_id is not None:
                    obj.updated_by_id = actor_id
