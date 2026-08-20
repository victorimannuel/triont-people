import os
import uuid
import secrets
from io import BytesIO
from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file, abort
from flask_login import login_required, current_user
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from extensions import db
from models.user import User
from models.company import Company
from models.leave import LeaveBalance, LeaveType, LeaveRequest
from models.auth import PasswordReset
from core.i18n import translate, normalize_language, SUPPORTED_LANGUAGES
from core.auth import get_active_company_id, role_required, validate_password_strength
from services.audit_service import audit_log
from services.notification_service import send_password_reset_otp_email
from routes.common import main_bp

ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_avatar_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS

@main_bp.route('/')
@login_required
def dashboard():
    this_year = date.today().year
    my_company = get_active_company_id()

    # My leave balances
    balances = LeaveBalance.query.filter_by(employee_id=current_user.id, company_id=my_company, year=this_year).all()
    balance_data = []
    for bal in balances:
        lt = LeaveType.query.filter_by(id=bal.leave_type_id, company_id=my_company).first()
        if lt:
            remaining = bal.total_days - bal.used_days - bal.pending_days
            balance_data.append({
                'id': lt.id,
                'name': lt.name,
                'color': lt.color,
                'icon': lt.icon,
                'total': bal.total_days,
                'used': bal.used_days,
                'pending': bal.pending_days,
                'remaining': max(0, remaining),
            })

    # My recent requests
    my_requests = LeaveRequest.query.filter_by(employee_id=current_user.id, company_id=my_company)\
        .order_by(LeaveRequest.created_at.desc()).limit(5).all()

    # Pending approvals (for managers/admins)
    pending_approvals = []
    if current_user.role in ('manager', 'hr', 'admin'):
        if current_user.role == 'manager':
            pending_approvals = LeaveRequest.query.filter(
                LeaveRequest.status == 'pending',
                LeaveRequest.company_id == my_company,
                LeaveRequest.current_approval_level == 1,
                LeaveRequest.employee_id.in_(
                    db.session.query(User.id).filter(User.manager_id == current_user.id)
                )
            ).order_by(LeaveRequest.created_at.desc()).all()
        else:
            pending_approvals = LeaveRequest.query.filter_by(status='pending', company_id=my_company)\
                .order_by(LeaveRequest.created_at.desc()).all()

    # Get all companies for admin chart filter
    companies = []
    if current_user.role == 'admin':
        companies = [{'id': c.id, 'name': c.name} for c in Company.query.filter_by(is_active=True).all()]

    # Team on leave this week (next 7 days)
    today = date.today()
    next_7_days = today + timedelta(days=7)
    team_leaves_query = LeaveRequest.query.filter(
        LeaveRequest.company_id == my_company,
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= next_7_days,
        LeaveRequest.end_date >= today
    ).order_by(LeaveRequest.start_date.asc(), LeaveRequest.end_date.asc()).all()

    team_leaves_this_week = []
    for req in team_leaves_query:
        if req.start_date <= today <= req.end_date:
            time_status = 'today'
        elif req.start_date == today + timedelta(days=1):
            time_status = 'tomorrow'
        else:
            time_status = 'upcoming'
        team_leaves_this_week.append({
            'request': req,
            'time_status': time_status,
        })

    return render_template('dashboard.html',
        balances=balance_data,
        my_requests=my_requests,
        pending_approvals=pending_approvals,
        team_leaves_this_week=team_leaves_this_week,
        today=today,
        this_year=this_year,
        companies=companies,
        current_company=my_company)

@main_bp.route('/workspace/language', methods=['POST'])
def select_language():
    language = request.form.get('language', 'en')
    if language not in SUPPORTED_LANGUAGES:
        language = 'en'
    session['language'] = language
    if current_user.is_authenticated:
        current_user.language_preference = language
        audit_log('user.language_updated', 'user', current_user.id, details={'language': language})
        db.session.commit()
    return jsonify(ok=True, language=language)

@main_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        language = normalize_language(request.form.get('language', current_user.language_preference))
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if name:
            current_user.name = name[:100]
        current_user.language_preference = language
        session['language'] = language

        tz = request.form.get('timezone', '').strip()
        if tz:
            current_user.timezone_preference = tz

        # Handle avatar upload
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            if not allowed_avatar_file(avatar_file.filename):
                flash(translate('Format file tidak didukung. Gunakan PNG, JPG, JPEG, WEBP, atau GIF.'), 'danger')
                return render_template('settings.html', calendar_token=current_user.get_calendar_token())
            
            ext = avatar_file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:12]}.{ext}"
            
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads', 'avatars')
            os.makedirs(uploads_dir, exist_ok=True)
            
            if current_user.avatar_path:
                old_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), current_user.avatar_path)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass
            
            dest_path = os.path.join(uploads_dir, unique_filename)
            avatar_file.save(dest_path)
            current_user.avatar_path = os.path.join('uploads', 'avatars', unique_filename)

        # Handle Direct Password Update (Option 1: Know current password)
        if current_password or new_password or confirm_password:
            if not current_user.check_password(current_password):
                flash(translate('Current password is incorrect.'), 'danger')
                return render_template('settings.html', calendar_token=current_user.get_calendar_token())
            if new_password != confirm_password:
                flash(translate('New passwords do not match.'), 'danger')
                return render_template('settings.html', calendar_token=current_user.get_calendar_token())
            if not validate_password_strength(new_password):
                flash(translate('Password must be at least 8 characters and include letters and numbers.'), 'danger')
                return render_template('settings.html', calendar_token=current_user.get_calendar_token())
            current_user.set_password(new_password)
            audit_log('user.password_updated', 'user', current_user.id, company_id=current_user.company_id)
            flash(translate('Password updated.'), 'success')
        else:
            flash(translate('Profile updated.'), 'success')

        audit_log('user.profile_updated', 'user', current_user.id, details={'language': language, 'timezone': current_user.timezone_preference})
        db.session.commit()
        return redirect(url_for('main.user_settings'))
    return render_template('settings.html', calendar_token=current_user.get_calendar_token())

@main_bp.route('/settings/password/request-otp', methods=['POST'])
@login_required
def request_password_change_otp():
    # Check cooldown (60 seconds)
    last_reset = PasswordReset.query.filter_by(user_id=current_user.id).order_by(PasswordReset.created_at.desc()).first()
    if last_reset and last_reset.created_at:
        elapsed = (datetime.utcnow() - last_reset.created_at).total_seconds()
        if elapsed < 60:
            rem = int(60 - elapsed)
            return jsonify(ok=False, message=translate(f'Harap tunggu {rem} detik sebelum meminta kode OTP baru.'), cooldown_remaining=rem), 429

    # Invalidate previous unused resets
    PasswordReset.query.filter_by(user_id=current_user.id, is_used=False).update({'is_used': True})

    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    reset_entry = PasswordReset(
        user_id=current_user.id,
        expires_at=expires_at,
        created_by_id=current_user.id
    )
    reset_entry.set_otp(otp_code)
    db.session.add(reset_entry)
    db.session.commit()

    company = db.session.get(Company, current_user.company_id)
    send_password_reset_otp_email(company, current_user, otp_code)
    audit_log('user.password_otp_requested', 'user', current_user.id, company_id=current_user.company_id)
    db.session.commit()

    return jsonify(
        ok=True,
        message=translate('Kode verifikasi OTP 6-digit telah dikirim ke email Anda.'),
        email=current_user.email,
        cooldown_remaining=60
    )

@main_bp.route('/settings/password/verify-otp', methods=['POST'])
@login_required
def verify_password_change_otp():
    otp_input = request.form.get('otp', '').strip()
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not otp_input or not new_password or not confirm_password:
        return jsonify(ok=False, message=translate('Harap lengkapi kode OTP dan password baru.')), 400

    if new_password != confirm_password:
        return jsonify(ok=False, message=translate('New passwords do not match.')), 400

    if not validate_password_strength(new_password):
        return jsonify(ok=False, message=translate('Password must be at least 8 characters and include letters and numbers.')), 400

    reset_entry = PasswordReset.query.filter_by(user_id=current_user.id, is_used=False).order_by(PasswordReset.created_at.desc()).first()
    if not reset_entry or reset_entry.is_expired:
        return jsonify(ok=False, message=translate('Kode OTP sudah kedaluwarsa. Silakan minta kode baru.')), 400

    if reset_entry.is_locked:
        return jsonify(ok=False, message=translate('Batas maksimal percobaan salah tercapai. Silakan minta kode baru.')), 400

    if not reset_entry.check_otp(otp_input):
        reset_entry.attempts += 1
        db.session.commit()
        rem = max(0, 5 - reset_entry.attempts)
        if rem == 0:
            return jsonify(ok=False, message=translate('Terlalu banyak percobaan salah. Kode OTP dibatalkan. Silakan minta kode baru.')), 400
        return jsonify(ok=False, message=translate(f'Kode OTP salah. Sisa kesempatan: {rem} kali.')), 400

    # OTP is valid! Apply password
    current_user.set_password(new_password)
    reset_entry.is_used = True

    audit_log('user.password_changed_with_otp', 'user', current_user.id, company_id=current_user.company_id)
    db.session.commit()

    flash(translate('Password updated.'), 'success')
    return jsonify(ok=True, message=translate('Password updated.'))

@main_bp.route('/avatar/<int:user_id>')
def user_avatar(user_id):
    user = db.session.get(User, user_id)
    if not user or not user.avatar_path:
        abort(404)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, user.avatar_path)
    if not os.path.exists(full_path):
        abort(404)
    
    import mimetypes
    mime_type, _ = mimetypes.guess_type(full_path)
    return send_file(full_path, mimetype=mime_type or 'image/jpeg')

@main_bp.route('/settings/avatar/delete', methods=['POST'])
@login_required
def delete_avatar():
    if current_user.avatar_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        old_path = os.path.join(base_dir, current_user.avatar_path)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass
        current_user.avatar_path = None
        db.session.commit()
        audit_log('user.avatar_deleted', 'user', current_user.id)
        flash(translate('Foto profil berhasil dihapus.'), 'success')
    return redirect(url_for('main.user_settings'))

@main_bp.route('/workspace/company', methods=['POST'])
@login_required
@role_required('admin')
def select_active_company():
    company_id = request.form.get('company_id', type=int)
    company = db.session.get(Company, company_id) if company_id else None
    if not company or not company.is_active:
        flash(translate('Perusahaan tidak tersedia.'), 'danger')
    else:
        session['active_company_id'] = company.id
        audit_log('workspace.company_switched', 'company', company.id)
        db.session.commit()
    return redirect(request.referrer or url_for('main.dashboard'))

@main_bp.route('/api/chart-data')
@login_required
def api_chart_data():
    this_year = date.today().year
    my_company = get_active_company_id()

    if current_user.role == 'employee':
        base = LeaveRequest.query.filter_by(employee_id=current_user.id, company_id=my_company)
    else:
        base = LeaveRequest.query.filter_by(company_id=my_company)

    monthly = []
    for m in range(1, 13):
        count = base.filter(
            db.extract('year', LeaveRequest.start_date) == this_year,
            db.extract('month', LeaveRequest.start_date) == m
        ).count()
        monthly.append(count)

    types = LeaveType.query.filter_by(company_id=my_company).all()
    type_labels = [t.name for t in types]
    type_counts = []
    for t in types:
        count = base.filter(
            db.extract('year', LeaveRequest.start_date) == this_year,
            LeaveRequest.leave_type_id == t.id
        ).count()
        type_counts.append(count)

    return jsonify({
        'monthly': monthly,
        'types': {'labels': type_labels, 'counts': type_counts}
    })

@main_bp.route('/export/excel')
@login_required
@role_required('manager', 'hr', 'admin')
def export_excel():
    from services.export_service import generate_leave_report_excel
    import re
    my_company = get_active_company_id()
    year = request.args.get('year', type=int) or date.today().year
    department_id = request.args.get('department_id', type=int)

    company = db.session.get(Company, my_company)
    company_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', company.name.lower()) if company else "company"
    filename = f"Laporan_Cuti_{company_slug}_{year}_{date.today().strftime('%Y%m%d')}.xlsx"

    excel_buffer = generate_leave_report_excel(my_company, year=year, department_id=department_id)
    audit_log('reports.exported', 'company', my_company, details={'year': year, 'department_id': department_id}, company_id=my_company)

    return send_file(
        excel_buffer,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
