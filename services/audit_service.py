import json
from flask import request
from flask_login import current_user
from extensions import db
from models.audit import AuditLog

def audit_log(action, target_type=None, target_id=None, details=None, company_id=None, actor_id=None):
    try:
        actor = current_user if current_user.is_authenticated else None
        entry = AuditLog(
            company_id=company_id if company_id is not None else (getattr(actor, 'company_id', None) if actor else None),
            actor_id=actor_id if actor_id is not None else (getattr(actor, 'id', None) if actor else None),
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=request.headers.get('X-Forwarded-For', request.remote_addr or '')[:64],
            user_agent=(request.headers.get('User-Agent') or '')[:255],
            details=json.dumps(details or {}, default=str),
        )
        db.session.add(entry)
    except Exception as exc:
        print(f'Audit log skipped: {exc}')
