from extensions import db
from models.leave import LeaveType


def leave_type_ordering():
    """Stable, company-configured ordering for leave types."""
    return (
        db.func.coalesce(db.func.nullif(LeaveType.sort_order, 0), LeaveType.id).asc(),
        LeaveType.id.asc(),
    )


def order_leave_type_query(query):
    return query.order_by(*leave_type_ordering())


def next_leave_type_sort_order(company_id):
    max_order = db.session.query(
        db.func.max(db.func.coalesce(db.func.nullif(LeaveType.sort_order, 0), LeaveType.id))
    ).filter(LeaveType.company_id == company_id).scalar()
    try:
        return int(max_order or 0) + 10
    except (TypeError, ValueError):
        return 10
