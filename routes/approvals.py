import json
from datetime import datetime, date
from sqlalchemy import or_
from flask import render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from extensions import db
from models.user import User, Department
from models.company import Company
from models.leave import LeaveRequest, LeaveBalance, LeaveType
from models.approval import ApprovalConfig
from core.i18n import translate
from core.auth import get_active_company_id, role_required
from services.audit_service import audit_log
from services.notification_service import send_notification
from services.import_service import parse_file_headers_and_preview, execute_leave_history_import
from core.pagination import get_pagination_args
from core.time_util import utcnow
from routes.common import main_bp

@main_bp.route('/approvals')
@login_required
@role_required('manager', 'hr', 'admin')
def approvals():
    my_company = get_active_company_id()
    if current_user.role == 'manager':
        subordinate_ids = db.session.query(User.id).filter(User.manager_id == current_user.id)
        dept_ids = db.session.query(Department.id).filter(Department.head_id == current_user.id)
        dept_member_ids = db.session.query(User.id).filter(User.department_id.in_(dept_ids))
        query = LeaveRequest.query.filter(
            LeaveRequest.status == 'pending',
            LeaveRequest.company_id == my_company,
            LeaveRequest.current_approval_level == 1,
            or_(
                LeaveRequest.employee_id.in_(subordinate_ids),
                LeaveRequest.employee_id.in_(dept_member_ids)
            )
        )
    else:
        query = LeaveRequest.query.filter_by(
            status='pending',
            company_id=my_company
        )

    page, per_page, per_page_str = get_pagination_args(default=20)
    pagination = query.order_by(LeaveRequest.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    pending_requests = pagination.items

    return render_template('approvals.html', pending_requests=pending_requests, requests=pending_requests, pagination=pagination, per_page_str=per_page_str)

@main_bp.route('/approval-history')
@login_required
@role_required('manager', 'hr', 'admin')
def approval_history():
    show_archived = request.args.get('archived') == '1'
    my_company = get_active_company_id()
    
    query = LeaveRequest.query.filter(
        LeaveRequest.company_id == my_company,
        LeaveRequest.is_archived == show_archived
    )

    if current_user.role == 'manager':
        subordinate_ids = db.session.query(User.id).filter(User.manager_id == current_user.id)
        dept_ids = db.session.query(Department.id).filter(Department.head_id == current_user.id)
        dept_member_ids = db.session.query(User.id).filter(User.department_id.in_(dept_ids))
        query = query.filter(
            or_(
                LeaveRequest.employee_id.in_(subordinate_ids),
                LeaveRequest.employee_id.in_(dept_member_ids),
                LeaveRequest.approved_by == current_user.id,
                LeaveRequest.employee_id == current_user.id
            )
        )

    # Year filter
    year_filter = request.args.get('year', type=int)
    if year_filter:
        query = query.filter(
            LeaveRequest.start_date >= date(year_filter, 1, 1),
            LeaveRequest.start_date <= date(year_filter, 12, 31)
        )

    # Status filter
    status_filter = request.args.get('status', '').strip()
    if status_filter in ('approved', 'rejected', 'pending'):
        query = query.filter(LeaveRequest.status == status_filter)

    # Employee filter
    employee_filter = request.args.get('employee_id', type=int)
    if employee_filter:
        query = query.filter(LeaveRequest.employee_id == employee_filter)

    # Leave type filter
    leave_type_filter = request.args.get('leave_type_id', type=int)
    if leave_type_filter:
        query = query.filter(LeaveRequest.leave_type_id == leave_type_filter)

    page, per_page, per_page_str = get_pagination_args(default=20)
    pagination = query.order_by(LeaveRequest.start_date.desc(), LeaveRequest.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    history = pagination.items

    # Get distinct years
    current_year = date.today().year
    distinct_years = [current_year, current_year - 1, current_year - 2]
    all_dates = db.session.query(LeaveRequest.start_date).filter_by(company_id=my_company).all()
    for (d,) in all_dates:
        if d and d.year not in distinct_years:
            distinct_years.append(d.year)
    years = sorted(list(set(distinct_years)), reverse=True)

    employees = User.query.filter_by(company_id=my_company, is_active=True).order_by(User.name).all()
    leave_types = LeaveType.query.filter_by(company_id=my_company, is_active=True).order_by(LeaveType.name).all()

    return render_template(
        'approval_history.html',
        history=history,
        requests=history,
        pagination=pagination,
        per_page_str=per_page_str,
        show_archived=show_archived,
        years=years,
        year_filter=year_filter,
        status_filter=status_filter,
        employee_filter=employee_filter,
        leave_type_filter=leave_type_filter,
        employees=employees,
        leave_types=leave_types
    )

@main_bp.route('/approval-history/archive/<int:request_id>', methods=['POST'])
@login_required
@role_required('admin')
def archive_approval_history(request_id):
    my_company = get_active_company_id()
    req = LeaveRequest.query.filter_by(id=request_id, company_id=my_company).first_or_404()
    req.is_archived = True
    audit_log('approval_history.archived', 'leave_request', req.id)
    db.session.commit()
    flash(translate('Riwayat approval berhasil diarsipkan!'), 'success')
    return redirect(request.referrer or url_for('main.approval_history'))

@main_bp.route('/approval-history/unarchive/<int:request_id>', methods=['POST'])
@login_required
@role_required('admin')
def unarchive_approval_history(request_id):
    my_company = get_active_company_id()
    req = LeaveRequest.query.filter_by(id=request_id, company_id=my_company).first_or_404()
    req.is_archived = False
    audit_log('approval_history.unarchived', 'leave_request', req.id)
    db.session.commit()
    flash(translate('Riwayat approval berhasil dikembalikan dari arsip!'), 'success')
    return redirect(request.referrer or url_for('main.approval_history', archived=1))

@main_bp.route('/approve/<int:request_id>', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def approve_leave(request_id):
    req = LeaveRequest.query.filter_by(
        id=request_id,
        company_id=get_active_company_id()
    ).with_for_update().first_or_404()

    action = request.form.get('action')
    expected_level_raw = request.form.get('expected_level')

    if req.status != 'pending':
        flash(translate('Pengajuan ini sudah diproses.'), 'warning')
        return redirect(url_for('main.approvals'))

    try:
        expected_level = int(expected_level_raw)
    except (TypeError, ValueError):
        expected_level = None

    if expected_level != req.current_approval_level:
        flash(translate('Status approval sudah berubah. Muat ulang halaman dan coba lagi.'), 'warning')
        return redirect(url_for('main.approvals'))

    config = ApprovalConfig.query.filter(
        ApprovalConfig.company_id == req.company_id,
        (ApprovalConfig.leave_type_id == req.leave_type_id) | (ApprovalConfig.leave_type_id.is_(None)),
        ApprovalConfig.level == req.current_approval_level
    ).order_by(ApprovalConfig.leave_type_id.desc()).first()

    if current_user.role == 'manager':
        # Manager can approve if there is no config (default level 1) or config is explicitly for manager
        if config and config.approver_role not in ('manager', 'hr'):
            abort(403)
        # Check if the employee is a direct subordinate or belongs to a department headed by this manager
        is_subordinate = (req.employee.manager_id == current_user.id)
        is_dept_head = False
        if req.employee.department_id:
            dept = Department.query.filter_by(id=req.employee.department_id, head_id=current_user.id).first()
            if dept:
                is_dept_head = True
        if not (is_subordinate or is_dept_head):
            abort(403)
    elif current_user.role in ('hr', 'admin'):
        # HR and Admin have company-wide authority to approve/reject all leave requests across levels and types
        pass
    else:
        abort(403)

    notes = request.form.get('notes', '')

    if action == 'approve':
        req.approved_by = current_user.id
        req.approved_at = utcnow()
        req.notes = notes

        if req.current_approval_level >= req.max_approval_level:
            req.status = 'approved'
            this_year = req.start_date.year
            bal = LeaveBalance.query.filter_by(employee_id=req.employee_id, company_id=req.company_id, leave_type_id=req.leave_type_id, year=this_year).first()
            if bal:
                bal.used_days += req.duration_days
                bal.pending_days = max(0, bal.pending_days - req.duration_days)
            flash(translate(f'Cuti {req.employee.name} disetujui ✅'), 'success')
            company = db.session.get(Company, req.company_id)
            send_notification(company, 'approve', req)
        else:
            req.current_approval_level += 1
            req.status = 'pending'
            req.approved_by = None
            req.approved_at = None
            flash(translate(f'Level {req.current_approval_level - 1} disetujui - menunggu approval level {req.current_approval_level}.'), 'info')

    elif action == 'reject':
        req.status = 'rejected'
        req.notes = notes
        this_year = req.start_date.year
        bal = LeaveBalance.query.filter_by(employee_id=req.employee_id, company_id=req.company_id, leave_type_id=req.leave_type_id, year=this_year).first()
        if bal:
            bal.pending_days = max(0, bal.pending_days - req.duration_days)
        flash(translate(f'Cuti {req.employee.name} ditolak ❌'), 'warning')
        company = db.session.get(Company, req.company_id)
        send_notification(company, 'reject', req)

    else:
        flash(translate('Aksi tidak valid.'), 'danger')
        return redirect(url_for('main.approvals'))

    audit_log('leave.request_' + action, 'leave_request', req.id, details={'status': req.status}, company_id=req.company_id)
    db.session.commit()
    return redirect(url_for('main.approvals'))

# ── IMPORT: LEAVE REQUEST HISTORY ──

@main_bp.route('/approvals/history/import/preview', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def approval_history_import_preview():
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

@main_bp.route('/approvals/history/import/execute', methods=['POST'])
@login_required
@role_required('manager', 'hr', 'admin')
def approval_history_import_execute():
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

    sync_balances = request.form.get('sync_balances') in ('1', 'true', 'True', True)
    my_company = get_active_company_id()

    try:
        result = execute_leave_history_import(
            file.stream,
            file.filename,
            mapping,
            my_company,
            current_user.id,
            sync_balances=sync_balances
        )
        return jsonify(result)
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

