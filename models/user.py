from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models.base import AuditMixin

class Department(AuditMixin, db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    head_id = db.Column(db.Integer, db.ForeignKey('users.id', use_alter=True, name='fk_departments_head_id'), nullable=True)

    company = db.relationship('Company')
    head = db.relationship('User', foreign_keys=[head_id])
    members = db.relationship('User', backref='department', foreign_keys='User.department_id', lazy='dynamic')


class User(UserMixin, AuditMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')  # employee, manager, hr, admin
    is_active = db.Column(db.Boolean, default=True)
    avatar_color = db.Column(db.String(7), default='#0d9488')
    language_preference = db.Column(db.String(10), nullable=False, default='en')
    timezone_preference = db.Column(db.String(50), nullable=False, default='Asia/Jakarta')

    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    manager = db.relationship('User', remote_side=[id], foreign_keys=[manager_id], backref='subordinates')

    calendar_token = db.Column(db.String(64), unique=True, nullable=True)
    avatar_path = db.Column(db.String(255), nullable=True)

    leave_requests = db.relationship('LeaveRequest', foreign_keys='LeaveRequest.employee_id', backref='employee', lazy='dynamic')
    approved_requests = db.relationship('LeaveRequest', foreign_keys='LeaveRequest.approved_by', backref='approver', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_calendar_token(self):
        import secrets
        if not self.calendar_token:
            self.calendar_token = secrets.token_urlsafe(32)
            db.session.commit()
        return self.calendar_token

    def regenerate_calendar_token(self):
        import secrets
        self.calendar_token = secrets.token_urlsafe(32)
        db.session.commit()
        return self.calendar_token
