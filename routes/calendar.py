from datetime import date, timedelta
from flask import render_template, request
from flask_login import login_required, current_user
from extensions import db
from models.user import User
from models.company import Company
from models.leave import LeaveType, LeaveRequest, LeaveBalance
from models.holiday import PublicHoliday
from core.auth import get_active_company_id
from services.holiday_service import ensure_company_holidays
from services.leave_type_service import order_leave_type_query
from routes.common import main_bp

@main_bp.route('/calendar')
@login_required
def calendar():
    today = date.today()
    month = request.args.get('month', type=int, default=today.month)
    year = request.args.get('year', type=int, default=today.year)

    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    days_in_month = last_day.day
    first_weekday = first_day.weekday()

    my_company = get_active_company_id()
    ensure_company_holidays(my_company)
    requests_query = LeaveRequest.query.filter(
        LeaveRequest.company_id == my_company,
        LeaveRequest.status.in_(['pending', 'approved']),
        LeaveRequest.start_date <= last_day,
        LeaveRequest.end_date >= first_day
    )
    if current_user.role == 'employee':
        requests_query = requests_query.filter(LeaveRequest.employee_id == current_user.id)
    elif current_user.role == 'manager':
        subordinate_ids = db.session.query(User.id).filter(
            User.company_id == my_company,
            (User.manager_id == current_user.id) | (User.id == current_user.id)
        )
        requests_query = requests_query.filter(LeaveRequest.employee_id.in_(subordinate_ids))

    all_requests = requests_query.all()

    leaves_by_date = {}
    for req in all_requests:
        start_d = 1 if req.start_date < first_day else req.start_date.day
        end_d = days_in_month if req.end_date > last_day else req.end_date.day
        for d in range(start_d, end_d + 1):
            if d not in leaves_by_date:
                leaves_by_date[d] = []
            leaves_by_date[d].append(req)

    holidays_query = PublicHoliday.query.filter(
        PublicHoliday.company_id == my_company,
        PublicHoliday.is_active == True,
        PublicHoliday.holiday_date >= first_day,
        PublicHoliday.holiday_date <= last_day
    ).all()
    holidays_by_date = {h.holiday_date.day: h for h in holidays_query}

    month_names = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                   'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

    this_year = date.today().year
    active_company = db.session.get(Company, my_company)
    delegate_enabled = bool(active_company and active_company.delegate_enabled)
    can_apply_leave = current_user.role in ('employee', 'manager', 'hr')
    leave_types = []
    balances = {}
    employees = []
    max_date = date(2030, 12, 31)
    if can_apply_leave:
        leave_types = order_leave_type_query(LeaveType.query.filter_by(is_active=True, company_id=my_company)).all()
        balances = {b.leave_type_id: b for b in LeaveBalance.query.filter_by(employee_id=current_user.id, company_id=my_company, year=this_year).all()}
        employees = User.query.filter(User.id != current_user.id, User.is_active == True, User.is_deleted == False, User.company_id == my_company).order_by(User.name).all() if delegate_enabled else []

    calendar_token = current_user.get_calendar_token()

    prev_month_days = (first_day - timedelta(days=1)).day

    holidays_json = [h.holiday_date.isoformat() for h in holidays_query]

    return render_template('calendar.html',
        month=month, year=year,
        prev_month=prev_month, prev_year=prev_year,
        next_month=next_month, next_year=next_year,
        month_name=month_names[month],
        days_in_month=days_in_month,
        first_weekday=first_weekday,
        prev_month_days=prev_month_days,
        leaves_by_date=leaves_by_date,
        holidays_by_date=holidays_by_date,
        holidays_json=holidays_json,
        today=today,
        can_apply_leave=can_apply_leave,
        leave_types=leave_types,
        balances=balances,
        employees=employees,
        max_date=max_date,
        delegate_enabled=delegate_enabled,
        calendar_token=calendar_token)


@main_bp.route('/calendar/feed/<token>.ics')
def calendar_feed(token):
    from datetime import datetime, timezone
    from flask import Response, abort
    if not token or len(token) < 16:
        abort(404)

    user = User.query.filter_by(calendar_token=token, is_active=True, is_deleted=False).first()
    if not user:
        abort(404)

    company = db.session.get(Company, user.company_id)
    ensure_company_holidays(user.company_id)

    today = date.today()
    feed_start = today - timedelta(days=180)
    feed_end = today + timedelta(days=540)

    # Holidays
    holidays = PublicHoliday.query.filter(
        PublicHoliday.company_id == user.company_id,
        PublicHoliday.is_active == True,
        PublicHoliday.holiday_date >= feed_start,
        PublicHoliday.holiday_date <= feed_end
    ).order_by(PublicHoliday.holiday_date).all()

    # Leaves
    leaves_query = LeaveRequest.query.filter(
        LeaveRequest.company_id == user.company_id,
        LeaveRequest.status == 'approved',
        LeaveRequest.start_date <= feed_end,
        LeaveRequest.end_date >= feed_start
    )
    if user.role == 'employee':
        # Include team member leaves if department exists, or user leaves
        if user.department_id:
            dept_user_ids = db.session.query(User.id).filter_by(department_id=user.department_id, company_id=user.company_id, is_active=True)
            leaves_query = leaves_query.filter(LeaveRequest.employee_id.in_(dept_user_ids))
        else:
            leaves_query = leaves_query.filter(LeaveRequest.employee_id == user.id)
    elif user.role == 'manager':
        sub_ids = db.session.query(User.id).filter(
            User.company_id == user.company_id,
            (User.manager_id == user.id) | (User.id == user.id),
            User.is_active == True
        )
        leaves_query = leaves_query.filter(LeaveRequest.employee_id.in_(sub_ids))

    leaves = leaves_query.order_by(LeaveRequest.start_date).all()

    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Triont People//Calendar Feed//EN",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:People - {company.name if company else 'Triont People'}",
        "X-WR-TIMEZONE:Asia/Jakarta",
        "REFRESH-INTERVAL;VALUE=DURATION:PT3H",
        "X-PUBLISHED-TTL:PT3H"
    ]

    now_str = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')

    for h in holidays:
        start_d = h.holiday_date.strftime('%Y%m%d')
        end_d = (h.holiday_date + timedelta(days=1)).strftime('%Y%m%d')
        summary = f"🎉 Libur: {h.name}"
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:holiday-{h.id}@people.thehyouman.com",
            f"DTSTAMP:{now_str}",
            f"DTSTART;VALUE=DATE:{start_d}",
            f"DTEND;VALUE=DATE:{end_d}",
            f"SUMMARY:{summary}",
            "DESCRIPTION:Hari Libur Nasional / Perusahaan",
            "STATUS:CONFIRMED",
            "TRANSP:TRANSPARENT",
            "END:VEVENT"
        ])

    for req in leaves:
        start_d = req.start_date.strftime('%Y%m%d')
        end_d = (req.end_date + timedelta(days=1)).strftime('%Y%m%d')
        part_tag = ""
        if req.day_part == 'morning':
            part_tag = " (Pagi)"
        elif req.day_part == 'afternoon':
            part_tag = " (Siang)"

        summary = f"🌴 [Cuti] {req.employee.name} - {req.leave_type.name}{part_tag}"
        desc = f"Karyawan: {req.employee.name}\\nJenis Cuti: {req.leave_type.name}\\nDurasi: {req.duration_days} hari{part_tag}\\nStatus: Disetujui (Approved)"
        if req.reason:
            clean_reason = req.reason.replace('\n', ' ').replace('\r', '')
            desc += f"\\nAlasan: {clean_reason}"
        if req.delegate:
            desc += f"\\nDelegasi: {req.delegate.name}"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:leave-{req.id}@people.thehyouman.com",
            f"DTSTAMP:{now_str}",
            f"DTSTART;VALUE=DATE:{start_d}",
            f"DTEND;VALUE=DATE:{end_d}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")
    ics_body = "\r\n".join(lines) + "\r\n"

    return Response(ics_body, mimetype='text/calendar', headers={
        'Content-Disposition': f'inline; filename="people-calendar.ics"',
        'Cache-Control': 'no-cache, no-store, must-revalidate'
    })


@main_bp.route('/calendar/sync/regenerate-token', methods=['POST'])
@login_required
def regenerate_calendar_token_action():
    from flask import redirect, url_for, flash, jsonify
    new_token = current_user.regenerate_calendar_token()
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'token': new_token})
    flash('Link sinkronisasi kalender berhasil diperbarui.', 'success')
    return redirect(url_for('main.calendar'))

