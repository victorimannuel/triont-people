import io
import os
import json
import zipfile
from datetime import datetime, date
from flask import current_app
from extensions import db
from models.user import User, Department
from models.company import Company
from models.leave import LeaveType, LeaveBalance, LeaveRequest, LeaveGrant
from models.holiday import PublicHoliday
from models.approval import ApprovalConfig
from models.audit import AuditLog

def _serialize_date(val):
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val

def generate_system_backup_dict(company_id=None):
    """
    Exports database records as a structured JSON dictionary.
    If company_id is provided, filters by company; otherwise dumps all companies.
    """
    comp_query = Company.query
    if company_id:
        comp_query = comp_query.filter_by(id=company_id)
    companies = comp_query.all()
    comp_ids = [c.id for c in companies]

    backup_data = {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "type": "single_company" if company_id else "system_full",
        "companies": [
            {
                "id": c.id,
                "name": c.name,
                "is_active": c.is_active,
                "primary_color": c.primary_color,
                "notifications_enabled": c.notifications_enabled,
                "delegate_enabled": c.delegate_enabled,
                "smtp_host": c.smtp_host,
                "smtp_port": c.smtp_port,
                "smtp_user": c.smtp_user,
                "notify_on_approve": c.notify_on_approve,
                "notify_on_reject": c.notify_on_reject,
                "notify_on_submit": c.notify_on_submit,
                "created_at": _serialize_date(c.created_at),
                "created_by_id": c.created_by_id,
                "updated_at": _serialize_date(c.updated_at),
                "updated_by_id": c.updated_by_id
            } for c in companies
        ],
        "departments": [
            {
                "id": d.id,
                "company_id": d.company_id,
                "name": d.name,
                "head_id": d.head_id,
                "created_at": _serialize_date(d.created_at),
                "created_by_id": d.created_by_id,
                "updated_at": _serialize_date(d.updated_at),
                "updated_by_id": d.updated_by_id
            } for d in Department.query.filter(Department.company_id.in_(comp_ids)).all()
        ],
        "users": [
            {
                "id": u.id,
                "company_id": u.company_id,
                "department_id": u.department_id,
                "name": u.name,
                "email": u.email,
                "password_hash": u.password_hash,
                "role": u.role,
                "is_active": u.is_active,
                "avatar_color": u.avatar_color,
                "avatar_path": u.avatar_path,
                "language_preference": u.language_preference,
                "manager_id": u.manager_id,
                "calendar_token": u.calendar_token,
                "created_at": _serialize_date(u.created_at),
                "created_by_id": u.created_by_id,
                "updated_at": _serialize_date(u.updated_at),
                "updated_by_id": u.updated_by_id
            } for u in User.query.filter(User.company_id.in_(comp_ids)).all()
        ],
        "leave_types": [
            {
                "id": lt.id,
                "company_id": lt.company_id,
                "name": lt.name,
                "description": lt.description,
                "days_per_year": lt.days_per_year,
                "color": lt.color,
                "icon": lt.icon,
                "requires_approval": lt.requires_approval,
                "is_active": lt.is_active,
                "requires_attachment": lt.requires_attachment,
                "attachment_label": lt.attachment_label,
                "created_at": _serialize_date(lt.created_at),
                "created_by_id": lt.created_by_id,
                "updated_at": _serialize_date(lt.updated_at),
                "updated_by_id": lt.updated_by_id
            } for lt in LeaveType.query.filter(LeaveType.company_id.in_(comp_ids)).all()
        ],
        "leave_balances": [
            {
                "id": b.id,
                "company_id": b.company_id,
                "employee_id": b.employee_id,
                "leave_type_id": b.leave_type_id,
                "year": b.year,
                "total_days": float(b.total_days),
                "used_days": float(b.used_days),
                "pending_days": float(b.pending_days),
                "created_at": _serialize_date(b.created_at),
                "created_by_id": b.created_by_id,
                "updated_at": _serialize_date(b.updated_at),
                "updated_by_id": b.updated_by_id
            } for b in LeaveBalance.query.filter(LeaveBalance.company_id.in_(comp_ids)).all()
        ],
        "leave_requests": [
            {
                "id": r.id,
                "company_id": r.company_id,
                "employee_id": r.employee_id,
                "leave_type_id": r.leave_type_id,
                "start_date": _serialize_date(r.start_date),
                "end_date": _serialize_date(r.end_date),
                "day_part": r.day_part,
                "duration_days": float(r.duration_days),
                "reason": r.reason,
                "status": r.status,
                "notes": r.notes,
                "delegate_id": r.delegate_id,
                "attachment_path": r.attachment_path,
                "attachment_original_name": r.attachment_original_name,
                "current_approval_level": r.current_approval_level,
                "max_approval_level": r.max_approval_level,
                "is_archived": r.is_archived,
                "created_at": _serialize_date(r.created_at),
                "created_by_id": r.created_by_id,
                "updated_at": _serialize_date(r.updated_at),
                "updated_by_id": r.updated_by_id
            } for r in LeaveRequest.query.filter(LeaveRequest.company_id.in_(comp_ids)).all()
        ],
        "leave_grants": [
            {
                "id": g.id,
                "company_id": g.company_id,
                "employee_id": g.employee_id,
                "leave_type_id": g.leave_type_id,
                "year": g.year,
                "mode": g.mode,
                "amount": float(g.amount) if g.amount is not None else 0.0,
                "old_total": float(g.old_total) if g.old_total is not None else 0.0,
                "new_total": float(g.new_total) if g.new_total is not None else 0.0,
                "actor_id": g.actor_id,
                "request_token": g.request_token,
                "created_at": _serialize_date(g.created_at),
                "created_by_id": g.created_by_id,
                "updated_at": _serialize_date(g.updated_at),
                "updated_by_id": g.updated_by_id
            } for g in LeaveGrant.query.filter(LeaveGrant.company_id.in_(comp_ids)).all()
        ],
        "approval_configs": [
            {
                "id": ac.id,
                "company_id": ac.company_id,
                "leave_type_id": ac.leave_type_id,
                "level": ac.level,
                "approver_role": ac.approver_role,
                "created_at": _serialize_date(ac.created_at),
                "created_by_id": ac.created_by_id,
                "updated_at": _serialize_date(ac.updated_at),
                "updated_by_id": ac.updated_by_id
            } for ac in ApprovalConfig.query.filter(ApprovalConfig.company_id.in_(comp_ids)).all()
        ],
        "public_holidays": [
            {
                "id": h.id,
                "company_id": h.company_id,
                "name": h.name,
                "holiday_date": _serialize_date(h.holiday_date),
                "kind": h.kind,
                "is_active": h.is_active,
                "created_at": _serialize_date(h.created_at),
                "created_by_id": h.created_by_id,
                "updated_at": _serialize_date(h.updated_at),
                "updated_by_id": h.updated_by_id
            } for h in PublicHoliday.query.filter(PublicHoliday.company_id.in_(comp_ids)).all()
        ],
        "audit_logs": [
            {
                "id": a.id,
                "company_id": a.company_id,
                "actor_id": a.actor_id,
                "action": a.action,
                "target_type": a.target_type,
                "target_id": a.target_id,
                "details": a.details,
                "ip_address": a.ip_address,
                "user_agent": a.user_agent,
                "created_at": _serialize_date(a.created_at)
            } for a in AuditLog.query.filter(AuditLog.company_id.in_(comp_ids)).order_by(AuditLog.id.desc()).limit(1000).all()
        ]
    }
    return backup_data

def _sql_escape(val):
    if val is None:
        return 'NULL'
    if isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    if isinstance(val, (int, float)):
        return str(val)
    val_str = str(val).replace("'", "''")
    return f"'{val_str}'"

def generate_system_backup_sql_text(company_id=None):
    data = generate_system_backup_dict(company_id)
    lines = [
        "-- --------------------------------------------------------",
        "-- People by Triont Database Backup",
        f"-- Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"-- Scope: {'Company ID ' + str(company_id) if company_id else 'Full System'}",
        "-- --------------------------------------------------------",
        "",
        "BEGIN;",
        ""
    ]

    tables_order = [
        ('companies', data.get('companies', [])),
        ('departments', data.get('departments', [])),
        ('users', data.get('users', [])),
        ('leave_types', data.get('leave_types', [])),
        ('leave_balances', data.get('leave_balances', [])),
        ('leave_requests', data.get('leave_requests', [])),
        ('leave_grants', data.get('leave_grants', [])),
        ('approval_configs', data.get('approval_configs', [])),
        ('public_holidays', data.get('public_holidays', [])),
        ('audit_logs', data.get('audit_logs', []))
    ]

    for tbl_name, rows in tables_order:
        if not rows:
            continue
        lines.append(f"-- Records for table `{tbl_name}` ({len(rows)} rows)")
        for row in rows:
            cols = list(row.keys())
            vals = [_sql_escape(row[k]) for k in cols]
            cols_str = ', '.join([f'"{c}"' for c in cols])
            vals_str = ', '.join(vals)
            lines.append(f'INSERT INTO "{tbl_name}" ({cols_str}) VALUES ({vals_str});')
        lines.append("")

    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines)

def generate_system_backup_sql(company_id=None):
    """
    Returns in-memory BytesIO containing formatted SQL dump.
    """
    sql_text = generate_system_backup_sql_text(company_id)
    buffer = io.BytesIO(sql_text.encode('utf-8'))
    buffer.seek(0)
    return buffer

def generate_system_backup_json(company_id=None):
    """
    Returns in-memory BytesIO containing formatted JSON database backup.
    """
    data = generate_system_backup_dict(company_id)
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    buffer = io.BytesIO(json_bytes)
    buffer.seek(0)
    return buffer

def generate_full_backup_zip(company_id=None):
    """
    Creates a full ZIP archive containing:
    1. database_backup.sql (SQL Dump)
    2. database_backup.json (Structured JSON Dump)
    3. uploads/ directory (attachments and avatars)
    4. manifest.json with system metadata
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Database SQL Dump
        sql_text = generate_system_backup_sql_text(company_id)
        zip_file.writestr("database_backup.sql", sql_text)

        # 2. Database JSON Dump
        data = generate_system_backup_dict(company_id)
        zip_file.writestr("database_backup.json", json.dumps(data, indent=2, ensure_ascii=False))

        # 3. Uploads folder
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads_dir = os.path.join(base_dir, 'uploads')
        if os.path.exists(uploads_dir):
            for root, _, files in os.walk(uploads_dir):
                for f in files:
                    file_path = os.path.join(root, f)
                    arcname = os.path.relpath(file_path, base_dir)
                    zip_file.write(file_path, arcname=arcname)

        # 4. Manifest metadata
        manifest = {
            "application": "People by Triont",
            "backup_date": datetime.now().isoformat(),
            "scope": f"Company ID: {company_id}" if company_id else "All Companies",
            "database_records": {
                "companies": len(data["companies"]),
                "departments": len(data["departments"]),
                "users": len(data["users"]),
                "leave_types": len(data["leave_types"]),
                "leave_balances": len(data["leave_balances"]),
                "leave_requests": len(data["leave_requests"]),
            }
        }
        zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

    buffer.seek(0)
    return buffer
