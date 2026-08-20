"""Populate the local People by Triton development database with coherent demo data.

Run with:
DATABASE_URL=sqlite:////absolute/path/people_dev.db SECRET_KEY=dev .venv/bin/python demo_data.py
"""

from datetime import date, datetime

from app import create_app
from models import ApprovalConfig, Company, Department, LeaveBalance, LeaveRequest, LeaveType, User, db

YEAR = 2026
PASSWORD = "people123"


def get_or_create_company(name, color):
    company = Company.query.filter_by(name=name).first()
    if not company:
        company = Company(name=name, primary_color=color, is_active=True)
        db.session.add(company)
        db.session.flush()
    company.primary_color = color
    company.is_active = True
    return company


def get_or_create_user(company, name, email, role, color):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(company_id=company.id, name=name, email=email, role=role)
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.flush()
    user.company_id = company.id
    user.name = name
    user.role = role
    user.avatar_color = color
    user.is_active = True
    return user


def get_or_create_department(company, name, head=None):
    department = Department.query.filter_by(company_id=company.id, name=name).first()
    if not department:
        department = Department(company_id=company.id, name=name)
        db.session.add(department)
        db.session.flush()
    department.head_id = head.id if head else None
    return department


def get_or_create_leave_type(company, name, days, color, description, icon):
    leave_type = LeaveType.query.filter_by(company_id=company.id, name=name).first()
    if not leave_type:
        leave_type = LeaveType(company_id=company.id, name=name)
        db.session.add(leave_type)
        db.session.flush()
    leave_type.days_per_year = days
    leave_type.color = color
    leave_type.description = description
    leave_type.icon = icon
    leave_type.is_active = True
    return leave_type


def ensure_balance(user, leave_type, used=0, pending=0):
    balance = LeaveBalance.query.filter_by(
        company_id=user.company_id,
        employee_id=user.id,
        leave_type_id=leave_type.id,
        year=YEAR,
    ).first()
    if not balance:
        balance = LeaveBalance(
            company_id=user.company_id,
            employee_id=user.id,
            leave_type_id=leave_type.id,
            year=YEAR,
        )
        db.session.add(balance)
    balance.total_days = leave_type.days_per_year
    balance.used_days = used
    balance.pending_days = pending


def get_or_create_request(employee, leave_type, start, end, status, reason, approver=None, notes=None):
    request = LeaveRequest.query.filter_by(
        company_id=employee.company_id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        start_date=start,
        end_date=end,
    ).first()
    if not request:
        request = LeaveRequest(
            company_id=employee.company_id,
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            start_date=start,
            end_date=end,
        )
        db.session.add(request)
    request.duration_days = (end - start).days + 1
    request.status = status
    request.reason = reason
    request.current_approval_level = 2 if status == "approved" else 1
    request.max_approval_level = 2
    request.approved_by = approver.id if approver and status == "approved" else None
    request.approved_at = datetime(2026, 8, 1, 10, 0) if status == "approved" else None
    request.notes = notes
    return request


def seed_demo_data():
    legacy_admin = db.session.get(Company, 1)
    legacy_employee = db.session.get(Company, 2)
    if legacy_admin:
        legacy_admin.name = "Triton Holdings"
        legacy_admin.primary_color = "#1E5A52"
        holdings = legacy_admin
    else:
        holdings = get_or_create_company("Triton Holdings", "#1E5A52")

    if legacy_employee:
        legacy_employee.name = "Triton Digital"
        legacy_employee.primary_color = "#2563EB"
        digital = legacy_employee
    else:
        digital = get_or_create_company("Triton Digital", "#2563EB")

    studio = get_or_create_company("Triton Studio", "#C2410C")
    db.session.flush()

    admin = get_or_create_user(holdings, "Nadia Prasetyo", "admin@people.triton", "admin", "#1E5A52")
    raka = get_or_create_user(holdings, "Raka Pratama", "manager@people.triton", "manager", "#2563EB")
    nabila = get_or_create_user(holdings, "Nabila Putri", "hr@people.triton", "hr", "#9333EA")
    aisha = get_or_create_user(holdings, "Aisha Ramadhani", "aisha@people.triton", "employee", "#DB2777")
    dimas = get_or_create_user(holdings, "Dimas Fadli", "dimas@people.triton", "employee", "#0891B2")
    catherine = get_or_create_user(holdings, "Catherine Wijaya", "catherine@people.triton", "employee", "#D97706")
    reza = get_or_create_user(holdings, "Reza Mahendra", "reza@people.triton", "employee", "#4F46E5")

    salsa = get_or_create_user(digital, "Salsa Aulia", "salsa@people.triton", "employee", "#DB2777")
    bima = get_or_create_user(digital, "Bima Aditya", "bob@people.triton", "manager", "#2563EB")
    farah = get_or_create_user(digital, "Farah Nursari", "farah@people.triton", "hr", "#9333EA")
    ilham = get_or_create_user(digital, "Ilham Setiawan", "ilham@people.triton", "employee", "#0891B2")
    maya = get_or_create_user(digital, "Maya Kurnia", "maya@people.triton", "employee", "#D97706")

    ardi = get_or_create_user(studio, "Ardi Nugraha", "ardi@people.triton", "manager", "#1E5A52")
    kezia = get_or_create_user(studio, "Kezia Ananda", "kezia@people.triton", "employee", "#DB2777")
    rafi = get_or_create_user(studio, "Rafi Akbar", "rafi@people.triton", "employee", "#0891B2")
    db.session.flush()

    product = get_or_create_department(holdings, "Product & Engineering", raka)
    people = get_or_create_department(holdings, "People & Culture", nabila)
    finance = get_or_create_department(holdings, "Finance & Operations", admin)
    growth = get_or_create_department(digital, "Growth", bima)
    customer = get_or_create_department(digital, "Customer Experience", farah)
    creative = get_or_create_department(studio, "Creative Studio", ardi)

    for user, department, manager in [
        (raka, product, admin), (nabila, people, admin), (aisha, product, raka),
        (dimas, product, raka), (catherine, finance, admin), (reza, product, raka),
        (bima, growth, None), (farah, customer, bima), (salsa, growth, bima),
        (ilham, growth, bima), (maya, customer, farah), (ardi, creative, None),
        (kezia, creative, ardi), (rafi, creative, ardi),
    ]:
        user.department_id = department.id
        user.manager_id = manager.id if manager else None

    all_types = {}
    for company in [holdings, digital, studio]:
        all_types[company.id] = {
            "annual": get_or_create_leave_type(company, "Cuti Tahunan", 12, "#1E5A52", "Waktu rehat tahunan untuk kebutuhan pribadi.", "fa-umbrella-beach"),
            "sick": get_or_create_leave_type(company, "Cuti Sakit", 0, "#DC2626", "Cuti saat kondisi kesehatan membutuhkan pemulihan.", "fa-notes-medical"),
            "parental": get_or_create_leave_type(company, "Cuti Melahirkan", 90, "#DB2777", "Dukungan waktu untuk kelahiran dan pemulihan.", "fa-heart"),
            "personal": get_or_create_leave_type(company, "Izin Personal", 2, "#D97706", "Izin singkat untuk urusan personal penting.", "fa-user-clock"),
        }
        if not ApprovalConfig.query.filter_by(company_id=company.id, leave_type_id=None, level=1).first():
            db.session.add(ApprovalConfig(company_id=company.id, leave_type_id=None, level=1, approver_role="manager"))
        if not ApprovalConfig.query.filter_by(company_id=company.id, leave_type_id=None, level=2).first():
            db.session.add(ApprovalConfig(company_id=company.id, leave_type_id=None, level=2, approver_role="hr"))

    balances = [
        (aisha, 2, 0), (dimas, 0, 2), (catherine, 1, 0), (reza, 0, 0),
        (salsa, 3, 0), (ilham, 0, 1), (maya, 1, 0), (kezia, 2, 0), (rafi, 0, 0),
    ]
    for user, annual_used, annual_pending in balances:
        for key, leave_type in all_types[user.company_id].items():
            used = annual_used if key == "annual" else 0
            pending = annual_pending if key == "annual" else 0
            ensure_balance(user, leave_type, used, pending)

    get_or_create_request(aisha, all_types[holdings.id]["annual"], date(2026, 8, 24), date(2026, 8, 25), "approved", "Liburan keluarga.", nabila, "Disetujui. Pastikan handover ke Raka.")
    get_or_create_request(dimas, all_types[holdings.id]["annual"], date(2026, 8, 20), date(2026, 8, 21), "pending", "Keperluan keluarga di luar kota.")
    get_or_create_request(catherine, all_types[holdings.id]["annual"], date(2026, 7, 13), date(2026, 7, 13), "rejected", "Urusan personal.", None, "Mohon ajukan ulang setelah penutupan laporan bulanan.")
    get_or_create_request(salsa, all_types[digital.id]["annual"], date(2026, 9, 7), date(2026, 9, 9), "approved", "Perjalanan keluarga.", farah, "Disetujui.")
    get_or_create_request(ilham, all_types[digital.id]["annual"], date(2026, 8, 28), date(2026, 8, 28), "pending", "Acara keluarga.")
    get_or_create_request(kezia, all_types[studio.id]["annual"], date(2026, 9, 14), date(2026, 9, 15), "approved", "Liburan singkat.", ardi, "Disetujui.")

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_demo_data()
        print("Demo data populated. Password for demo users: people123")
