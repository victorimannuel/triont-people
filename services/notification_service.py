import smtplib
from email.message import EmailMessage

def _dispatch_email(company, to_email, subject, body):
    """Internal helper to dispatch email via SMTP with timeout and error logging."""
    if not to_email or not company or not company.smtp_host or not company.smtp_user:
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
        print(f'❌ Failed to send email to {to_email}: {e}')
        return False

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
    action_title = status_text.get(event, event)

    notes_line = f"\nCatatan: {leave_request.notes}" if getattr(leave_request, 'notes', None) else ""
    reason_line = f"\nAlasan: {leave_request.reason}" if getattr(leave_request, 'reason', None) else ""

    part = getattr(leave_request, 'day_part', 'full') or 'full'
    if part == 'morning':
        duration_str = '0.5 hari (Pagi)'
    elif part == 'afternoon':
        duration_str = '0.5 hari (Siang)'
    else:
        duration_str = f"{int(leave_request.duration_days) if leave_request.duration_days % 1 == 0 else leave_request.duration_days:g} hari"

    if event == 'submit':
        # 1. Confirmation to employee
        emp_subject = f'[{company.name}] Pengajuan Cuti Berhasil Dikirim - {leave_request.leave_type.name}'
        emp_body = f"""Halo {emp.name},

Pengajuan cuti {leave_request.leave_type.name} Anda berhasil dikirim dan sedang menunggu persetujuan atasan/HR.

Detail Pengajuan:
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {leave_request.start_date.strftime('%d %B %Y')} s/d {leave_request.end_date.strftime('%d %B %Y')}
- Durasi     : {duration_str}
- Status     : Menunggu Persetujuan (Pending){reason_line}

Salam,
{company.name} (People by Triont)
"""
        _dispatch_email(company, emp.email, emp_subject, emp_body)

        # 2. Notification to manager (if employee has a direct manager)
        if getattr(emp, 'manager', None) and emp.manager.email:
            mgr_subject = f'[{company.name}] Pengajuan Cuti Baru Menunggu Persetujuan - {emp.name}'
            mgr_body = f"""Halo {emp.manager.name},

Anggota tim Anda, {emp.name}, baru saja mengajukan permohonan cuti yang memerlukan persetujuan Anda.

Detail Pengajuan:
- Karyawan   : {emp.name} ({emp.email})
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {leave_request.start_date.strftime('%d %B %Y')} s/d {leave_request.end_date.strftime('%d %B %Y')}
- Durasi     : {duration_str}{reason_line}

Silakan tinjau dan berikan keputusan melalui Inbox Approval di People by Triont:
https://people.thehyouman.com/approvals

Salam,
{company.name} (People by Triont)
"""
            _dispatch_email(company, emp.manager.email, mgr_subject, mgr_body)

    else:
        # Decision notification to employee (approve / reject)
        subject = f'[{company.name}] Pengajuan Cuti {action_title.title()} - {leave_request.leave_type.name}'
        body = f"""Halo {emp.name},

Pengajuan cuti {leave_request.leave_type.name} Anda telah {action_title}.

Detail Pengajuan:
- Jenis Cuti : {leave_request.leave_type.name}
- Tanggal    : {leave_request.start_date.strftime('%d %B %Y')} s/d {leave_request.end_date.strftime('%d %B %Y')}
- Durasi     : {duration_str}
- Status     : {leave_request.status.title()}{reason_line}{notes_line}

Salam,
{company.name} (People by Triont)
"""
        _dispatch_email(company, emp.email, subject, body)

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

