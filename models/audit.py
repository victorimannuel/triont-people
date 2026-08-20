import json
from extensions import db
from core.time_util import utcnow

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(80), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

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
            'auth.login_success': 'Login Berhasil',
            'auth.login_failed': 'Login Gagal',
            'auth.logout': 'Logout',
            'admin.employee_created': 'Tambah Karyawan',
            'admin.employee_updated': 'Edit Karyawan',
            'admin.employee_archived': 'Arsipkan Karyawan',
            'admin.employee_unarchived': 'Buka Arsip Karyawan',
            'admin.employee_deleted': 'Hapus Karyawan Permanen',
            'admin.leave_granted': 'Penyesuaian Kuota Cuti',
            'admin.leave_type_created': 'Tambah Jenis Cuti',
            'admin.leave_type_updated': 'Edit Jenis Cuti',
            'admin.leave_type_archived': 'Arsipkan Jenis Cuti',
            'admin.leave_type_unarchived': 'Pulihkan Jenis Cuti',
            'admin.leave_type_deleted': 'Hapus Jenis Cuti',
            'admin.department_created': 'Tambah Departemen',
            'admin.department_updated': 'Edit Departemen',
            'admin.department_deleted': 'Hapus Departemen',
            'admin.company_created': 'Tambah Perusahaan',
            'admin.company_updated': 'Edit Perusahaan',
            'admin.approval_config_updated': 'Update Alur Approval',
            'company.smtp_updated': 'Update Pengaturan SMTP',
            'holiday.synced': 'Sinkronisasi Hari Libur',
            'leave.request_submitted': 'Pengajuan Cuti',
            'leave.request_approve': 'Approve Cuti',
            'leave.request_reject': 'Tolak Cuti',
            'leave.request_cancel': 'Batalkan Cuti',
            'approval_history.archived': 'Arsipkan Riwayat Approval',
            'approval_history.unarchived': 'Buka Arsip Approval',
            'system.backup_downloaded': 'Unduh Backup Sistem',
            'reports.exported': 'Ekspor Laporan Excel',
            'import.employees_completed': 'Import Karyawan Selesai',
            'import.history_completed': 'Import Riwayat Selesai',
            'user.password_updated': 'Ubah Password',
            'user.profile_updated': 'Update Profil',
            'user.avatar_uploaded': 'Upload Foto Profil',
            'user.avatar_deleted': 'Hapus Foto Profil',
            'user.language_updated': 'Ubah Bahasa',
            'workspace.company_switched': 'Ganti Perusahaan Aktif',
            'security.csrf_failed': 'Keamanan: CSRF Gagal'
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
