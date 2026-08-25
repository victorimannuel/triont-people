import json
from extensions import db
from core.time_util import utcnow

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    __table_args__ = (
        db.Index('idx_audit_logs_company_created', 'company_id', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    target_type = db.Column(db.String(80), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    company = db.relationship('Company')
    actor = db.relationship('User')

    @property
    def details_dict(self):
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except Exception:
            return {'raw': self.details}

    @property
    def action_label(self):
        labels = {
            'auth.login_success': 'Login Successful',
            'auth.login_failed': 'Login Failed',
            'auth.logout': 'Logout',
            'admin.employee_created': 'Add Employee',
            'admin.employee_updated': 'Edit Employee',
            'admin.employee_archived': 'Archive Employee',
            'admin.employee_unarchived': 'Unarchive Employee',
            'admin.employee_deleted': 'Permanently Delete Employee',
            'admin.leave_granted': 'Adjust Leave Quota',
            'admin.leave_balance_rollover': 'Year-End Leave Balance Rollover',
            'admin.leave_type_created': 'Add Leave Type',
            'admin.leave_type_updated': 'Edit Leave Type',
            'admin.leave_type_archived': 'Archive Leave Type',
            'admin.leave_type_unarchived': 'Restore Leave Type',
            'admin.leave_type_deleted': 'Delete Leave Type',
            'admin.department_created': 'Add Department',
            'admin.department_updated': 'Edit Department',
            'admin.department_deleted': 'Delete Department',
            'admin.company_created': 'Add Company',
            'admin.company_updated': 'Edit Company',
            'admin.custom_domain_tested': 'Test Custom Domain',
            'admin.approval_config_updated': 'Update Approval Workflow',
            'admin.approval_config_added': 'Add Approval Workflow Level',
            'admin.approval_config_deleted': 'Delete Approval Workflow Level',
            'company.smtp_updated': 'Update SMTP Settings',
            'holiday.synced': 'Sync Public Holidays',
            'leave.request_submitted': 'Submit Leave Request',
            'leave.request_approve': 'Approve Leave Request',
            'leave.request_reject': 'Reject Leave Request',
            'leave.request_cancel': 'Cancel Leave Request',
            'approval_history.archived': 'Archive Approval History',
            'approval_history.unarchived': 'Unarchive Approval History',
            'system.backup_downloaded': 'Download System Backup',
            'reports.exported': 'Export Excel Report',
            'import.employees_completed': 'Employee Import Completed',
            'import.history_completed': 'History Import Completed',
            'user.password_updated': 'Change Password',
            'user.profile_updated': 'Update Profile',
            'user.avatar_uploaded': 'Upload Profile Photo',
            'user.avatar_deleted': 'Delete Profile Photo',
            'user.language_updated': 'Change Language',
            'workspace.company_switched': 'Switch Active Company',
            'security.csrf_failed': 'Security: CSRF Verification Failed',
            'security.forbidden': 'Security: Forbidden Access',
            'security.suspicious_404': 'Security: Suspicious Probe Blocked',
            'auth.otp_failed': 'OTP Verification Failed',
            'auth.otp_locked': 'OTP Verification Locked',
            'user.password_otp_failed': 'Password OTP Failed',
            'user.password_otp_locked': 'Password OTP Locked'
        }
        return labels.get(self.action, self.action.replace('.', ' ').replace('_', ' ').title())

    @property
    def action_badge_class(self):
        act = self.action.lower()
        if 'deleted' in act or 'failed' in act or 'reject' in act:
            return 'bg-red-50 text-red-700 border border-red-200/80'
        elif 'created' in act or 'success' in act or 'approve' in act:
            return 'bg-emerald-50 text-emerald-700 border border-emerald-200/80'
        elif 'archived' in act or 'granted' in act or 'warning' in act:
            return 'bg-amber-50 text-amber-700 border border-amber-200/80'
        elif 'backup' in act or 'export' in act:
            return 'bg-purple-50 text-purple-700 border border-purple-200/80'
        elif 'import' in act or 'synced' in act:
            return 'bg-blue-50 text-blue-700 border border-blue-200/80'
        else:
            return 'bg-teal-50 text-teal-700 border border-teal-200/80'

    @property
    def action_icon(self):
        act = self.action.lower()
        if 'login_success' in act:
            return 'fa-right-to-bracket'
        elif 'login_failed' in act:
            return 'fa-triangle-exclamation'
        elif 'logout' in act:
            return 'fa-right-from-bracket'
        elif 'deleted' in act:
            return 'fa-trash-can'
        elif 'archived' in act:
            return 'fa-box-archive'
        elif 'unarchived' in act:
            return 'fa-arrow-rotate-left'
        elif 'created' in act:
            return 'fa-plus-circle'
        elif 'updated' in act or 'profile' in act or 'password' in act:
            return 'fa-pen-to-square'
        elif 'granted' in act:
            return 'fa-calendar-plus'
        elif 'backup' in act:
            return 'fa-database'
        elif 'export' in act or 'report' in act:
            return 'fa-file-excel'
        elif 'import' in act:
            return 'fa-file-import'
        elif 'approve' in act:
            return 'fa-circle-check'
        elif 'reject' in act:
            return 'fa-circle-xmark'
        elif 'submit' in act:
            return 'fa-paper-plane'
        else:
            return 'fa-clock-rotate-left'
