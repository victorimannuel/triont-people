import smtplib
from email.message import EmailMessage

def _dispatch_email(company, to_email, subject, body, *, raise_errors=False):
    """Internal helper to dispatch email via SMTP with timeout and error logging."""
    if not to_email or not company or not company.smtp_host or not company.smtp_user:
        if raise_errors:
            raise ValueError('SMTP configuration unavailable')
        print(f'ℹ️  [NO_SMTP] Email to {to_email} with subject "{subject}" logged.')
        return False

    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = company.smtp_user
        msg['To'] = to_email
        msg.set_content(body)

        if company.smtp_port == 465:
            with smtplib.SMTP_SSL(company.smtp_host, company.smtp_port, timeout=15) as server:
                if company.smtp_password:
                    server.login(company.smtp_user, company.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(company.smtp_host, company.smtp_port, timeout=15) as server:
                server.starttls()
                if company.smtp_password:
                    server.login(company.smtp_user, company.smtp_password)
                server.send_message(msg)
        print(f'✅ Notification sent to {to_email}')
        return True
    except Exception as e:
        if raise_errors:
            raise
        print('SMTP delivery failed.')
        return False


def _dispatch_unique(company, to_email, subject, body, sent_emails, dispatcher=None):
    normalized = (to_email or '').strip().lower()
    if not normalized or normalized in sent_emails:
        return False
    sent_emails.add(normalized)
    return (dispatcher or _dispatch_email)(company, to_email, subject, body)


def _company_notification_recipients(company_id, exclude_user_ids=None):
    """Active same-company users who should receive company-wide leave notices."""
    if not company_id:
        return []

    from models.user import User

    exclude_user_ids = set(exclude_user_ids or [])
    query = User.query.filter(
        User.company_id == company_id,
        User.is_active == True,
        User.is_deleted == False,
    ).order_by(User.name)
    if exclude_user_ids:
        query = query.filter(~User.id.in_(exclude_user_ids))
    return query.all()


def _current_approval_recipients(leave_request):
    """Return the users responsible for the request's current approval level."""
    from models.user import User
    from services.approval_service import effective_approval_stage

    if leave_request.status != 'pending':
        return []
    _, config = effective_approval_stage(leave_request)

    if config and config.approver_role in ('hr', 'admin', 'superadmin'):
        return User.query.filter(
            User.company_id == leave_request.company_id,
            User.role == config.approver_role,
            User.is_active == True,
            User.is_deleted == False,
        ).order_by(User.name).all()

    manager = getattr(leave_request.employee, 'manager', None)
    return [manager] if manager and manager.email else []

def send_notification(company, event, leave_request, dispatcher=None, recipient_scope='all', force=False):
    """Deliver notifications, or pass each message to a supplied dispatcher."""
    if not company:
        return

    if not force and (
        not company.notifications_enabled
        or (event == 'approve' and not company.notify_on_approve)
        or (event == 'reject' and not company.notify_on_reject)
        or (event == 'submit' and not company.notify_on_submit)
    ):
        return

    emp = leave_request.employee
    status_text = {'approve': 'disetujui', 'reject': 'ditolak', 'submit': 'diajukan'}
    status_label = {'approve': 'Disetujui', 'reject': 'Ditolak', 'submit': 'Menunggu Persetujuan'}
    action_title = status_text.get(event, event)
    sent_emails = set()

    notes_line = f"\nCatatan: {leave_request.notes}" if getattr(leave_request, 'notes', None) else ""
    reason_line = f"\nAlasan: {leave_request.reason}" if getattr(leave_request, 'reason', None) else ""

    part = getattr(leave_request, 'day_part', 'full') or 'full'
    if part == 'morning':
        duration_str = '0.5 hari (Pagi)'
    elif part == 'afternoon':
        duration_str = '0.5 hari (Siang)'
    else:
        duration_str = f"{int(leave_request.duration_days) if leave_request.duration_days % 1 == 0 else leave_request.duration_days:g} hari"

    date_range = f"{leave_request.start_date.strftime('%d %B %Y')} s/d {leave_request.end_date.strftime('%d %B %Y')}"
    resend_prefix = 'Kirim ulang: ' if force else ''
    approval_action = ''
    approval_stage = ''
    pending_approval = event == 'submit' and leave_request.status == 'pending'
    if pending_approval:
        from services.approval_service import effective_approval_stage
        level, config = effective_approval_stage(leave_request)
        role = config.approver_role if config else 'manager'
        role_label = {'manager': 'Manager', 'hr': 'HR', 'admin': 'Admin', 'superadmin': 'Super Admin'}.get(role, role)
        approval_stage = f'Persetujuan {role_label} (tahap {level} dari {leave_request.max_approval_level})'
        approval_action = f"""Tindakan yang diperlukan:
1. Buka Inbox Approval di People by Triont dan masuk dengan akun Anda:
https://people.thehyouman.com/approvals
2. Tinjau pengajuan {emp.name} untuk tanggal {date_range}.
3. Pilih Approve (Setujui) atau Reject (Tolak), lalu konfirmasikan keputusan Anda.

Jika pengajuan sudah diproses oleh approver lain, tidak diperlukan tindakan tambahan."""

    if recipient_scope in ('manager', 'approver'):
        recipients = (
            _current_approval_recipients(leave_request)
            if recipient_scope == 'approver'
            else [getattr(emp, 'manager', None)]
        )
        for recipient in recipients:
            if not recipient or not recipient.email:
                continue
            purpose = 'Perlu tindakan: Persetujuan cuti' if pending_approval else 'Informasi hasil pengajuan cuti'
            subject = f'[{company.name}] {resend_prefix}{purpose} - {emp.name}'
            introduction = (f'Pengajuan cuti {emp.name} memerlukan persetujuan Anda.\n'
                            f'Anda menerima email ini sebagai approver pada {approval_stage}.'
                            if pending_approval else f'Pengajuan cuti {emp.name} telah {action_title}.')
            next_action = approval_action if pending_approval else 'Email ini hanya untuk informasi hasil pengajuan. Tidak diperlukan tindakan approval.'
            body = f"""Halo {recipient.name},

{introduction}

Detail Pengajuan:
- Karyawan   : {emp.name} ({emp.email})
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {date_range}
- Durasi     : {duration_str}
- Status     : {status_label.get(event, leave_request.status.title())}{reason_line}{notes_line}

{next_action}

Salam,
{company.name} (People by Triont)
"""
            _dispatch_unique(company, recipient.email, subject, body, sent_emails, dispatcher)
        return

    if event == 'submit':
        # 1. Confirmation to employee/requester
        emp_subject = f'[{company.name}] {resend_prefix}Status Pengajuan Cuti Anda - {leave_request.leave_type.name}'
        emp_body = f"""Halo {emp.name},

Pengajuan cuti {leave_request.leave_type.name} Anda sudah tercatat dan sedang menunggu persetujuan atasan/HR.

Detail Pengajuan:
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {date_range}
- Durasi     : {duration_str}
- Status     : Menunggu Persetujuan (Pending){reason_line}

Anda tidak perlu mengirim pengajuan yang sama lagi. Pantau status melalui menu History:
https://people.thehyouman.com/history

Salam,
{company.name} (People by Triont)
"""
        _dispatch_unique(company, emp.email, emp_subject, emp_body, sent_emails, dispatcher)

        # 2. Action notification to the approver responsible for the active level.
        for approver in _current_approval_recipients(leave_request):
            approver_subject = f'[{company.name}] {resend_prefix}Perlu tindakan: Persetujuan cuti - {emp.name}'
            approver_body = f"""Halo {approver.name},

Pengajuan cuti {emp.name} memerlukan persetujuan Anda.
Anda menerima email ini sebagai approver pada {approval_stage}.

Detail Pengajuan:
- Karyawan   : {emp.name} ({emp.email})
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {date_range}
- Durasi     : {duration_str}{reason_line}

{approval_action}

Salam,
{company.name} (People by Triont)
"""
            _dispatch_unique(company, approver.email, approver_subject, approver_body, sent_emails, dispatcher)

        team_subject = f'[{company.name}] {resend_prefix}Info Cuti Diajukan - {emp.name}'
        team_body = f"""Halo,

{emp.name} mengajukan cuti {leave_request.leave_type.name}.

Detail Pengajuan:
- Karyawan   : {emp.name}
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {date_range}
- Durasi     : {duration_str}
- Status     : Menunggu Persetujuan{reason_line}

Email ini untuk informasi tim dan perencanaan jadwal. Cuti ini belum disetujui.
Tidak diperlukan tindakan approval dari Anda melalui email ini.

Salam,
{company.name} (People by Triont)
"""
        for user in _company_notification_recipients(company.id, exclude_user_ids={emp.id}):
            _dispatch_unique(company, user.email, team_subject, team_body, sent_emails, dispatcher)

    else:
        # Decision notification to employee/requester
        subject = f'[{company.name}] {resend_prefix}Pengajuan Cuti {action_title.title()} - {leave_request.leave_type.name}'
        body = f"""Halo {emp.name},

Pengajuan cuti {leave_request.leave_type.name} Anda telah {action_title}.

Detail Pengajuan:
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {date_range}
- Durasi     : {duration_str}
- Status     : {leave_request.status.title()}{reason_line}{notes_line}

Lihat detail keputusan pada menu History:
https://people.thehyouman.com/history
Jika perlu klarifikasi atas keputusan ini, hubungi approver atau HR Anda.

Salam,
{company.name} (People by Triont)
"""
        _dispatch_unique(company, emp.email, subject, body, sent_emails, dispatcher)

        team_subject = f'[{company.name}] {resend_prefix}Info Cuti {status_label.get(event, action_title.title())} - {emp.name}'
        team_body = f"""Halo,

Pengajuan cuti {emp.name} telah {action_title}.

Detail Pengajuan:
- Karyawan   : {emp.name}
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {date_range}
- Durasi     : {duration_str}
- Status     : {status_label.get(event, leave_request.status.title())}{reason_line}{notes_line}

Email ini untuk informasi hasil pengajuan dan penyesuaian jadwal tim.
Tidak diperlukan tindakan approval dari Anda melalui email ini.

Salam,
{company.name} (People by Triont)
"""
        for user in _company_notification_recipients(company.id, exclude_user_ids={emp.id}):
            _dispatch_unique(company, user.email, team_subject, team_body, sent_emails, dispatcher)

def send_password_reset_otp_email(company, user, otp_code: str):
    """Sends OTP verification email for password reset."""
    company_name = company.name if company else "People by Triont"
    subject = f'[{company_name}] Kode Verifikasi Reset Password: {otp_code}'

    body = f"""Halo {user.name},

Kami menerima permintaan untuk mereset kata sandi akun Anda di {company_name}.

Berikut adalah kode verifikasi OTP Anda:
========================================
             {otp_code}
========================================

Kode ini berlaku selama 15 menit. Masukkan kode di atas pada halaman verifikasi untuk melanjutkan proses reset password.

PERINGATAN KEAMANAN:
Jangan berikan kode ini kepada siapapun. Jika Anda tidak merasa melakukan permintaan ini, abaikan email ini dan akun Anda tetap aman.

Salam,
Tim {company_name} (People by Triont)
"""

    if company and company.smtp_host and company.smtp_user:
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = company.smtp_user
            msg['To'] = user.email
            msg.set_content(body)

            if company.smtp_port == 465:
                with smtplib.SMTP_SSL(company.smtp_host, company.smtp_port, timeout=15) as server:
                    if company.smtp_password:
                        server.login(company.smtp_user, company.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(company.smtp_host, company.smtp_port, timeout=15) as server:
                    server.starttls()
                    if company.smtp_password:
                        server.login(company.smtp_user, company.smtp_password)
                    server.send_message(msg)
            print(f'✅ Password reset OTP sent to {user.email}')
            return True
        except Exception as e:
            print(f'❌ Failed to send password reset OTP email: {e}')
            return False
    else:
        print(f'ℹ️  [DEV/NO_SMTP] Password reset OTP for {user.email}: {otp_code}')
        return True

def send_password_reset_link_email(company, user, reset_link: str):
    """Sends direct password reset link email."""
    company_name = company.name if company else "People by Triont"
    subject = f'[{company_name}] Atur Ulang Kata Sandi Akun Anda'

    body = f"""Halo {user.name},

Admin telah mengirimkan tautan untuk mengatur ulang kata sandi akun Anda di {company_name}.

Klik tautan di bawah ini untuk langsung membuat kata sandi baru Anda:
{reset_link}

Tautan ini berlaku selama 60 menit dan hanya dapat digunakan 1 (satu) kali.

PERINGATAN KEAMANAN:
Jangan berikan tautan ini kepada siapapun. Jika Anda tidak meminta perubahan ini atau memiliki pertanyaan, silakan hubungi tim administrator Anda.

Salam,
Tim {company_name} (People by Triont)
"""

    if company and company.smtp_host and company.smtp_user:
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = company.smtp_user
            msg['To'] = user.email
            msg.set_content(body)

            if company.smtp_port == 465:
                with smtplib.SMTP_SSL(company.smtp_host, company.smtp_port, timeout=15) as server:
                    if company.smtp_password:
                        server.login(company.smtp_user, company.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(company.smtp_host, company.smtp_port, timeout=15) as server:
                    server.starttls()
                    if company.smtp_password:
                        server.login(company.smtp_user, company.smtp_password)
                    server.send_message(msg)
            print(f'✅ Password reset link email sent to {user.email}')
            return True
        except Exception as e:
            print(f'❌ Failed to send password reset link email: {e}')
            return False
    else:
        print(f'ℹ️  [DEV/NO_SMTP] Password reset link for {user.email}: {reset_link}')
        return True
