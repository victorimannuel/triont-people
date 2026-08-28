import os
from datetime import date, datetime
from flask import Flask, session, request, jsonify, render_template
from flask_login import current_user
from config import Config
from extensions import db, login_manager, migrate
from core.csrf import csrf_token, enforce_csrf, inject_csrf_fields
from core.i18n import translate, LANGUAGE_LABELS, normalize_language, SUPPORTED_LANGUAGES, get_client_translations
from core.auth import get_active_company_id, load_user, is_admin_role, is_superadmin_role
from models import Company, init_audit_events
from services.seed_service import seed_initial_data
from routes import register_blueprints

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    if migrate:
        migrate.init_app(app, db)

    init_audit_events()

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in first.'

    # Security and CSRF hooks
    app.before_request(enforce_csrf)
    app.after_request(inject_csrf_fields)

    # Register blueprints
    register_blueprints(app)

    # Template context processors & globals
    @app.context_processor
    def inject_helpers():
        from core.time_util import TIMEZONE_CHOICES, get_current_user_timezone
        from core.pagination import update_query_params
        return {
            'csrf_token': csrf_token,
            't': translate,
            'client_translations': get_client_translations(),
            'language_labels': LANGUAGE_LABELS,
            'timezone_choices': TIMEZONE_CHOICES,
            'current_user_tz': get_current_user_timezone(),
            'update_query_params': update_query_params,
            'is_impersonating': bool(session.get('impersonator_admin_id')),
            'is_admin_role': is_admin_role,
            'is_superadmin_role': is_superadmin_role,
            'impersonator_admin_name': session.get('impersonator_admin_name', 'Admin'),
            'date': date,
            'datetime': datetime,
        }

    @app.template_filter('user_tz')
    @app.template_filter('format_datetime')
    def format_datetime_filter(dt, fmt='%d/%m/%Y %H:%M'):
        if not dt:
            return '-'
        from core.time_util import format_user_datetime
        return format_user_datetime(dt, fmt=fmt)

    @app.template_filter('indonesian_date')
    def indonesian_date_filter(d):
        if not d:
            return ''
        months = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
        if isinstance(d, str):
            try:
                d = datetime.strptime(d[:10], '%Y-%m-%d').date()
            except Exception:
                return str(d)
        try:
            return f"{d.day} {months[d.month - 1]} {d.year}"
        except Exception:
            return str(d)

    @app.template_filter('format_days')
    def format_days_filter(days):
        if days is None:
            return '0'
        try:
            f = float(days)
            return f"{int(f)}" if f % 1 == 0 else f"{f:g}"
        except Exception:
            return str(days)

    @app.template_filter('format_duration')
    def format_duration_filter(req_or_days, day_part='full'):
        if hasattr(req_or_days, 'duration_days'):
            days = req_or_days.duration_days
            part = getattr(req_or_days, 'day_part', 'full') or 'full'
        else:
            try:
                days = float(req_or_days)
            except Exception:
                days = 0.0
            part = day_part

        if part == 'morning':
            return '0.5 hari (Pagi)'
        elif part == 'afternoon':
            return '0.5 hari (Siang)'
        else:
            if days % 1 == 0:
                return f"{int(days)} hari"
            return f"{days:g} hari"

    @app.template_filter('format_role')
    def format_role_filter(role):
        if not role:
            return ''
        r = str(role).lower()
        if r == 'hr':
            return 'HR'
        if r == 'superadmin':
            return 'Super Admin'
        if r == 'admin':
            return 'Admin'
        if r == 'manager':
            return 'Manager'
        if r == 'employee':
            return 'Employee'
        return str(role).capitalize()

    @app.context_processor
    def inject_theme():
        if not current_user.is_authenticated:
            return dict(
                primary_color='#0d9488',
                active_company=None,
                available_companies=[],
                current_language=normalize_language(session.get('language', 'en'))
            )
        active_company = db.session.get(Company, get_active_company_id())
        available_companies = []
        if is_admin_role(current_user.role):
            available_companies = Company.query.filter_by(is_active=True).order_by(Company.name).all()
        primary = active_company.primary_color if active_company else '#1e5a52'
        current_language = current_user.language_preference or normalize_language(session.get('language', 'en'))
        if current_language not in SUPPORTED_LANGUAGES:
            current_language = 'en'
        session['language'] = current_language
        return dict(
            primary_color=primary,
            active_company=active_company,
            available_companies=available_companies,
            current_language=current_language
        )

    @app.route('/sw.js')
    def service_worker_file():
        from flask import send_from_directory
        return send_from_directory(os.path.join(app.root_path, 'static'), 'sw.js', mimetype='application/javascript')

    def log_security_event(action, status_code):
        try:
            from services.audit_service import audit_log
            actor_id = current_user.id if current_user.is_authenticated else None
            company_id = getattr(current_user, 'company_id', None) if current_user.is_authenticated else None
            audit_log(action, details={
                'method': request.method,
                'path': request.path,
                'result': 'blocked',
                'result_status': status_code,
            }, company_id=company_id, actor_id=actor_id)
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

    def is_suspicious_probe_path(path):
        lowered = (path or '').lower()
        probe_markers = (
            'graphql', '/gql', '/api/gql', '/api/graphql',
            '/wp-', 'wp-admin', 'wp-login', '.env', '.git',
            'phpmyadmin', 'xmlrpc.php', 'vendor/phpunit',
        )
        return any(marker in lowered for marker in probe_markers)

    # Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        log_security_event('security.forbidden', 403)
        if request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
            return jsonify({
                'error': 'Forbidden',
                'message': translate('You do not have permission to access this resource.'),
                'status_code': 403
            }), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        if is_suspicious_probe_path(request.path):
            log_security_event('security.suspicious_404', 404)
        if request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
            return jsonify({
                'error': 'Not Found',
                'message': translate('The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.'),
                'status_code': 404
            }), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        try:
            db.session.rollback()
        except Exception:
            pass
        if request.path.startswith('/api/') or request.accept_mimetypes.best == 'application/json':
            return jsonify({
                'error': 'Internal Server Error',
                'message': translate('Something went wrong on our end. Please try again later or contact support if the problem persists.'),
                'status_code': 500
            }), 500
        return render_template('errors/500.html'), 500

    # Auto-create tables & seed initial data on startup if configured
    with app.app_context():
        if app.config.get('AUTO_CREATE_DB', True):
            db.create_all()
        try:
            with db.engine.connect() as conn:
                def safe_add_column(tbl, col_def):
                    try:
                        conn.execute(db.text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col_def};"))
                        conn.commit()
                        return
                    except Exception:
                        pass
                    try:
                        conn.execute(db.text(f"ALTER TABLE {tbl} ADD COLUMN {col_def};"))
                        conn.commit()
                    except Exception:
                        pass

                audit_tables = [
                    'companies', 'departments', 'users', 'leave_types',
                    'approval_configs', 'leave_requests', 'leave_balances',
                    'leave_grants', 'public_holidays', 'password_resets'
                ]
                for table in audit_tables:
                    safe_add_column(table, 'created_by_id INTEGER')
                    safe_add_column(table, 'updated_by_id INTEGER')
                    safe_add_column(table, 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                    safe_add_column(table, 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                    safe_add_column(table, 'is_deleted BOOLEAN DEFAULT FALSE')
                    safe_add_column(table, 'deleted_at TIMESTAMP')
                safe_add_column('leave_requests', "day_part VARCHAR(20) DEFAULT 'full'")
                safe_add_column('users', "calendar_token VARCHAR(64)")
                safe_add_column('users', "avatar_path VARCHAR(255)")
                safe_add_column('users', "timezone_preference VARCHAR(50) DEFAULT 'Asia/Jakarta'")
                safe_add_column('leave_types', "sort_order INTEGER DEFAULT 0")
                safe_add_column('leave_types', "requires_attachment BOOLEAN DEFAULT FALSE")
                safe_add_column('leave_types', "attachment_label VARCHAR(100) DEFAULT 'Surat Dokter / Bukti Pendukung'")
                try:
                    conn.execute(db.text("UPDATE leave_types SET sort_order = id WHERE sort_order IS NULL OR sort_order = 0;"))
                    conn.commit()
                except Exception:
                    pass
                safe_add_column('leave_requests', "attachment_path VARCHAR(255)")
                safe_add_column('leave_requests', "attachment_original_name VARCHAR(255)")

                def safe_create_index(index_name, tbl, cols):
                    try:
                        conn.execute(db.text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {tbl} ({cols});"))
                        conn.commit()
                        return
                    except Exception:
                        pass
                    try:
                        conn.execute(db.text(f"CREATE INDEX {index_name} ON {tbl} ({cols});"))
                        conn.commit()
                        return
                    except Exception:
                        pass

                safe_create_index('idx_audit_logs_company_id', 'audit_logs', 'company_id')
                safe_create_index('idx_audit_logs_actor_id', 'audit_logs', 'actor_id')
                safe_create_index('idx_audit_logs_action', 'audit_logs', 'action')
                safe_create_index('idx_audit_logs_created_at', 'audit_logs', 'created_at')
                safe_create_index('idx_audit_logs_company_created', 'audit_logs', 'company_id, created_at')
                for table in audit_tables:
                    safe_create_index(f'idx_{table}_is_deleted', table, 'is_deleted')
        except Exception:
            pass

        if app.config.get('AUTO_CREATE_DB', True):
            seed_initial_data()

    return app

if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=5000, debug=True)
