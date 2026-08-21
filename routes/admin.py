import json
import re
import secrets
from datetime import datetime, date, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify, abort, send_file, session
from flask_login import login_required, current_user, login_user
from sqlalchemy.exc import IntegrityError
from extensions import db
from models.user import User, Department
from models.company import Company
from models.leave import LeaveType, LeaveRequest, LeaveBalance, LeaveGrant
from models.approval import ApprovalConfig
from models.holiday import PublicHoliday
from models.audit import AuditLog
from models.auth import PasswordReset
from core.i18n import translate, normalize_language
from core.auth import get_active_company_id, role_required, validate_password_strength
from services.audit_service import audit_log
from services.holiday_service import sync_company_holidays
from services.import_service import parse_file_headers_and_preview, execute_employee_import
from services.notification_service import send_password_reset_otp_email, send_password_reset_link_email
from core.pagination import get_pagination_args
from core.time_util import utcnow
from routes.common import main_bp

def get_manageable_company_id(company_id=None):
    if not current_user.is_authenticated:
        return None
    if current_user.role != 'admin':
        return current_user.company_id
    if company_id and db.session.get(Company, company_id):
        return company_id
    return get_active_company_id()

# ── ADMIN: COMPANIES & SMTP ──

@main_bp.route('/admin/companies')
@login_required
@role_required('admin')
def admin_companies():
    query = Company.query.order_by(Company.name)
    q = request.args.get('q', '').strip()
    if q:
        query = query.filter(Company.name.ilike(f'%{q}%'))
    notif = request.args.get('notifications', '')
    if notif == 'enabled':
        query = query.filter_by(notifications_enabled=True)
    elif notif == 'disabled':
        query = query.filter_by(notifications_enabled=False)
    page, per_page, per_page_str = get_pagination_args(default=20)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    companies = pagination.items
    return render_template('admin/companies.html', companies=companies, pagination=pagination, per_page_str=per_page_str)

@main_bp.route('/admin/companies/add', methods=['POST'])
@login_required
@role_required('admin')
def admin_add_company():
    name = request.form.get('name', '').strip()
    primary_color = request.form.get('primary_color', '#0d9488')
    if not name:
        flash(translate('Company name is required.'), 'danger')
        return redirect(url_for('main.admin_companies'))
    if Company.query.filter_by(name=name).first():
        flash(translate('Company already exists.'), 'danger')
        return redirect(url_for('main.admin_companies'))
    company = Company(name=name, primary_color=primary_color, delegate_enabled=bool(request.form.get('delegate_enabled')))
    db.session.add(company)
    db.session.commit()
    audit_log('admin.company_created', 'company', company.id, details={'name': company.name}, company_id=company.id)
    flash(translate(f'Perusahaan {name} berhasil ditambahkan!'), 'success')
    return redirect(url_for('main.admin_companies'))

@main_bp.route('/admin/companies/edit/<int:company_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_edit_company(company_id):
    company = Company.query.get_or_404(company_id)
    company.name = request.form.get('name', company.name)
    company.primary_color = request.form.get('primary_color', company.primary_color)
    company.notifications_enabled = bool(request.form.get('notifications_enabled'))
    company.delegate_enabled = bool(request.form.get('delegate_enabled'))
    company.smtp_host = request.form.get('smtp_host') or None
    company.smtp_port = request.form.get('smtp_port', type=int) or 587
    company.smtp_user = request.form.get('smtp_user') or None
    if request.form.get('smtp_password'):
        company.smtp_password = request.form.get('smtp_password')
    company.notify_on_approve = bool(request.form.get('notify_on_approve'))
    company.notify_on_reject = bool(request.form.get('notify_on_reject'))
    company.notify_on_submit = bool(request.form.get('notify_on_submit'))
    db.session.commit()
    audit_log('admin.company_updated', 'company', company.id, details={'name': company.name}, company_id=company.id)
    flash(translate(f'Perusahaan {company.name} berhasil diperbarui!'), 'success')
    return redirect(url_for('main.admin_companies'))

@main_bp.route('/admin/smtp', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_smtp():
    company_id = get_active_company_id()
    company = db.session.get(Company, company_id)
    if request.method == 'POST':
        if not company:
            flash(translate('Company not found.'), 'danger')
            return redirect(url_for('main.admin_smtp'))

        company.notifications_enabled = bool(request.form.get('notifications_enabled'))
        company.smtp_host = request.form.get('smtp_host', '').strip() or None
        company.smtp_port = request.form.get('smtp_port', type=int) or 587
        company.smtp_user = request.form.get('smtp_user', '').strip() or None
        if request.form.get('smtp_password'):
            company.smtp_password = request.form.get('smtp_password')
        company.notify_on_approve = bool(request.form.get('notify_on_approve'))
        company.notify_on_reject = bool(request.form.get('notify_on_reject'))
        company.notify_on_submit = bool(request.form.get('notify_on_submit'))

        audit_log('company.smtp_updated', 'company', company.id)
        db.session.commit()
        flash(translate('Company SMTP settings updated.'), 'success')
        return redirect(url_for('main.admin_smtp'))

    return render_template('admin/smtp.html', company=company)

@main_bp.route('/admin/smtp/test', methods=['POST'])
@login_required
@role_required('admin')
def admin_smtp_test():
    company_id = get_active_company_id()
    company = db.session.get(Company, company_id)
    if not company or not company.smtp_host or not company.smtp_user:
        flash(translate('Please fill in SMTP configuration first.'), 'warning')
        return redirect(url_for('main.admin_smtp'))

    test_recipient = request.form.get('test_recipient', current_user.email).strip() or current_user.email
    try:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg['Subject'] = f'Test Email Notifikasi - {company.name}'
        msg['From'] = company.smtp_user
        msg['To'] = test_recipient
        msg.set_content(f"""Halo {current_user.name},

Ini adalah email uji coba dari People by Triont untuk perusahaan {company.name}.
Konfigurasi SMTP server Anda telah berhasil terhubung dan berfungsi dengan baik!

Waktu pengujian: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
SMTP Host: {company.smtp_host}:{company.smtp_port}
Email Pengirim: {company.smtp_user}

Salam,
People by Triont""")

        if company.smtp_port == 465:
            server = smtplib.SMTP_SSL(company.smtp_host, company.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(company.smtp_host, company.smtp_port, timeout=15)
            server.starttls()

        with server:
            if company.smtp_password:
                server.login(company.smtp_user, company.smtp_password)
            server.send_message(msg)

        flash(translate(f'Email uji coba berhasil dikirim ke {test_recipient}! ✅'), 'success')
    except Exception as e:
        flash(translate(f'Gagal mengirim email test: {e}'), 'danger')

    return redirect(url_for('main.admin_smtp'))

@main_bp.route('/admin/custom-domain-guide')
@login_required
@role_required('admin')
def admin_custom_domain_guide():
    return render_template('admin/custom_domain_guide.html')

# ── ADMIN: EMPLOYEES ──

@main_bp.route('/admin/employees')
@login_required
@role_required('manager', 'hr', 'admin')
def admin_employees():
    status_tab = request.args.get('status', '').strip().lower()
    if not status_tab:
        if request.args.get('archived') == '1':
            status_tab = 'archived'
        elif request.args.get('deleted') == '1':
            status_tab = 'deleted'
        else:
            status_tab = 'active'

    # Non-admin cannot access deleted tab
    if status_tab == 'deleted' and current_user.role != 'admin':
        status_tab = 'active'

    show_archived = (status_tab == 'archived')
    my_company = get_active_company_id()

    if status_tab == 'deleted':
        query = User.query.filter_by(company_id=my_company, is_deleted=True)
    elif status_tab == 'archived':
        query = User.query.filter_by(company_id=my_company, is_deleted=False, is_active=False)
    else:
        status_tab = 'active'
        query = User.query.filter_by(company_id=my_company, is_deleted=False, is_active=True)

    q = request.args.get('q', '').strip()
    if q:
        query = query.filter((User.name.ilike(f'%{q}%')) | (User.email.ilike(f'%{q}%')))

    role = request.args.get('role', '')
    if role:
        query = query.filter_by(role=role)

    department_id = request.args.get('department_id', type=int)
    if department_id:
        query = query.filter_by(department_id=department_id)

    page, per_page, per_page_str = get_pagination_args(default=20)
    pagination = query.order_by(User.role.desc(), User.name).paginate(page=page, per_page=per_page, error_out=False)
    employees = pagination.items
    managers = User.query.filter(User.company_id == my_company, User.is_deleted == False, User.is_active == True, User.role.in_(['manager', 'hr', 'admin'])).order_by(User.name).all()
    departments = Department.query.filter_by(company_id=my_company).all()
    return render_template(
        'admin/employees.html',
        employees=employees,
        pagination=pagination,
        per_page_str=per_page_str,
        managers=managers,
        departments=departments,
        leave_types=LeaveType.query.filter_by(company_id=my_company, is_active=True).order_by(LeaveType.name).all(),
        grant_token=secrets.token_urlsafe(24),
        companies=Company.query.filter_by(is_active=True).order_by(Company.name).all(),
        show_archived=show_archived,
        current_tab=status_tab
    )

@main_bp.route('/admin/impersonate/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_impersonate_user(user_id):
    target_user = db.session.get(User, user_id)
    if not target_user or not target_user.is_active:
        flash(translate('Pengguna tidak ditemukan atau tidak aktif.'), 'danger')
        return redirect(url_for('main.admin_employees'))

    if target_user.id == current_user.id:
        flash(translate('Anda sudah login sebagai akun ini.'), 'info')
        return redirect(url_for('main.dashboard'))

    # Store original impersonator admin in session
    admin_id = current_user.id
    admin_name = current_user.name
    session['impersonator_admin_id'] = admin_id
    session['impersonator_admin_name'] = admin_name

    # Switch session to target user
    login_user(target_user)
    session['company_id'] = target_user.company_id
    session['language'] = normalize_language(target_user.language_preference or 'en')

    audit_log('admin.impersonate_user', 'user', target_user.id, details={
        'admin_id': admin_id,
        'admin_name': admin_name,
        'target_email': target_user.email,
        'target_name': target_user.name
    }, company_id=target_user.company_id)
    db.session.commit()

    flash(translate(f'Berhasil masuk sebagai {target_user.name} ({target_user.email}).'), 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/admin/employees/<int:user_id>/send-reset-password', methods=['POST'])
@login_required
@role_required('admin')
def admin_send_employee_password_reset(user_id):
    emp = db.session.get(User, user_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or 'application/json' in request.headers.get('Accept', '')

    if not emp or not emp.is_active:
        msg = translate('Pengguna tidak ditemukan atau tidak aktif.')
        if is_ajax:
            return jsonify({'success': False, 'error': msg}), 404
        flash(msg, 'danger')
        return redirect(url_for('main.admin_employees'))

    try:
        # Invalidate previous unused resets
        PasswordReset.query.filter_by(user_id=emp.id, is_used=False).update({'is_used': True})

        reset_token = secrets.token_urlsafe(32)
        otp_placeholder = f"{secrets.randbelow(900000) + 100000:06d}"
        expires_at = utcnow() + timedelta(minutes=60)

        reset_entry = PasswordReset(
            user_id=emp.id,
            reset_token=reset_token,
            expires_at=expires_at,
            created_by_id=current_user.id
        )
        reset_entry.set_otp(otp_placeholder)
        db.session.add(reset_entry)
        db.session.commit()

        reset_link = url_for('auth.reset_password', token=reset_token, _external=True)

        company = db.session.get(Company, emp.company_id) if emp.company_id else None
        email_sent = False
        try:
            email_sent = send_password_reset_link_email(company, emp, reset_link)
        except Exception as mail_err:
            print(f"Error sending password reset link email: {mail_err}")

        audit_log('admin.send_employee_password_reset', 'user', emp.id, details={
            'admin_id': current_user.id,
            'employee_email': emp.email,
            'employee_name': emp.name,
            'email_sent': bool(email_sent)
        }, company_id=emp.company_id)
        db.session.commit()

        if email_sent:
            msg = translate(f'Link reset password telah dikirim ke {emp.name} ({emp.email}).')
            if is_ajax:
                return jsonify({'success': True, 'message': msg, 'employee_name': emp.name, 'employee_email': emp.email})
            flash(msg, 'success')
        else:
            msg = translate(f'Link reset password berhasil dibuat untuk {emp.name} ({emp.email}), namun email gagal dikirim atau SMTP belum dikonfigurasi.')
            if is_ajax:
                return jsonify({'success': False, 'warning': True, 'message': msg, 'employee_name': emp.name, 'employee_email': emp.email})
            flash(msg, 'warning')
    except Exception as e:
        db.session.rollback()
        print(f"Error in admin_send_employee_password_reset: {e}")
        err_msg = translate(f'Terjadi kesalahan saat memproses reset password: {str(e)}')
        if is_ajax:
            return jsonify({'success': False, 'error': err_msg}), 500
        flash(err_msg, 'danger')

    return redirect(url_for('main.admin_employees'))

@main_bp.route('/admin/stop-impersonation', methods=['GET', 'POST'])
@login_required
def admin_stop_impersonation():
    admin_id = session.get('impersonator_admin_id')
    if not admin_id:
        flash(translate('You are not currently in account simulation mode.'), 'info')
        return redirect(url_for('main.dashboard'))

    admin_user = db.session.get(User, admin_id)
    if not admin_user or admin_user.role != 'admin' or not admin_user.is_active:
        session.pop('impersonator_admin_id', None)
        session.pop('impersonator_admin_name', None)
        flash(translate('Sesi admin tidak valid.'), 'danger')
        return redirect(url_for('main.dashboard'))

    # Remove impersonator flags
    session.pop('impersonator_admin_id', None)
    session.pop('impersonator_admin_name', None)

    # Restore admin login
    login_user(admin_user)
    session['company_id'] = admin_user.company_id
    session['language'] = normalize_language(admin_user.language_preference or 'en')

    audit_log('admin.stop_impersonation', 'user', admin_user.id, company_id=admin_user.company_id)
    db.session.commit()

    flash(translate('Returned to Super Admin session.'), 'success')
    return redirect(url_for('main.admin_employees'))

@main_bp.route('/admin/leave-balances')
@login_required
@role_required('manager', 'hr', 'admin')
def admin_leave_balances():
    my_company = get_active_company_id()
    this_year = date.today().year
    year_filter = request.args.get('year', type=int) or this_year
    q = request.args.get('q', '').strip()
    department_id = request.args.get('department_id', type=int)

    # Query distinct years available in LeaveBalance for this company
    existing_years = [r[0] for r in db.session.query(LeaveBalance.year).filter_by(company_id=my_company).distinct().order_by(LeaveBalance.year.desc()).all() if r[0]]
    if this_year not in existing_years:
        existing_years.insert(0, this_year)
    years = sorted(list(set(existing_years + [this_year, this_year - 1, 2025, 2024])), reverse=True)

    # Active leave types and departments
    leave_types = LeaveType.query.filter_by(company_id=my_company, is_active=True).order_by(LeaveType.id.asc()).all()
    departments = Department.query.filter_by(company_id=my_company).order_by(Department.name.asc()).all()

    # Query employees
    emp_query = User.query.filter_by(company_id=my_company, is_active=True, is_deleted=False)
    if current_user.role == 'manager':
        subordinate_ids = db.session.query(User.id).filter(User.manager_id == current_user.id)
        dept_ids = db.session.query(Department.id).filter(Department.head_id == current_user.id)
        dept_member_ids = db.session.query(User.id).filter(User.department_id.in_(dept_ids))
        emp_query = emp_query.filter(
            (User.id.in_(subordinate_ids)) |
            (User.id.in_(dept_member_ids)) |
            (User.id == current_user.id)
        )

    if q:
        emp_query = emp_query.filter((User.name.ilike(f'%{q}%')) | (User.email.ilike(f'%{q}%')))

    if department_id:
        emp_query = emp_query.filter_by(department_id=department_id)

    page, per_page, per_page_str = get_pagination_args(default=20)
    pagination = emp_query.order_by(User.name.asc()).paginate(page=page, per_page=per_page, error_out=False)
    employees = pagination.items
    emp_ids = [e.id for e in employees]

    # Query balances for these employees and year
    balances = LeaveBalance.query.filter(
        LeaveBalance.company_id == my_company,
        LeaveBalance.year == year_filter,
        LeaveBalance.employee_id.in_(emp_ids)
    ).all() if emp_ids else []

    # Map by (employee_id, leave_type_id)
    balance_map = {(b.employee_id, b.leave_type_id): b for b in balances}

    # Calculate aggregate stats
    total_allocated = sum(b.total_days for b in balances)
    total_used = sum(b.used_days for b in balances)
    total_pending = sum(b.pending_days for b in balances)
    total_remaining = sum(max(0.0, b.total_days - b.used_days) for b in balances)

    return render_template(
        'admin/leave_balances.html',
        employees=employees,
        pagination=pagination,
        per_page_str=per_page_str,
        leave_types=leave_types,
        departments=departments,
        balance_map=balance_map,
        years=years,
        year_filter=year_filter,
        q=q,
        department_filter=department_id,
        total_allocated=total_allocated,
        total_used=total_used,
        total_pending=total_pending,
        total_remaining=total_remaining,
        grant_token=secrets.token_urlsafe(24)
    )

@main_bp.route('/admin/leave-balances/rollover', methods=['POST'])
@login_required
@role_required('hr', 'admin')
def admin_leave_balance_rollover():
    """Batch annual rollover: reset or carry-forward leave balances for all active employees."""
    company_id = get_active_company_id()
    data = request.get_json(silent=True) or {}

    from_year = data.get('from_year')
    # must be an integer
    if not isinstance(from_year, int):
        return jsonify(ok=False, message=translate('Parameter tidak valid.')), 400

    to_year = from_year + 1
    mode = data.get('mode', '')          # 'reset' | 'carry_forward'
    leave_type_ids = data.get('leave_type_ids', [])   # empty list = all types
    max_carry = data.get('max_carry_days')             # None = no cap
    rollover_token = data.get('rollover_token', '').strip()

    # --- Validate inputs ---
    current_year = date.today().year
    if not (2020 <= from_year <= current_year + 1):
        return jsonify(ok=False, message=translate('Tahun sumber tidak valid.')), 400
    if mode not in ('reset', 'carry_forward'):
        return jsonify(ok=False, message=translate('Mode rollover tidak valid.')), 400
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', rollover_token):
        return jsonify(ok=False, message=translate('Token tidak valid.')), 400
    if max_carry is not None and (not isinstance(max_carry, (int, float)) or max_carry < 0):
        return jsonify(ok=False, message=translate('Batas carry-forward tidak valid.')), 400

    # Idempotency check via LeaveGrant with special rollover mode flag
    # Idempotency: grants are stored as {rollover_token}_{lt.id}, check for prefix
    existing = LeaveGrant.query.filter(
        LeaveGrant.company_id == company_id,
        LeaveGrant.request_token.like(f'{rollover_token}_%'),
    ).first()
    if existing:
        return jsonify(ok=True, message=translate('Rollover ini sudah diproses sebelumnya.'), skipped=True)

    # Active leave types for this company
    lt_query = LeaveType.query.filter_by(company_id=company_id, is_active=True)
    if leave_type_ids:
        lt_query = lt_query.filter(LeaveType.id.in_(leave_type_ids))
    leave_types = lt_query.all()
    if not leave_types:
        return jsonify(ok=False, message=translate('Tidak ada jenis cuti yang sesuai.')), 400

    # Active employees for this company
    employees = User.query.filter_by(company_id=company_id, is_active=True, is_deleted=False).all()
    if not employees:
        return jsonify(ok=False, message=translate('Tidak ada karyawan aktif.')), 400

    created_count = 0
    updated_count = 0

    for emp in employees:
        for lt in leave_types:
            src_bal = LeaveBalance.query.filter_by(
                company_id=company_id,
                employee_id=emp.id,
                leave_type_id=lt.id,
                year=from_year,
            ).first()

            if mode == 'reset':
                carry_days = 0.0
            else:
                # carry_forward: remaining = total - used (floored at 0)
                if src_bal:
                    remaining = max(0.0, src_bal.total_days - src_bal.used_days)
                    carry_days = remaining if max_carry is None else min(remaining, float(max_carry))
                else:
                    carry_days = 0.0

            # Base quota from leave type definition
            base_quota = float(lt.days_per_year)
            new_total = base_quota + carry_days

            # Upsert destination year balance
            dst_bal = LeaveBalance.query.filter_by(
                company_id=company_id,
                employee_id=emp.id,
                leave_type_id=lt.id,
                year=to_year,
            ).with_for_update().first()

            if dst_bal:
                dst_bal.total_days = new_total
                updated_count += 1
            else:
                dst_bal = LeaveBalance(
                    company_id=company_id,
                    employee_id=emp.id,
                    leave_type_id=lt.id,
                    year=to_year,
                    total_days=new_total,
                    used_days=0.0,
                    pending_days=0.0,
                )
                db.session.add(dst_bal)
                created_count += 1

    # Record one LeaveGrant per leave type as an audit trail (actor-level)
    for lt in leave_types:
        grant = LeaveGrant(
            company_id=company_id,
            employee_id=None,
            leave_type_id=lt.id,
            year=to_year,
            mode=f'rollover_{mode}',
            amount=0,
            old_total=0,
            new_total=0,
            actor_id=current_user.id,
            request_token=f'{rollover_token}_{lt.id}',
        )
        db.session.add(grant)

    audit_log('admin.leave_balance_rollover', 'company', company_id, details={
        'from_year': from_year,
        'to_year': to_year,
        'mode': mode,
        'max_carry_days': max_carry,
        'leave_type_ids': [lt.id for lt in leave_types],
        'employees_affected': len(employees),
        'balances_created': created_count,
        'balances_updated': updated_count,
    }, company_id=company_id)

    db.session.commit()

    msg = translate(f'Rollover selesai: {created_count + updated_count} saldo diproses untuk {len(employees)} karyawan ke tahun {to_year}.')
    return jsonify(ok=True, message=msg, created=created_count, updated=updated_count, to_year=to_year)


@main_bp.route('/admin/employees/add', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_add_employee():
    target_company_id = get_manageable_company_id(request.form.get('company_id', type=int))
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'employee')
    manager_id = request.form.get('manager_id', type=int)
    department_id = request.form.get('department_id', type=int)

    if not all([name, email, password]):
        flash(translate('Please enter name, email, and password.'), 'danger')
        return redirect(url_for('main.admin_employees'))

    if not validate_password_strength(password):
        flash(translate('Password must be at least 8 characters and include letters and numbers.'), 'danger')
        return redirect(url_for('main.admin_employees'))

    if User.query.filter_by(email=email).first():
        flash(translate('Email is already registered.'), 'danger')
        return redirect(url_for('main.admin_employees'))

    user = User(name=name, email=email, role=role, company_id=target_company_id)
    user.set_password(password)
    if manager_id:
        manager = User.query.filter_by(id=manager_id, company_id=target_company_id).first()
        if manager:
            user.manager_id = manager.id
    if department_id:
        department = Department.query.filter_by(id=department_id, company_id=target_company_id).first()
        if department:
            user.department_id = department.id
    db.session.add(user)
    db.session.flush()

    this_year = date.today().year
    for leave_type in LeaveType.query.filter(LeaveType.days_per_year > 0, LeaveType.company_id == target_company_id).all():
        bal = LeaveBalance(
            company_id=target_company_id,
            employee_id=user.id,
            leave_type_id=leave_type.id,
            year=this_year,
            total_days=leave_type.days_per_year
        )
        db.session.add(bal)
    db.session.commit()
    audit_log('admin.employee_created', 'user', user.id, details={'name': user.name, 'email': user.email, 'role': user.role}, company_id=target_company_id)
    flash(translate(f'Karyawan {name} berhasil ditambahkan!'), 'success')
    return redirect(url_for('main.admin_employees'))

@main_bp.route('/admin/employees/import/preview', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_employees_import_preview():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Tidak ada file yang diunggah.'}), 400
    
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'File belum dipilih.'}), 400

    try:
        preview_data = parse_file_headers_and_preview(file.stream, file.filename)
        return jsonify({'success': True, 'data': preview_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@main_bp.route('/admin/employees/import/execute', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_employees_import_execute():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Tidak ada file yang diunggah.'}), 400
    
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'File belum dipilih.'}), 400

    mapping_raw = request.form.get('mapping', '{}')
    try:
        mapping = json.loads(mapping_raw)
    except Exception:
        mapping = {}

    update_existing = request.form.get('update_existing') in ('1', 'true', 'True', True)
    target_company_id = get_manageable_company_id(request.form.get('company_id', type=int))

    try:
        result = execute_employee_import(
            file.stream,
            file.filename,
            mapping,
            target_company_id,
            current_user.id,
            update_existing=update_existing
        )
        return jsonify(result)
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@main_bp.route('/admin/employees/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_edit_employee(user_id):
    if request.method == 'GET':
        return redirect(url_for('main.admin_employees'))

    user = User.query.filter_by(id=user_id, company_id=get_active_company_id()).first_or_404()
    target_company_id = get_manageable_company_id(request.form.get('company_id', type=int))
    email = request.form.get('email', user.email).strip()
    if User.query.filter(User.email == email, User.id != user.id).first():
        flash(translate('Email is already registered.'), 'danger')
        return redirect(url_for('main.admin_employees'))
    new_role = request.form.get('role', user.role)

    user.name = request.form.get('name', user.name).strip()
    user.email = email
    user.role = new_role
    user.company_id = target_company_id
    user.manager_id = None
    user.department_id = None
    manager_id = request.form.get('manager_id', type=int)
    department_id = request.form.get('department_id', type=int)
    if manager_id and User.query.filter_by(id=manager_id, company_id=target_company_id).first():
        user.manager_id = manager_id
    if department_id and Department.query.filter_by(id=department_id, company_id=target_company_id).first():
        user.department_id = department_id
    password = request.form.get('password', '')
    if password:
        if not validate_password_strength(password):
            flash(translate('Password must be at least 8 characters and include letters and numbers.'), 'danger')
            return redirect(url_for('main.admin_employees'))
        user.set_password(password)
    db.session.commit()
    audit_log('admin.employee_updated', 'user', user.id, details={'name': user.name, 'email': user.email, 'role': user.role}, company_id=target_company_id)
    flash(translate(f'Karyawan {user.name} berhasil diperbarui!'), 'success')
    return redirect(url_for('main.admin_employees'))

@main_bp.route('/admin/employees/<int:user_id>/leave-balance')
@login_required
@role_required('manager', 'hr', 'admin')
def admin_employee_leave_balance(user_id):
    company_id = get_active_company_id()
    employee = User.query.filter_by(id=user_id, company_id=company_id).first_or_404()
    leave_type_id = request.args.get('leave_type_id', type=int)
    year = request.args.get('year', type=int) or date.today().year
    if year < 2000 or year > date.today().year + 5:
        abort(400)
    leave_type = LeaveType.query.filter_by(id=leave_type_id, company_id=company_id).first_or_404()
    balance = LeaveBalance.query.filter_by(
        company_id=company_id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        year=year,
    ).first()
    total = balance.total_days if balance else 0
    used = balance.used_days if balance else 0
    pending = balance.pending_days if balance else 0
    return jsonify(
        total_days=total,
        used_days=used,
        pending_days=pending,
        remaining_days=total - used - pending,
    )

@main_bp.route('/admin/employees/<int:user_id>/grant-leave', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_grant_leave(user_id):
    company_id = get_active_company_id()
    employee = User.query.filter_by(id=user_id, company_id=company_id).first_or_404()
    if employee.role == 'admin':
        abort(403)

    leave_type_id = request.form.get('leave_type_id', type=int)
    year = request.form.get('year', type=int)
    amount = request.form.get('amount', type=float)
    mode = request.form.get('mode', 'add')
    request_token = request.form.get('grant_token', '').strip()
    if (
        not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', request_token)
        or not year
        or year < 2000
        or year > date.today().year + 5
        or amount is None
        or amount < 0
        or mode not in ('add', 'set')
        or (mode == 'add' and amount == 0)
    ):
        flash(translate('The leave grant data is invalid.'), 'danger')
        return redirect(url_for('main.admin_employees'))

    if LeaveGrant.query.filter_by(request_token=request_token).first():
        flash(translate('This leave grant has already been processed.'), 'info')
        return redirect(url_for('main.admin_employees'))

    leave_type = LeaveType.query.filter_by(
        id=leave_type_id,
        company_id=company_id,
        is_active=True,
    ).first()
    if not leave_type:
        flash(translate('Leave type is not available.'), 'danger')
        return redirect(url_for('main.admin_employees'))

    balance = LeaveBalance.query.filter_by(
        company_id=company_id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        year=year,
    ).with_for_update().first()
    if not balance:
        balance = LeaveBalance(
            company_id=company_id,
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            year=year,
            total_days=0,
        )
        db.session.add(balance)

    old_total = balance.total_days
    if mode == 'set':
        committed_days = balance.used_days + balance.pending_days
        if amount < committed_days:
            flash(translate('The total allocation cannot be lower than used and pending leave.'), 'danger')
            return redirect(url_for('main.admin_employees'))
        balance.total_days = amount
    else:
        balance.total_days += amount

    grant = LeaveGrant(
        company_id=company_id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        year=year,
        mode=mode,
        amount=amount,
        old_total=old_total,
        new_total=balance.total_days,
        actor_id=current_user.id,
        request_token=request_token,
    )
    db.session.add(grant)
    try:
        db.session.flush()
        audit_log('admin.leave_granted', 'leave_balance', balance.id, details={
            'employee_id': employee.id,
            'leave_type_id': leave_type.id,
            'year': year,
            'mode': mode,
            'amount': amount,
            'old_total': old_total,
            'new_total': balance.total_days,
            'grant_id': grant.id,
        }, company_id=company_id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(translate('This leave grant has already been processed.'), 'info')
        return redirect(url_for('main.admin_employees'))

    flash(translate('Leave grant saved.'), 'success')
    return redirect(url_for('main.admin_employees'))

@main_bp.route('/admin/employees/delete/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_delete_employee(user_id):
    if request.method == 'GET':
        flash(translate('Employee deletion must be done via the Delete button on the Admin page.'), 'warning')
        return redirect(url_for('main.admin_employees'))

    my_company = get_active_company_id()
    user = User.query.filter_by(id=user_id, company_id=my_company).first_or_404()
    if user.role == 'admin':
        flash(translate('Admin users cannot be deleted.'), 'danger')
        return redirect(url_for('main.admin_employees'))

    action = request.form.get('action', 'delete')
    name = user.name

    if action == 'archive':
        user.is_active = False
        user.is_deleted = False
        Department.query.filter_by(head_id=user.id).update({'head_id': None})
        User.query.filter_by(manager_id=user.id).update({'manager_id': None})
        audit_log('admin.employee_archived', 'user', user.id, details={'email': user.email}, company_id=my_company)
        db.session.commit()
        flash(translate(f'Karyawan {name} berhasil diarsipkan / dinonaktifkan.'), 'success')
        return redirect(url_for('main.admin_employees', status='archived'))

    # Soft delete: mark is_deleted = True, keep all history/balances/requests intact
    user.is_active = False
    user.is_deleted = True
    user.deleted_at = utcnow()
    Department.query.filter_by(head_id=user.id).update({'head_id': None})
    User.query.filter_by(manager_id=user.id).update({'manager_id': None})

    audit_log('admin.employee_deleted', 'user', user.id, details={'email': user.email, 'mode': 'soft_delete'}, company_id=my_company)
    db.session.commit()
    flash(translate(f'Karyawan {name} berhasil dipindahkan ke kotak sampah.'), 'success')
    return redirect(url_for('main.admin_employees', status='deleted' if current_user.role == 'admin' else 'active'))

@main_bp.route('/admin/employees/restore/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_restore_employee(user_id):
    my_company = get_active_company_id()
    user = User.query.filter_by(id=user_id, company_id=my_company).first_or_404()
    user.is_deleted = False
    user.deleted_at = None
    user.is_active = True
    audit_log('admin.employee_restored', 'user', user.id, details={'email': user.email}, company_id=my_company)
    db.session.commit()
    flash(translate(f'Karyawan {user.name} berhasil dipulihkan.'), 'success')
    return redirect(url_for('main.admin_employees', status='deleted'))

@main_bp.route('/admin/employees/unarchive/<int:user_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_unarchive_employee(user_id):
    my_company = get_active_company_id()
    user = User.query.filter_by(id=user_id, company_id=my_company).first_or_404()
    user.is_active = True
    user.is_deleted = False
    audit_log('admin.employee_unarchived', 'user', user.id, details={'email': user.email}, company_id=my_company)
    db.session.commit()
    flash(translate(f'Karyawan {user.name} berhasil diaktifkan kembali.'), 'success')
    return redirect(url_for('main.admin_employees', status='archived'))

# ── ADMIN: LEAVE TYPES ──

@main_bp.route('/admin/leave-types')
@login_required
@role_required('manager', 'hr', 'admin')
def admin_leave_types():
    my_company = get_active_company_id()
    show_archived = request.args.get('archived') == '1'
    status = request.args.get('status', '')
    query = LeaveType.query.filter_by(company_id=my_company)

    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    else:
        query = query.filter_by(is_active=(not show_archived))

    q = request.args.get('q', '').strip()
    if q:
        query = query.filter(LeaveType.name.ilike(f'%{q}%'))

    page, per_page, per_page_str = get_pagination_args(default=20)
    pagination = query.order_by(LeaveType.name).paginate(page=page, per_page=per_page, error_out=False)
    leave_types = pagination.items

    # Query approval configs for this company
    all_configs = ApprovalConfig.query.filter_by(company_id=my_company).order_by(ApprovalConfig.level.asc()).all()
    default_configs = [c for c in all_configs if c.leave_type_id is None]
    type_configs_map = {}
    for c in all_configs:
        if c.leave_type_id is not None:
            type_configs_map.setdefault(c.leave_type_id, []).append(c)

    return render_template(
        'admin/leave_types.html',
        leave_types=leave_types,
        pagination=pagination,
        per_page_str=per_page_str,
        companies=Company.query.filter_by(is_active=True).order_by(Company.name).all(),
        type_configs_map=type_configs_map,
        default_configs=default_configs,
        show_archived=show_archived
    )

@main_bp.route('/admin/leave-types/add', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_add_leave_type():
    if request.method == 'GET':
        return redirect(url_for('main.admin_leave_types'))

    my_company = get_manageable_company_id(request.form.get('company_id', type=int))
    name = request.form.get('name', '').strip()
    days_per_year = request.form.get('days_per_year', type=int, default=0)
    color = request.form.get('color', '#0d9488')
    description = request.form.get('description', '')
    requires_attachment = bool(request.form.get('requires_attachment'))
    attachment_label = request.form.get('attachment_label', '').strip() or 'Surat Dokter / Bukti Pendukung'

    if not name:
        flash(translate('Leave name is required.'), 'danger')
        return redirect(url_for('main.admin_leave_types'))

    lt = LeaveType(name=name, description=description, days_per_year=days_per_year, color=color,
                   is_active=True, company_id=my_company,
                   requires_attachment=requires_attachment, attachment_label=attachment_label)
    db.session.add(lt)
    db.session.flush()

    this_year = date.today().year
    for emp in User.query.filter(User.role == 'employee', User.company_id == my_company).all():
        bal = LeaveBalance(
            company_id=my_company,
            employee_id=emp.id,
            leave_type_id=lt.id,
            year=this_year,
            total_days=days_per_year,
        )
        db.session.add(bal)
    db.session.commit()
    audit_log('admin.leave_type_created', 'leave_type', lt.id, details={'name': lt.name, 'days': lt.days_per_year}, company_id=my_company)
    flash(translate(f'Jenis cuti {name} berhasil ditambahkan!'), 'success')
    return redirect(url_for('main.admin_leave_types'))

@main_bp.route('/admin/leave-types/edit/<int:type_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_edit_leave_type(type_id):
    lt = LeaveType.query.filter_by(id=type_id, company_id=get_active_company_id()).first_or_404()
    my_company = get_manageable_company_id(request.form.get('company_id', type=int))
    lt.name = request.form.get('name', lt.name)
    lt.days_per_year = request.form.get('days_per_year', type=int, default=lt.days_per_year)
    lt.color = request.form.get('color', lt.color)
    lt.description = request.form.get('description', lt.description)
    lt.is_active = bool(request.form.get('is_active', lt.is_active))
    lt.requires_attachment = bool(request.form.get('requires_attachment'))
    new_label = request.form.get('attachment_label', '').strip()
    lt.attachment_label = new_label if new_label else 'Surat Dokter / Bukti Pendukung'
    lt.company_id = my_company
    db.session.commit()
    audit_log('admin.leave_type_updated', 'leave_type', lt.id, details={'name': lt.name, 'days': lt.days_per_year}, company_id=my_company)
    flash(translate(f'Jenis cuti {lt.name} berhasil diperbarui!'), 'success')
    return redirect(url_for('main.admin_leave_types'))

@main_bp.route('/admin/leave-types/archive/<int:type_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_archive_leave_type(type_id):
    company_id = get_active_company_id()
    leave_type = LeaveType.query.filter_by(id=type_id, company_id=company_id).first_or_404()
    leave_type.is_active = False
    audit_log('admin.leave_type_archived', 'leave_type', leave_type.id, details={'name': leave_type.name}, company_id=company_id)
    db.session.commit()
    flash(translate(f'Jenis cuti {leave_type.name} berhasil diarsipkan.'), 'success')
    return redirect(url_for('main.admin_leave_types'))

@main_bp.route('/admin/leave-types/unarchive/<int:type_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_unarchive_leave_type(type_id):
    company_id = get_active_company_id()
    leave_type = LeaveType.query.filter_by(id=type_id, company_id=company_id).first_or_404()
    leave_type.is_active = True
    audit_log('admin.leave_type_unarchived', 'leave_type', leave_type.id, details={'name': leave_type.name}, company_id=company_id)
    db.session.commit()
    flash(translate(f'Jenis cuti {leave_type.name} berhasil dipulihkan dari arsip.'), 'success')
    return redirect(url_for('main.admin_leave_types', archived=1))

@main_bp.route('/admin/leave-types/delete/<int:type_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_delete_leave_type(type_id):
    company_id = get_active_company_id()
    leave_type = LeaveType.query.filter_by(id=type_id, company_id=company_id).first_or_404()
    has_requests = LeaveRequest.query.filter_by(company_id=company_id, leave_type_id=leave_type.id).first() is not None
    has_grants = LeaveGrant.query.filter_by(company_id=company_id, leave_type_id=leave_type.id).first() is not None

    if has_requests or has_grants:
        if leave_type.is_active:
            leave_type.is_active = False
            audit_log('admin.leave_type_archived', 'leave_type', leave_type.id, details={'name': leave_type.name}, company_id=company_id)
            db.session.commit()
        flash(translate('This leave type is already in use and has been archived.'), 'warning')
        return redirect(url_for('main.admin_leave_types'))

    ApprovalConfig.query.filter_by(company_id=company_id, leave_type_id=leave_type.id).delete(synchronize_session=False)
    LeaveBalance.query.filter_by(company_id=company_id, leave_type_id=leave_type.id).delete(synchronize_session=False)
    name = leave_type.name
    audit_log('admin.leave_type_deleted', 'leave_type', leave_type.id, details={'name': name}, company_id=company_id)
    db.session.delete(leave_type)
    db.session.commit()
    flash(translate(f'Jenis cuti {name} berhasil dihapus.'), 'success')
    return redirect(url_for('main.admin_leave_types'))

# ── ADMIN: DEPARTMENTS ──

@main_bp.route('/admin/departments')
@login_required
@role_required('manager', 'hr', 'admin')
def admin_departments():
    my_company = get_active_company_id()
    query = Department.query.filter_by(company_id=my_company)
    q = request.args.get('q', '').strip()
    if q:
        query = query.filter(Department.name.ilike(f'%{q}%'))
    head_id = request.args.get('head_id', '')
    if head_id == 'none':
        query = query.filter(Department.head_id.is_(None))
    elif head_id:
        query = query.filter_by(head_id=int(head_id))

    page, per_page, per_page_str = get_pagination_args(default=20)
    pagination = query.order_by(Department.name).paginate(page=page, per_page=per_page, error_out=False)
    departments = pagination.items
    managers = User.query.filter(User.company_id == my_company, User.is_active == True, User.is_deleted == False, User.role.in_(['manager', 'hr', 'admin'])).order_by(User.name).all()
    return render_template('admin/departments.html', departments=departments, pagination=pagination, per_page_str=per_page_str, managers=managers, companies=Company.query.filter_by(is_active=True).order_by(Company.name).all())

@main_bp.route('/admin/departments/add', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_add_department():
    my_company = get_manageable_company_id(request.form.get('company_id', type=int))
    name = request.form.get('name', '').strip()
    head_id = request.form.get('head_id', type=int)

    if not name:
        flash(translate('Department name is required.'), 'danger')
        return redirect(url_for('main.admin_departments'))

    dept = Department(name=name, company_id=my_company, head_id=head_id)
    db.session.add(dept)
    db.session.commit()
    audit_log('admin.department_created', 'department', dept.id, details={'name': dept.name}, company_id=my_company)
    flash(translate(f'Departemen {name} berhasil ditambahkan!'), 'success')
    return redirect(url_for('main.admin_departments'))

@main_bp.route('/admin/departments/edit/<int:dept_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_edit_department(dept_id):
    dept = Department.query.filter_by(id=dept_id, company_id=get_active_company_id()).first_or_404()
    target_company_id = get_manageable_company_id(request.form.get('company_id', type=int))
    dept.name = request.form.get('name', dept.name)
    head_id = request.form.get('head_id', type=int)
    dept.company_id = target_company_id
    dept.head_id = head_id if User.query.filter_by(id=head_id, company_id=target_company_id).first() else None
    db.session.commit()
    audit_log('admin.department_updated', 'department', dept.id, details={'name': dept.name}, company_id=target_company_id)
    flash(translate(f'Departemen {dept.name} berhasil diperbarui!'), 'success')
    return redirect(url_for('main.admin_departments'))

@main_bp.route('/admin/departments/delete/<int:dept_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_delete_department(dept_id):
    dept = Department.query.filter_by(id=dept_id, company_id=get_active_company_id()).first_or_404()
    dept_name = dept.name
    dept_id_val = dept.id
    dept_comp = dept.company_id
    User.query.filter_by(department_id=dept.id).update({'department_id': None})
    db.session.delete(dept)
    db.session.commit()
    audit_log('admin.department_deleted', 'department', dept_id_val, details={'name': dept_name}, company_id=dept_comp)
    flash(translate(f'Departemen {dept_name} berhasil dihapus!'), 'success')
    return redirect(url_for('main.admin_departments'))

# ── ADMIN: APPROVAL CONFIGS ──

@main_bp.route('/admin/approval-configs/<int:type_id>')
@login_required
@role_required('manager', 'hr', 'admin')
def admin_approval_configs(type_id):
    my_company = get_active_company_id()
    leave_type = LeaveType.query.filter_by(id=type_id, company_id=my_company).first_or_404()
    configs = ApprovalConfig.query.filter(
        ApprovalConfig.company_id == my_company,
        (ApprovalConfig.leave_type_id == type_id) | (ApprovalConfig.leave_type_id.is_(None))
    ).order_by(ApprovalConfig.level).all()
    roles = [('manager', 'Manager'), ('hr', 'HR'), ('director', 'Direktur')]
    return render_template('admin/approval_configs.html', leave_type=leave_type, configs=configs, roles=roles)

@main_bp.route('/admin/approval-configs/add/<int:type_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_add_approval_config(type_id):
    my_company = get_active_company_id()
    level = request.form.get('level', type=int)
    approver_role = request.form.get('approver_role')

    if not level or not approver_role:
        flash(translate('Level and role are required.'), 'danger')
        return redirect(url_for('main.admin_approval_configs', type_id=type_id))

    leave_type = LeaveType.query.filter_by(id=type_id, company_id=my_company).first_or_404()
    config = ApprovalConfig(company_id=my_company, leave_type_id=leave_type.id, level=level, approver_role=approver_role)
    db.session.add(config)
    db.session.commit()
    audit_log('admin.approval_config_added', 'approval_config', config.id, details={'leave_type_id': type_id, 'level': level, 'role': approver_role}, company_id=my_company)
    flash(translate('Approval level added.'), 'success')
    return redirect(url_for('main.admin_approval_configs', type_id=type_id))

@main_bp.route('/admin/approval-configs/delete/<int:config_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def admin_delete_approval_config(config_id):
    config = ApprovalConfig.query.filter_by(id=config_id, company_id=get_active_company_id()).first_or_404()
    type_id = config.leave_type_id
    config_id_val = config.id
    config_level = config.level
    config_comp = config.company_id
    db.session.delete(config)
    db.session.commit()
    audit_log('admin.approval_config_deleted', 'approval_config', config_id_val, details={'leave_type_id': type_id, 'level': config_level}, company_id=config_comp)
    flash(translate('Approval level deleted.'), 'success')
    return redirect(url_for('main.admin_approval_configs', type_id=type_id))

# ── ADMIN: HOLIDAY MANAGEMENT ──

@main_bp.route('/admin/holidays/sync', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def sync_holidays():
    company_id = get_active_company_id()
    sync_company_holidays(company_id)
    flash(translate('National holidays and collective leave list synchronized! ✅'), 'success')
    return redirect(url_for('main.long_weekend'))

@main_bp.route('/admin/holidays/add', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def add_holiday():
    company_id = get_active_company_id()
    h_date_str = request.form.get('holiday_date', '').strip()
    name = request.form.get('name', '').strip()
    kind = request.form.get('kind', 'company').strip()

    if not h_date_str or not name:
        flash(translate('Date and holiday name are required.'), 'danger')
        return redirect(url_for('main.long_weekend'))

    try:
        h_date = datetime.strptime(h_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash(translate('Date format is invalid.'), 'danger')
        return redirect(url_for('main.long_weekend'))

    existing = PublicHoliday.query.filter_by(company_id=company_id, holiday_date=h_date).first()
    if existing:
        existing.name = name
        existing.kind = kind
        existing.is_active = True
        flash(translate('Holiday updated! ✅'), 'success')
    else:
        new_h = PublicHoliday(
            company_id=company_id,
            holiday_date=h_date,
            name=name,
            kind=kind,
            is_active=True
        )
        db.session.add(new_h)
        flash(translate('New holiday added! ✅'), 'success')

    db.session.commit()
    return redirect(url_for('main.long_weekend', year=h_date.year))

@main_bp.route('/admin/holidays/<int:holiday_id>/delete', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def delete_holiday(holiday_id):
    company_id = get_active_company_id()
    h = PublicHoliday.query.filter_by(id=holiday_id, company_id=company_id).first_or_404()
    year = h.holiday_date.year
    db.session.delete(h)
    db.session.commit()
    flash(translate('Holiday deleted! 🗑️'), 'success')
    return redirect(url_for('main.long_weekend', year=year))

# ── ADMIN: EXCEL REPORT EXPORT ──

@main_bp.route('/admin/reports/export')
@login_required
@role_required('manager', 'hr', 'admin')
def admin_export_leave_report():
    from services.export_service import generate_leave_report_excel
    my_company = get_active_company_id()
    year = request.args.get('year', type=int) or date.today().year
    department_id = request.args.get('department_id', type=int)

    company = db.session.get(Company, my_company)
    company_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', company.name.lower()) if company else "company"
    filename = f"Laporan_Cuti_{company_slug}_{year}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    excel_buffer = generate_leave_report_excel(my_company, year=year, department_id=department_id)
    audit_log('reports.exported', 'company', my_company, details={'year': year, 'department_id': department_id}, company_id=my_company)

    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

# ── ADMIN: SYSTEM & DATABASE BACKUP ──

@main_bp.route('/admin/backup/download')
@login_required
@role_required('admin')
def admin_download_backup():
    from services.backup_service import generate_system_backup_json, generate_system_backup_sql, generate_full_backup_zip
    backup_format = request.args.get('format', 'zip').lower().strip()
    my_company = get_active_company_id()
    company = db.session.get(Company, my_company)
    company_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', company.name.lower()) if company else "system"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if backup_format == 'json':
        buffer = generate_system_backup_json(company_id=my_company)
        filename = f"backup_triton_people_{company_slug}_{timestamp}.json"
        mimetype = "application/json"
    elif backup_format == 'sql':
        buffer = generate_system_backup_sql(company_id=my_company)
        filename = f"backup_triton_people_{company_slug}_{timestamp}.sql"
        mimetype = "application/sql"
    else:
        buffer = generate_full_backup_zip(company_id=my_company)
        filename = f"backup_triton_people_{company_slug}_{timestamp}.zip"
        mimetype = "application/zip"

    audit_log('system.backup_downloaded', 'company', my_company, details={'format': backup_format, 'filename': filename}, company_id=my_company)

    return send_file(
        buffer,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )

# ── ADMIN: AUDIT LOGS ──

@main_bp.route('/admin/audit-logs')
@login_required
@role_required('admin')
def admin_audit_logs():
    my_company = get_active_company_id()

    category = request.args.get('category', 'all').strip()
    actor_id = request.args.get('actor_id', type=int)
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    q = request.args.get('q', '').strip()
    page, per_page, per_page_str = get_pagination_args(default=20)

    query = AuditLog.query.filter(
        (AuditLog.company_id == my_company) | (AuditLog.company_id.is_(None))
    )

    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)

    if category and category != 'all':
        if category == 'auth':
            query = query.filter(AuditLog.action.startswith('auth.'))
        elif category == 'employee':
            query = query.filter(AuditLog.action.startswith('admin.employee_') | (AuditLog.action == 'user.profile_updated') | (AuditLog.action == 'user.avatar_uploaded') | (AuditLog.action == 'user.avatar_deleted'))
        elif category == 'leave':
            query = query.filter(AuditLog.action.startswith('leave.') | (AuditLog.action == 'admin.leave_granted') | AuditLog.action.startswith('admin.leave_type_') | AuditLog.action.startswith('approval_history.'))
        elif category == 'department':
            query = query.filter(AuditLog.action.startswith('admin.department_'))
        elif category == 'company':
            query = query.filter(AuditLog.action.startswith('admin.company_') | AuditLog.action.startswith('company.') | (AuditLog.action == 'workspace.company_switched'))
        elif category == 'system':
            query = query.filter(AuditLog.action.startswith('system.') | AuditLog.action.startswith('reports.') | AuditLog.action.startswith('import.') | AuditLog.action.startswith('security.') | (AuditLog.action == 'holiday.synced'))

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= start_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(AuditLog.created_at <= end_date)
        except ValueError:
            pass

    if q:
        search_fmt = f"%{q}%"
        query = query.filter(
            (AuditLog.action.ilike(search_fmt)) |
            (AuditLog.details.ilike(search_fmt)) |
            (AuditLog.target_type.ilike(search_fmt)) |
            (AuditLog.ip_address.ilike(search_fmt))
        )

    # Metrics
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    total_logs_count = query.count()
    today_count = AuditLog.query.filter((AuditLog.company_id == my_company) | (AuditLog.company_id.is_(None)), AuditLog.created_at >= today_start).count()
    auth_count = AuditLog.query.filter((AuditLog.company_id == my_company) | (AuditLog.company_id.is_(None)), AuditLog.action.startswith('auth.')).count()
    data_ops_count = AuditLog.query.filter((AuditLog.company_id == my_company) | (AuditLog.company_id.is_(None)), ~AuditLog.action.startswith('auth.')).count()

    pagination = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    actors = User.query.filter_by(company_id=my_company).order_by(User.name.asc()).all()

    return render_template(
        'admin/audit_logs.html',
        logs=pagination.items,
        pagination=pagination,
        per_page_str=per_page_str,
        actors=actors,
        category=category,
        actor_id=actor_id,
        start_date=start_date_str,
        end_date=end_date_str,
        q=q,
        total_logs_count=total_logs_count,
        today_count=today_count,
        auth_count=auth_count,
        data_ops_count=data_ops_count
    )

@main_bp.route('/admin/audit-logs/export')
@login_required
@role_required('admin')
def admin_export_audit_logs():
    from services.export_service import generate_audit_logs_excel
    my_company = get_active_company_id()
    company = db.session.get(Company, my_company)
    company_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', company.name.lower()) if company else "company"

    category = request.args.get('category', 'all').strip()
    actor_id = request.args.get('actor_id', type=int)
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    q = request.args.get('q', '').strip()

    query = AuditLog.query.filter(
        (AuditLog.company_id == my_company) | (AuditLog.company_id.is_(None))
    )

    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)

    if category and category != 'all':
        if category == 'auth':
            query = query.filter(AuditLog.action.startswith('auth.'))
        elif category == 'employee':
            query = query.filter(AuditLog.action.startswith('admin.employee_') | (AuditLog.action == 'user.profile_updated') | (AuditLog.action == 'user.avatar_uploaded') | (AuditLog.action == 'user.avatar_deleted'))
        elif category == 'leave':
            query = query.filter(AuditLog.action.startswith('leave.') | (AuditLog.action == 'admin.leave_granted') | AuditLog.action.startswith('admin.leave_type_') | AuditLog.action.startswith('approval_history.'))
        elif category == 'department':
            query = query.filter(AuditLog.action.startswith('admin.department_'))
        elif category == 'company':
            query = query.filter(AuditLog.action.startswith('admin.company_') | AuditLog.action.startswith('company.') | (AuditLog.action == 'workspace.company_switched'))
        elif category == 'system':
            query = query.filter(AuditLog.action.startswith('system.') | AuditLog.action.startswith('reports.') | AuditLog.action.startswith('import.') | AuditLog.action.startswith('security.') | (AuditLog.action == 'holiday.synced'))

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(AuditLog.created_at >= start_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(AuditLog.created_at <= end_date)
        except ValueError:
            pass

    if q:
        search_fmt = f"%{q}%"
        query = query.filter(
            (AuditLog.action.ilike(search_fmt)) |
            (AuditLog.details.ilike(search_fmt)) |
            (AuditLog.target_type.ilike(search_fmt)) |
            (AuditLog.ip_address.ilike(search_fmt))
        )

    logs = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(5000).all()
    excel_buffer = generate_audit_logs_excel(my_company, logs)
    filename = f"Audit_Log_{company_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    audit_log('reports.exported', 'company', my_company, details={'type': 'audit_logs', 'count': len(logs)}, company_id=my_company)

    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

