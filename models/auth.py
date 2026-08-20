from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models.base import AuditMixin

class PasswordReset(AuditMixin, db.Model):
    __tablename__ = 'password_resets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    otp_hash = db.Column(db.String(256), nullable=False)
    reset_token = db.Column(db.String(64), nullable=True, unique=True, index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    is_used = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('password_resets', lazy='dynamic', cascade='all, delete-orphan'))

    def set_otp(self, otp_code: str):
        self.otp_hash = generate_password_hash(otp_code)

    def check_otp(self, otp_code: str) -> bool:
        if not self.otp_hash or not otp_code:
            return False
        return check_password_hash(self.otp_hash, str(otp_code).strip())

    @property
    def is_expired(self) -> bool:
        now = datetime.utcnow()
        return now > self.expires_at

    @property
    def is_locked(self) -> bool:
        return self.attempts >= 5
