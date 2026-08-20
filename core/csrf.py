import re
import secrets
from flask import request, session, g, jsonify, flash, redirect, url_for, current_app
from core.i18n import translate

def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token

def enforce_csrf():
    g.csrf_token = csrf_token()
    if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return
    if current_app.config.get('TESTING') and not current_app.config.get('WTF_CSRF_ENABLED', True):
        return
    sent_token = request.form.get('_csrf_token') or request.headers.get('X-CSRFToken')
    if not sent_token or sent_token != session.get('_csrf_token'):
        from services.audit_service import audit_log
        from extensions import db
        audit_log('security.csrf_failed', details={'path': request.path})
        db.session.commit()
        is_ajax_or_json = (
            request.is_json
            or '/import/' in request.path
            or request.path.startswith('/api/')
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
            or (request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html)
        )
        if is_ajax_or_json:
            return jsonify(success=False, ok=False, error='Validasi keamanan (CSRF) gagal atau sesi telah berakhir. Silakan muat ulang halaman.'), 400
        flash(translate('Security check failed. Please try again.'), 'danger')
        return redirect(request.referrer or url_for('auth.login'))

def inject_csrf_fields(response):
    if response.content_type and response.content_type.startswith('text/html'):
        html = response.get_data(as_text=True)
        if '<form' in html and ('method="POST"' in html or 'method="post"' in html):
            token_field = f'<input type="hidden" name="_csrf_token" value="{g.csrf_token}">'
            html = re.sub(r'(<form\b(?=[^>]*method=["\'](?:POST|post)["\'])[^>]*>)', r'\1' + token_field, html)
            response.set_data(html)
    return response
