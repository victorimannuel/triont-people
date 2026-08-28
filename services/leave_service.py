from datetime import date, timedelta
from extensions import db
from models.leave import LeaveBalance, LeaveType, LeaveGrant
from models.holiday import PublicHoliday
from services.leave_type_service import order_leave_type_query

def ensure_user_balances(user_id, company_id, year=None):
    if not year:
        year = date.today().year
    leave_types = order_leave_type_query(LeaveType.query.filter_by(company_id=company_id, is_active=True)).all()
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

def calculate_working_duration(start_date, end_date, company_id=None, day_part='full', exclude_weekends=True, exclude_holidays=True):
    """
    Calculates effective working leave duration in days.
    - If day_part is 'morning' or 'afternoon', returns 0.5.
    - If exclude_weekends is True, excludes Saturdays and Sundays.
    - If exclude_holidays is True and company_id is provided, excludes active company public holidays.
    """
    if day_part in ('morning', 'afternoon'):
        return 0.5

    if not start_date or not end_date or start_date > end_date:
        return 0.0

    holidays = set()
    if exclude_holidays and company_id:
        holiday_records = PublicHoliday.query.filter(
            PublicHoliday.company_id == company_id,
            PublicHoliday.is_active == True,
            PublicHoliday.holiday_date >= start_date,
            PublicHoliday.holiday_date <= end_date
        ).all()
        holidays = {h.holiday_date for h in holiday_records}

    curr = start_date
    working_days = 0.0
    while curr <= end_date:
        is_weekend = exclude_weekends and curr.weekday() in (5, 6)
        is_holiday = curr in holidays
        if not is_weekend and not is_holiday:
            working_days += 1.0
        curr += timedelta(days=1)

    return working_days

