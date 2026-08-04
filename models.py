from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime

db = SQLAlchemy()


class Company(db.Model):
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
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='company', foreign_keys='User.company_id', lazy='dynamic')
    leave_types = db.relationship('LeaveType', backref='company', foreign_keys='LeaveType.company_id', lazy='dynamic')


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    head_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company')
    head = db.relationship('User', foreign_keys=[head_id])
    members = db.relationship('User', backref='department', foreign_keys='User.department_id', lazy='dynamic')


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')  # employee, manager, hr, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar_color = db.Column(db.String(7), default='#0d9488')

    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    manager = db.relationship('User', remote_side=[id], backref='subordinates')

    leave_requests = db.relationship('LeaveRequest', foreign_keys='LeaveRequest.employee_id', backref='employee', lazy='dynamic')
    approved_requests = db.relationship('LeaveRequest', foreign_keys='LeaveRequest.approved_by', backref='approver', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LeaveType(db.Model):
    __tablename__ = 'leave_types'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    days_per_year = db.Column(db.Integer, nullable=False, default=0)
    color = db.Column(db.String(7), default='#6366F1')
    icon = db.Column(db.String(50), default='fa-calendar-alt')
    requires_approval = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)

    balances = db.relationship('LeaveBalance', backref='leave_type', lazy='dynamic')
    requests = db.relationship('LeaveRequest', backref='leave_type', lazy='dynamic')


class ApprovalConfig(db.Model):
    __tablename__ = 'approval_configs'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=True)  # null = default for all types
    level = db.Column(db.Integer, nullable=False)  # 1, 2, 3...
    approver_role = db.Column(db.String(20), nullable=False)  # manager, hr, director

    company = db.relationship('Company')
    leave_type = db.relationship('LeaveType')
    __table_args__ = (db.UniqueConstraint('company_id', 'leave_type_id', 'level', name='uix_approval_level'),)


class LeaveRequest(db.Model):
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    delegate = db.relationship('User', foreign_keys=[delegate_id])


class LeaveBalance(db.Model):
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