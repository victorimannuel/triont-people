import re
from functools import wraps
from flask import session, flash, redirect, url_for, request, jsonify
from flask_login import current_user
from extensions import db, login_manager
from models.user import User
from models.company import Company
from core.i18n import translate

@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user and getattr(user, 'is_deleted', False):
        return None
    return user

def get_active_company_id():
    if not current_user.is_authenticated:
        return None
    if current_user.role == 'admin':
        active_id = session.get('active_company_id')
        if active_id:
            company = db.session.get(Company, active_id)
            if company and company.is_active:
                return active_id
        session['active_company_id'] = current_user.company_id
        return current_user.company_id
    return current_user.company_id

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                is_ajax_or_json = (
                    request.is_json
                    or '/import/' in request.path
                    or request.path.startswith('/api/')
                    or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                    or 'application/json' in request.headers.get('Accept', '')
                )
                if is_ajax_or_json:
                    msg = 'Sesi login Anda telah berakhir. Silakan login kembali.' if not current_user.is_authenticated else 'Akses ditolak.'
                    return jsonify({'success': False, 'error': msg}), 401 if not current_user.is_authenticated else 403
                flash(translate('Access denied.'), 'danger')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_password_strength(password):
    if not password or len(password) < 8:
        return False
    return bool(re.search(r'[A-Za-z]', password) and re.search(r'\d', password))
