import os
import uuid
from datetime import date
from flask import render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models.user import User
from models.company import Company
from models.leave import LeaveType, LeaveRequest, LeaveBalance
from models.approval import ApprovalConfig
from models.holiday import PublicHoliday
from core.i18n import translate
from core.auth import get_active_company_id, role_required
from services.audit_service import audit_log
from services.notification_service import send_notification
from services.holiday_service import calculate_long_weekends
from services.leave_service import calculate_working_duration
from routes.common import main_bp

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5 MB

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _get_upload_dir():
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'leave_attachments')
    os.makedirs(base, exist_ok=True)
    return base

@main_bp.route('/apply', methods=['GET', 'POST'])
@login_required
@role_required('employee', 'manager', 'hr')
def apply_leave():
    this_year = date.today().year
    my_company = get_active_company_id()
    leave_types = LeaveType.query.filter_by(is_active=True, company_id=my_company).all()
    balances = {b.leave_type_id: b for b in LeaveBalance.query.filter_by(employee_id=current_user.id, company_id=my_company, year=this_year).all()}
    max_date = date(2030, 12, 31)
    active_company = db.session.get(Company, my_company)
    delegate_enabled = bool(active_company and active_company.delegate_enabled)
    employees = User.query.filter(User.id != current_user.id, User.is_active == True, User.company_id == my_company).order_by(User.name).all() if delegate_enabled else []

    def _lt_json():
        return {lt.id: {'requires_attachment': bool(lt.requires_attachment), 'attachment_label': lt.attachment_label or ''} for lt in leave_types}

    holidays = PublicHoliday.query.filter_by(company_id=my_company, is_active=True).all()
    holidays_json = [h.holiday_date.isoformat() for h in holidays]

    def _render_apply(**kwargs):
        return render_template('apply.html', leave_types=leave_types, balances=balances,
                               max_date=max_date, employees=employees,
                               delegate_enabled=delegate_enabled, leave_types_json=_lt_json(),
                               holidays_json=holidays_json, **kwargs)

    if request.method == 'POST':
        leave_type_id = request.form.get('leave_type', type=int)
        day_part = request.form.get('day_part', 'full').strip().lower()
        if day_part not in ('morning', 'afternoon', 'full'):
            day_part = 'full'
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip() if day_part == 'full' else start_date_str
        reason = request.form.get('reason', '')
        delegate_id = request.form.get('delegate_id', type=int) if delegate_enabled else None

        if not leave_type_id or not start_date_str or (day_part == 'full' and not end_date_str):
            flash(translate('Please complete all required fields.'), 'danger')
            return _render_apply()

        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
        except:
            flash(translate('Date format is invalid.'), 'danger')
            return _render_apply()

        if end_date < start_date:
            flash(translate('End date must be after or equal to start date.'), 'danger')
            return _render_apply()

        if start_date < date.today():
            flash(translate('You cannot request leave in the past.'), 'danger')
            return _render_apply()

        # Check overlapping leave
        overlapping_reqs = LeaveRequest.query.filter(
            LeaveRequest.employee_id == current_user.id,
            LeaveRequest.company_id == my_company,
            LeaveRequest.status.in_(['pending', 'approved']),
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date
        ).all()

        has_conflict = False
        for ex in overlapping_reqs:
            ex_part = getattr(ex, 'day_part', 'full') or 'full'
            if day_part == 'full' or ex_part == 'full':
                has_conflict = True
                break
            if day_part == ex_part:
                has_conflict = True
                break

        if has_conflict:
            flash(translate('You already have a leave request on those dates.'), 'danger')
            return _render_apply()

        # Check balance
        lt = LeaveType.query.filter_by(id=leave_type_id, company_id=my_company, is_active=True).first()
        if not lt:
            flash(translate('Leave type is not available.'), 'danger')
            return _render_apply()
        if delegate_id and not User.query.filter(User.id == delegate_id, User.id != current_user.id, User.company_id == my_company, User.is_active == True).first():
            flash(translate('Delegate is not available.'), 'danger')
            return _render_apply()

        # Check attachment requirement
        upload_file = request.files.get('attachment')
        saved_filename = None
        original_name = None
        if lt.requires_attachment:
            if not upload_file or upload_file.filename == '':
                flash(translate('Lampiran wajib diunggah untuk jenis cuti ini.'), 'danger')
                return _render_apply()
            if not _allowed_file(upload_file.filename):
                flash(translate('Format file tidak didukung. Gunakan PDF, JPG, atau PNG.'), 'danger')
                return _render_apply()
            upload_file.seek(0, 2)
            size = upload_file.tell()
            upload_file.seek(0)
            if size > MAX_ATTACHMENT_BYTES:
                flash(translate('Ukuran file maksimal 5 MB.'), 'danger')
                return _render_apply()
            ext = upload_file.filename.rsplit('.', 1)[1].lower()
            saved_filename = f"{uuid.uuid4().hex}.{ext}"
            original_name = secure_filename(upload_file.filename)

        bal = balances.get(leave_type_id)
        duration = calculate_working_duration(
            start_date, end_date,
            company_id=my_company,
            day_part=day_part,
            exclude_weekends=True,
            exclude_holidays=True
        )
        if duration <= 0:
            flash(translate('Selected dates fall entirely on weekends or public holidays (0 working days).'), 'danger')
            return _render_apply()

        if lt and bal and lt.days_per_year > 0:
            remaining = bal.total_days - bal.used_days - bal.pending_days
            if duration > remaining:
                rem_str = f"{remaining:g}"
                flash(translate(f'Cuti {lt.name} Anda tidak mencukupi. Sisa: {rem_str} hari.'), 'danger')
                return _render_apply()

        # Determine approval levels
        approval_configs = ApprovalConfig.query.filter(
            ApprovalConfig.company_id == my_company,
            (ApprovalConfig.leave_type_id == leave_type_id) | (ApprovalConfig.leave_type_id.is_(None))
        ).order_by(ApprovalConfig.level).all()
        max_level = max((c.level for c in approval_configs if c.leave_type_id == leave_type_id),
                      default=max((c.level for c in approval_configs if c.leave_type_id is None), default=1))

        req = LeaveRequest(
            employee_id=current_user.id,
            leave_type_id=leave_type_id,
            company_id=my_company,
            start_date=start_date,
            end_date=end_date,
            day_part=day_part,
            duration_days=duration,
            reason=reason,
            delegate_id=delegate_id if delegate_id else None,
            attachment_path=saved_filename,
            attachment_original_name=original_name,
            status='pending',
            current_approval_level=1,
            max_approval_level=max_level
        )
        db.session.add(req)
        if saved_filename and upload_file:
            upload_file.save(os.path.join(_get_upload_dir(), saved_filename))
        if bal:
            bal.pending_days += duration
        audit_log('leave.request_submitted', 'leave_request', req.id, details={'duration_days': duration, 'day_part': day_part, 'leave_type_id': leave_type_id}, company_id=my_company)
        db.session.commit()

        company = db.session.get(Company, my_company)
        send_notification(company, 'submit', req)

        flash(translate('Leave request submitted. Waiting for approval.'), 'success')
        return redirect(url_for('main.dashboard'))

    return _render_apply()

@main_bp.route('/leave-attachment/<int:request_id>')
@login_required
def download_leave_attachment(request_id):
    my_company = get_active_company_id()
    req = LeaveRequest.query.filter_by(id=request_id, company_id=my_company).first_or_404()
    # Allow: own employee, approver roles, or admin
    is_own = (req.employee_id == current_user.id)
    is_approver = current_user.role in ('manager', 'hr', 'admin')
    if not (is_own or is_approver):
        abort(403)
    if not req.attachment_path:
        abort(404)
    return send_from_directory(
        _get_upload_dir(),
        req.attachment_path,
        as_attachment=True,
        download_name=req.attachment_original_name or req.attachment_path
    )

@main_bp.route('/history')
@login_required
def history():
    year_filter = request.args.get('year', type=int)
    status_filter = request.args.get('status', '')
    this_year = date.today().year
    if not year_filter:
        year_filter = this_year

    years = list(range(this_year - 2, this_year + 3))
    my_company = get_active_company_id()

    query = LeaveRequest.query.filter(
        LeaveRequest.employee_id == current_user.id,
        LeaveRequest.company_id == my_company,
        db.extract('year', LeaveRequest.start_date) == year_filter
    )
    if status_filter:
        query = query.filter_by(status=status_filter)

    from core.pagination import get_pagination_args
    page, per_page, per_page_str = get_pagination_args(default=20)
    pagination = query.order_by(LeaveRequest.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    requests = pagination.items

    balances = LeaveBalance.query.filter_by(employee_id=current_user.id, company_id=my_company, year=year_filter).all()

    return render_template(
        'history.html',
        requests=requests,
        pagination=pagination,
        per_page_str=per_page_str,
        years=years,
        year_filter=year_filter,
        status_filter=status_filter,
        balances=balances
    )

@main_bp.route('/long-weekend')
@login_required
def long_weekend():
    company_id = get_active_company_id()
    years = [2025, 2026, 2027]
    requested_year = request.args.get('year', type=int, default=date.today().year)
    year = requested_year if requested_year in years else date.today().year

    suggestions, holidays = calculate_long_weekends(company_id, year)
    return render_template('long_weekend.html', year=year, years=years, suggestions=suggestions, holidays=holidays)

@main_bp.route('/leaves/<int:request_id>/slip')
@login_required
def leave_slip(request_id):
    from datetime import datetime
    my_company = get_active_company_id()
    req = LeaveRequest.query.filter_by(id=request_id, company_id=my_company).first_or_404()

    is_owner = (req.employee_id == current_user.id)
    is_manager = (req.employee.manager_id == current_user.id) if req.employee else False
    is_admin_or_hr = (current_user.role in ('admin', 'hr'))

    if not (is_owner or is_manager or is_admin_or_hr):
        abort(403)

    company = db.session.get(Company, my_company)
    ref_number = f"LV-{req.start_date.strftime('%Y%m')}-{req.id:05d}"
    return render_template(
        'leave_slip.html',
        leave_request=req,
        company=company,
        ref_number=ref_number,
        printed_at=datetime.now(),
        printed_by=current_user
    )

@main_bp.route('/leaves/<int:request_id>/cancel', methods=['POST'])
@login_required
def cancel_leave(request_id):
    my_company = get_active_company_id()
    req = LeaveRequest.query.filter_by(id=request_id, company_id=my_company).first_or_404()

    is_owner = (req.employee_id == current_user.id)
    is_admin_or_hr = (current_user.role in ('admin', 'hr'))

    if not (is_owner or is_admin_or_hr):
        flash(translate('You do not have permission to cancel this leave request.'), 'danger')
        return redirect(url_for('main.history'))

    if req.status != 'pending':
        flash(translate('Only pending leave requests can be cancelled.'), 'danger')
        return redirect(url_for('main.history'))

    # Refund pending days in balance
    bal = LeaveBalance.query.filter_by(
        employee_id=req.employee_id,
        leave_type_id=req.leave_type_id,
        company_id=my_company,
        year=req.start_date.year
    ).first()
    if bal:
        bal.pending_days = max(0.0, bal.pending_days - req.duration_days)

    req.status = 'cancelled'
    cancel_reason = request.form.get('reason', '').strip()
    req.notes = f"Dibatalkan oleh {current_user.name}" + (f": {cancel_reason}" if cancel_reason else "")

    audit_log('leave.request_cancel', 'leave_request', req.id, company_id=my_company, details={
        'employee_id': req.employee_id,
        'leave_type_id': req.leave_type_id,
        'duration_days': req.duration_days,
        'reason': cancel_reason
    })
    db.session.commit()

    flash(translate('Leave request cancelled successfully.'), 'success')
    return redirect(url_for('main.history'))

