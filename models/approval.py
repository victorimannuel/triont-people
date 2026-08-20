from extensions import db
from models.base import AuditMixin

class ApprovalConfig(AuditMixin, db.Model):
    __tablename__ = 'approval_configs'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=True)  # null = default for all types
    level = db.Column(db.Integer, nullable=False)  # 1, 2, 3...
    approver_role = db.Column(db.String(20), nullable=False)  # manager, hr, director

    company = db.relationship('Company')
    leave_type = db.relationship('LeaveType')
    __table_args__ = (db.UniqueConstraint('company_id', 'leave_type_id', 'level', name='uix_approval_level'),)
