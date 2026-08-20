from datetime import date
from extensions import db
from models.base import AuditMixin

class LeaveType(AuditMixin, db.Model):
    __tablename__ = 'leave_types'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    days_per_year = db.Column(db.Integer, nullable=False, default=0)
    color = db.Column(db.String(7), default='#6366F1')
    icon = db.Column(db.String(50), default='fa-calendar-alt')
    requires_approval = db.Column(db.Boolean, default=True)
    requires_attachment = db.Column(db.Boolean, default=False, nullable=False, server_default='false')
    attachment_label = db.Column(db.String(100), default='Surat Dokter / Bukti Pendukung', nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    balances = db.relationship('LeaveBalance', backref='leave_type', lazy='dynamic')
    requests = db.relationship('LeaveRequest', backref='leave_type', lazy='dynamic')


class LeaveRequest(AuditMixin, db.Model):
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    duration_days = db.Column(db.Float, nullable=False, default=0)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending')
    current_approval_level = db.Column(db.Integer, nullable=False, default=1)
    max_approval_level = db.Column(db.Integer, nullable=False, default=1)
    notes = db.Column(db.Text, nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    delegate_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    day_part = db.Column(db.String(20), nullable=False, default='full', server_default='full')
    attachment_path = db.Column(db.String(255), nullable=True)
    attachment_original_name = db.Column(db.String(255), nullable=True)
    is_archived = db.Column(db.Boolean, default=False, nullable=False, server_default='false')

    delegate = db.relationship('User', foreign_keys=[delegate_id])


class LeaveBalance(AuditMixin, db.Model):
    __tablename__ = 'leave_balances'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False, default=lambda: date.today().year)
    total_days = db.Column(db.Float, nullable=False, default=0)
    used_days = db.Column(db.Float, nullable=False, default=0)
    pending_days = db.Column(db.Float, nullable=False, default=0)

    employee = db.relationship('User', backref='balances', foreign_keys=[employee_id])
    __table_args__ = (db.UniqueConstraint('company_id', 'employee_id', 'leave_type_id', 'year', name='uix_company_employee_leave_year'),)


class LeaveGrant(AuditMixin, db.Model):
    __tablename__ = 'leave_grants'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id', ondelete='SET NULL'), nullable=True)
    year = db.Column(db.Integer, nullable=False)
    mode = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    old_total = db.Column(db.Float, nullable=False)
    new_total = db.Column(db.Float, nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    request_token = db.Column(db.String(100), nullable=False, unique=True)

    __table_args__ = (
        db.Index('ix_leave_grants_company_employee_year', 'company_id', 'employee_id', 'year'),
    )
