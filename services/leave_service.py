from datetime import date
from extensions import db
from models.leave import LeaveBalance, LeaveType, LeaveGrant

def ensure_user_balances(user_id, company_id, year=None):
    if not year:
        year = date.today().year
    leave_types = LeaveType.query.filter_by(company_id=company_id, is_active=True).all()
    balances = {b.leave_type_id: b for b in LeaveBalance.query.filter_by(employee_id=user_id, company_id=company_id, year=year).all()}
    
    for lt in leave_types:
        if lt.id not in balances:
            new_bal = LeaveBalance(
                company_id=company_id,
                employee_id=user_id,
                leave_type_id=lt.id,
                year=year,
                total_days=float(lt.days_per_year),
                used_days=0.0,
                pending_days=0.0
            )
            db.session.add(new_bal)
            balances[lt.id] = new_bal
    db.session.flush()
    return balances

def calculate_working_duration(start_date, end_date):
    return float((end_date - start_date).days + 1)
