import uuid
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models.user import User
from models.company import Company
from models.auth import PasswordReset
from core.i18n import translate, normalize_language, SUPPORTED_LANGUAGES
from core.auth import role_required, validate_password_strength
from core.time_util import utcnow
from services.audit_service import audit_log
from services.notification_service import send_password_reset_otp_email

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            session['language'] = normalize_language(user.language_preference or 'en')
            audit_log('auth.login_success', 'user', user.id, company_id=user.company_id, actor_id=user.id)
            db.session.commit()
            next_page = request.args.get('next')
            flash(translate(f'Selamat datang, {user.name}!'), 'success')
            return redirect(next_page or url_for('main.dashboard'))
        audit_log('auth.login_failed', details={'email': email})
        db.session.commit()
        flash(translate('Email or password is incorrect.'), 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    audit_log('auth.logout')
    session.pop('impersonator_admin_id', None)
    session.pop('impersonator_admin_name', None)
    db.session.commit()
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash(translate('Harap masukkan alamat email Anda.'), 'danger')
            return render_template('forgot_password.html')

        user = User.query.filter_by(email=email).first()
        session['reset_email'] = email

        if not user or not user.is_active:
            # Anti-enumeration response
            flash(translate('Jika email terdaftar, kode verifikasi OTP telah dikirimkan ke email Anda.'), 'info')
            return redirect(url_for('auth.verify_otp'))

        # Check cooldown (60 seconds)
        last_reset = PasswordReset.query.filter_by(user_id=user.id).order_by(PasswordReset.created_at.desc()).first()
        if last_reset and last_reset.created_at:
            elapsed = (utcnow() - last_reset.created_at).total_seconds()
            if elapsed < 60:
                rem = int(60 - elapsed)
                flash(translate(f'Harap tunggu {rem} detik sebelum meminta kode OTP baru.'), 'warning')
                return redirect(url_for('auth.verify_otp'))

        # Invalidate previous unused resets
        PasswordReset.query.filter_by(user_id=user.id, is_used=False).update({'is_used': True})

        # Generate 6-digit numeric OTP
        otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
        expires_at = utcnow() + timedelta(minutes=15)

        reset_entry = PasswordReset(
            user_id=user.id,
            expires_at=expires_at,
            created_by_id=user.id
        )
        reset_entry.set_otp(otp_code)
        db.session.add(reset_entry)
        db.session.commit()

        company = db.session.get(Company, user.company_id)
        send_password_reset_otp_email(company, user, otp_code)
        audit_log('auth.forgot_password_requested', 'user', user.id, company_id=user.company_id, details={'email': user.email})
        db.session.commit()

        flash(translate('Kode verifikasi OTP telah dikirim ke email Anda. Silakan cek kotak masuk.'), 'success')
        return redirect(url_for('auth.verify_otp'))

    return render_template('forgot_password.html')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    email = session.get('reset_email')
    if not email:
        return redirect(url_for('auth.forgot_password'))

    user = User.query.filter_by(email=email, is_active=True).first()

    # Calculate cooldown for resend button
    cooldown_remaining = 0
    if user:
        last_reset = PasswordReset.query.filter_by(user_id=user.id).order_by(PasswordReset.created_at.desc()).first()
        if last_reset and last_reset.created_at:
            elapsed = (utcnow() - last_reset.created_at).total_seconds()
            if elapsed < 60:
                cooldown_remaining = int(60 - elapsed)

    if request.method == 'POST':
        otp_input = request.form.get('otp', '').strip()
        if not otp_input or len(otp_input) != 6:
            flash(translate('Masukkan 6 digit kode OTP yang valid.'), 'danger')
            return render_template('verify_otp.html', email=email, cooldown_remaining=cooldown_remaining)

        if not user:
            flash(translate('Kode OTP tidak valid atau telah kedaluwarsa.'), 'danger')
            return redirect(url_for('auth.forgot_password'))

        reset_entry = PasswordReset.query.filter_by(user_id=user.id, is_used=False).order_by(PasswordReset.created_at.desc()).first()
        if not reset_entry or reset_entry.is_expired:
            flash(translate('Kode OTP sudah kedaluwarsa. Silakan minta kode baru.'), 'danger')
            return render_template('verify_otp.html', email=email, cooldown_remaining=cooldown_remaining)

        if reset_entry.is_locked:
            flash(translate('Batas maksimal percobaan salah tercapai. Silakan minta kode baru.'), 'danger')
            return redirect(url_for('auth.forgot_password'))

        if not reset_entry.check_otp(otp_input):
            reset_entry.attempts += 1
            db.session.commit()
            remaining_attempts = max(0, 5 - reset_entry.attempts)
            if remaining_attempts == 0:
                flash(translate('Terlalu banyak percobaan salah. Kode OTP dibatalkan. Silakan minta kode baru.'), 'danger')
                return redirect(url_for('auth.forgot_password'))
            flash(translate(f'Kode OTP salah. Sisa kesempatan: {remaining_attempts} kali.'), 'danger')
            return render_template('verify_otp.html', email=email, cooldown_remaining=cooldown_remaining)

        # OTP is valid: generate one-time reset token
        reset_token = uuid.uuid4().hex
        reset_entry.reset_token = reset_token
        session['reset_token'] = reset_token
        session['reset_user_id'] = user.id
        audit_log('auth.otp_verified', 'user', user.id, company_id=user.company_id)
        db.session.commit()

        flash(translate('Verifikasi OTP berhasil. Silakan buat kata sandi baru Anda.'), 'success')
        return redirect(url_for('auth.reset_password'))

    return render_template('verify_otp.html', email=email, cooldown_remaining=cooldown_remaining)

@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    email = session.get('reset_email')
    if not email:
        flash(translate('Sesi verifikasi berakhir. Silakan masukkan email Anda kembali.'), 'warning')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.filter_by(email=email, is_active=True).first()
    if not user:
        flash(translate('Kode verifikasi OTP baru telah dikirimkan jika email terdaftar.'), 'info')
        return redirect(url_for('auth.verify_otp'))

    last_reset = PasswordReset.query.filter_by(user_id=user.id).order_by(PasswordReset.created_at.desc()).first()
    if last_reset and last_reset.created_at:
        elapsed = (utcnow() - last_reset.created_at).total_seconds()
        if elapsed < 60:
            rem = int(60 - elapsed)
            flash(translate(f'Harap tunggu {rem} detik sebelum meminta kode baru.'), 'warning')
            return redirect(url_for('auth.verify_otp'))

    # Invalidate previous unused resets
    PasswordReset.query.filter_by(user_id=user.id, is_used=False).update({'is_used': True})

    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    expires_at = utcnow() + timedelta(minutes=15)

    reset_entry = PasswordReset(
        user_id=user.id,
        expires_at=expires_at,
        created_by_id=user.id
    )
    reset_entry.set_otp(otp_code)
    db.session.add(reset_entry)
    db.session.commit()

    company = db.session.get(Company, user.company_id)
    send_password_reset_otp_email(company, user, otp_code)
    audit_log('auth.otp_resent', 'user', user.id, company_id=user.company_id)
    db.session.commit()

    flash(translate('Kode OTP baru telah dikirim ke email Anda.'), 'success')
    return redirect(url_for('auth.verify_otp'))

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    token = request.args.get('token', '').strip()
    if token:
        reset_entry = PasswordReset.query.filter_by(reset_token=token, is_used=False).first()
        if not reset_entry or reset_entry.is_expired:
            flash(translate('Tautan reset kata sandi tidak valid atau telah kedaluwarsa. Silakan minta tautan baru.'), 'danger')
            return redirect(url_for('auth.forgot_password'))
        session['reset_token'] = reset_entry.reset_token
        session['reset_user_id'] = reset_entry.user_id

    reset_token = session.get('reset_token')
    user_id = session.get('reset_user_id')

    if not reset_token or not user_id:
        flash(translate('Sesi reset password tidak valid atau telah kedaluwarsa. Silakan mulai ulang.'), 'danger')
        return redirect(url_for('auth.forgot_password'))

    reset_entry = PasswordReset.query.filter_by(user_id=user_id, reset_token=reset_token, is_used=False).first()
    if not reset_entry or reset_entry.is_expired:
        session.pop('reset_token', None)
        session.pop('reset_user_id', None)
        flash(translate('Sesi reset password telah kedaluwarsa. Silakan minta tautan baru.'), 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not new_password or not confirm_password:
            flash(translate('Harap isi semua kolom password.'), 'danger')
            return render_template('reset_password.html')

        if new_password != confirm_password:
            flash(translate('Konfirmasi password tidak cocok dengan password baru.'), 'danger')
            return render_template('reset_password.html')

        if not validate_password_strength(new_password):
            flash(translate('Password minimal 8 karakter dan harus mengandung kombinasi huruf serta angka.'), 'danger')
            return render_template('reset_password.html')

        user = db.session.get(User, user_id)
        if not user:
            flash(translate('Pengguna tidak ditemukan.'), 'danger')
            return redirect(url_for('auth.forgot_password'))

        user.set_password(new_password)
        reset_entry.is_used = True
        reset_entry.reset_token = None

        session.pop('reset_token', None)
        session.pop('reset_user_id', None)
        session.pop('reset_email', None)

        audit_log('auth.password_reset_success', 'user', user.id, company_id=user.company_id)
        db.session.commit()

        flash(translate('Kata sandi berhasil diperbarui! Silakan masuk menggunakan kata sandi baru Anda.'), 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')
