from extensions import db
from models.base import AuditMixin

class Company(AuditMixin, db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    primary_color = db.Column(db.String(7), default='#0d9488')
    notifications_enabled = db.Column(db.Boolean, default=False)
    smtp_host = db.Column(db.String(200), nullable=True)
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(200), nullable=True)
    smtp_password = db.Column(db.String(200), nullable=True)
    notify_on_approve = db.Column(db.Boolean, default=True)
    notify_on_reject = db.Column(db.Boolean, default=True)
    notify_on_submit = db.Column(db.Boolean, default=False)
    delegate_enabled = db.Column(db.Boolean, nullable=False, default=True)
    is_active = db.Column(db.Boolean, default=True)

    users = db.relationship('User', backref='company', foreign_keys='User.company_id', lazy='dynamic')
    leave_types = db.relationship('LeaveType', backref='company', foreign_keys='LeaveType.company_id', lazy='dynamic')
