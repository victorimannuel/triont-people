import os
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from models import db, User, LeaveType, LeaveRequest, LeaveBalance, Company, ApprovalConfig, Department

# ──────────────────────── App Factory ────────────────────────

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gwcuti-secret-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://gwcuti:gwcuti_secret_2026@localhost:5432/gwcuti')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu.'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    with app.app_context():
        from models import User, LeaveType, LeaveRequest, LeaveBalance
        db.create_all()
        seed_initial_data()

    # ── Register blueprints (inline for simplicity) ──
    register_routes(app)

    # ── Template context processors ──
    @app.context_processor
    def inject_globals():
        return {'date': date, 'datetime': datetime}

    @app.template_filter('indonesian_date')
    def indonesian_date_filter(d):
        if not d:
            return ''
        months = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
        return f"{d.day} {months[d.month - 1]} {d.year}"

    # ── Theme color context processor ──
    @app.context_processor
    def inject_theme():
        if current_user.is_authenticated:
            company = Company.query.get(current_user.company_id)
            primary = company.primary_color if company else '#0d9488'
            return dict(primary_color=primary)
        return dict(primary_color='#0d9488')

    return app

# ──────────────────────── Notification Helper ────────────────────────

def send_notification(company, event, leave_request):
    """Send notification based on company config. Logs to console if SMTP not configured."""
    if not company or not company.notifications_enabled:
        return

    if event == 'approve' and not company.notify_on_approve:
        return
    if event == 'reject' and not company.notify_on_reject:
        return
    if event == 'submit' and not company.notify_on_submit:
        return

    emp = leave_request.employee
    status_text = {'approve': 'disetujui', 'reject': 'ditolak', 'submit': 'diajukan'}
    subject = f'Cuti {status_text[event]} — {emp.name}'
    body = f"""
    Halo {emp.name},

    Pengajuan cuti {leave_request.leave_type.name} Anda telah {status_text[event]}.
    Tanggal: {leave_request.start_date.strftime('%d %B %Y')} — {leave_request.end_date.strftime('%d %B %Y')}
    Durasi: {int(leave_request.duration_days)} hari
    Status: {leave_request.status.title()}

    - GwCuti
    """

    if company.smtp_host and company.smtp_user:
        try:
            import smtplib
            from email.message import EmailMessage
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = company.smtp_user
            msg['To'] = emp.email
            msg.set_content(body)

            with smtplib.SMTP(company.smtp_host, company.smtp_port) as server:
                if company.smtp_password:
                    server.starttls()
                    server.login(company.smtp_user, company.smtp_password)
                server.send_message(msg)
        except Exception as e:
            print(f'[NOTIF FAIL] {e}')
    else:
        # Log to console if email not configured
        print(f'[NOTIF] {subject}')
        print(f'[NOTIF] To: {emp.email}')
        print(f'[NOTIF] {body.strip()}')

# ──────────────────────── Seed Data ────────────────────────

def seed_initial_data():
    if User.query.first() is not None:
        return  # already seeded

    # Company
    company = Company(name='The Hyouman', primary_color='#0d9488')
    db.session.add(company)
    db.session.flush()
    cid = company.id

    # Leave Types
    types = [
        LeaveType(name='Cuti Tahunan', description='Cuti tahunan reguler', days_per_year=12, color='#0d9488', icon='fa-umbrella-beach', requires_approval=True, company_id=cid),
        LeaveType(name='Cuti Sakit', description='Cuti karena sakit (surat dokter menyusul)', days_per_year=30, color='#ef4444', icon='fa-hospital', requires_approval=True, company_id=cid),
        LeaveType(name='Cuti Izin', description='Izin keperluan pribadi', days_per_year=0, color='#f59e0b', icon='fa-calendar-check', requires_approval=True, company_id=cid),
        LeaveType(name='Cuti Melahirkan', description='Cuti melahirkan', days_per_year=90, color='#ec4899', icon='fa-baby', requires_approval=True, company_id=cid),
        LeaveType(name='Cuti Pernikahan', description='Cuti pernikahan', days_per_year=3, color='#8b5cf6', icon='fa-ring', requires_approval=True, company_id=cid),
    ]
    db.session.add_all(types)
    db.session.flush()

    # Departments
    dept_engineering = Department(name='Engineering', company_id=cid)
    dept_hr = Department(name='Human Resources', company_id=cid)
    dept_finance = Department(name='Finance', company_id=cid)
    db.session.add_all([dept_engineering, dept_hr, dept_finance])
    db.session.flush()

    # Admin (no department)
    admin = User(name='Admin GwCuti', email='admin@gwcuti.app', role='admin', avatar_color='#ef4444', company_id=cid)
    admin.set_password('admin123')
    # Manager — head of Engineering
    manager = User(name='Manager Budi', email='manager@gwcuti.app', role='manager', avatar_color='#0d9488', company_id=cid, department_id=dept_engineering.id)
    manager.set_password('manager123')
    # HR — head of Human Resources
    hr = User(name='HR Dewi', email='hr@gwcuti.app', role='hr', avatar_color='#10b981', company_id=cid, department_id=dept_hr.id)
    hr.set_password('hr123')
    db.session.add_all([admin, manager, hr])
    db.session.flush()
    # Set department heads
    dept_engineering.head_id = manager.id
    dept_hr.head_id = hr.id
    db.session.flush()

    # Employees
    # Engineering: Andi, Siti, Bambang
    emp1 = User(name='Andi Pratama', email='andi@gwcuti.app', role='employee', manager_id=manager.id, avatar_color='#6366F1', company_id=cid, department_id=dept_engineering.id)
    emp1.set_password('employee123')
    emp2 = User(name='Siti Nurhaliza', email='siti@gwcuti.app', role='employee', manager_id=manager.id, avatar_color='#EC4899', company_id=cid, department_id=dept_engineering.id)
    emp2.set_password('employee123')
    emp3 = User(name='Bambang Susilo', email='bambang@gwcuti.app', role='employee', manager_id=manager.id, avatar_color='#10B981', company_id=cid, department_id=dept_engineering.id)
    emp3.set_password('employee123')
    # Finance: Dewi, Rudi
    emp4 = User(name='Dewi Lestari', email='dewi@gwcuti.app', role='employee', manager_id=None, avatar_color='#F59E0B', company_id=cid, department_id=dept_finance.id)
    emp4.set_password('employee123')
    emp5 = User(name='Rudi Hermawan', email='rudi@gwcuti.app', role='employee', manager_id=None, avatar_color='#8B5CF6', company_id=cid, department_id=dept_finance.id)
    emp5.set_password('employee123')
    db.session.add_all([emp1, emp2, emp3, emp4, emp5])
    db.session.flush()

    # Balances for each employee × leave type
    this_year = date.today().year
    employees_all = User.query.filter(User.role == 'employee').all()
    leave_types = LeaveType.query.all()
    for emp in employees_all:
        for lt in leave_types:
            if lt.days_per_year > 0:
                bal = LeaveBalance(employee_id=emp.id, leave_type_id=lt.id, year=this_year, total_days=lt.days_per_year, used_days=0, pending_days=0, company_id=cid)
                db.session.add(bal)

    # Default approval configs (1 level: manager for all leave types)
    for lt in leave_types:
        db.session.add(ApprovalConfig(company_id=cid, leave_type_id=lt.id, level=1, approver_role='manager'))
    # Also a fallback default for any new leave type
    db.session.add(ApprovalConfig(company_id=cid, leave_type_id=None, level=1, approver_role='manager'))

    # Sample leave requests for the current year
    import random
    sample_reqs = [
        (employees_all[0], leave_types[0], 10, 12, 'Cuti tahunan ke Bali', 'approved', manager.id),
        (employees_all[1], leave_types[1], 2, 2, 'Kurang enak badan', 'approved', manager.id),
        (employees_all[2], leave_types[2], 5, 5, 'Ada acara keluarga', 'pending', None),
        (employees_all[3], leave_types[0], 20, 22, 'Liburan ke Jepang', 'rejected', manager.id),
    ]
    for emp, lt, start_day, end_day, reason, status, appr_id in sample_reqs:
        start = date(this_year, 1, start_day) if start_day <= 28 else date(this_year, 2, start_day - 28)
        end = date(this_year, 1, end_day) if end_day <= 28 else date(this_year, 2, end_day - 28)
        dur = (end - start).days + 1
        req = LeaveRequest(
            employee_id=emp.id, leave_type_id=lt.id,
            start_date=start, end_date=end, duration_days=dur,
            reason=reason, status=status,
            approved_by=appr_id,
            approved_at=datetime.utcnow() if status == 'approved' else None,
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
            company_id=cid,
            current_approval_level=1 if status == 'pending' else 1,
            max_approval_level=1
        )
        db.session.add(req)
        if status == 'approved':
            bal = LeaveBalance.query.filter_by(employee_id=emp.id, leave_type_id=lt.id, year=this_year).first()
            if bal:
                bal.used_days += dur
        elif status == 'pending':
            bal = LeaveBalance.query.filter_by(employee_id=emp.id, leave_type_id=lt.id, year=this_year).first()
            if bal:
                bal.pending_days += dur

    db.session.commit()

# ──────────────────────── Decorators ────────────────────────

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ──────────────────────── Routes ────────────────────────

