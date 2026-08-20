from extensions import db
from models.base import AuditMixin

class PublicHoliday(AuditMixin, db.Model):
    __tablename__ = 'public_holidays'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    holiday_date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default='national')  # national, collective, company
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    company = db.relationship('Company')
    __table_args__ = (db.UniqueConstraint('company_id', 'holiday_date', name='uix_public_holiday_date'),)
