import re
from flask import session

SUPPORTED_LANGUAGES = ('en', 'id', 'idc')

LANGUAGE_LABELS = {
    'en': 'English',
    'id': 'Indonesia formal',
    'idc': 'Indonesia casual',
}

# Canonical English Base Translations Dictionary
TRANSLATIONS = {
    "- No Department -": {"id": "- Tanpa Departemen -", "idc": "- Tanpa Divisi -"},
    "- No Manager -": {"id": "- Tanpa Manager -", "idc": "- Tanpa Manager -"},
    "- None -": {"id": "- Tidak Ada -", "idc": "- Ga Ada -"},
    "- Select Manager (Optional) -": {"id": "- Pilih Atasan (Opsional) -", "idc": "- Pilih Atasan (Opsional) -"},
    "0.5 Afternoon": {"id": "0.5 Siang", "idc": "0.5 Siang"},
    "0.5 day (Morning: 08:00 - 12:00)": {"id": "0.5 hari (Pagi: 08:00 - 12:00)", "idc": "0.5 hari (Pagi: 08:00 - 12:00)"},
    "0.5 Morning": {"id": "0.5 Pagi", "idc": "0.5 Pagi"},
    "A 6-digit code has been sent to": {"id": "Kode 6-digit telah dikirim ke", "idc": "Kode 6 digit udah dikirim ke"},
    "A 6-digit OTP code will be sent to your registered email for identity verification.": {"id": "Kode OTP 6-digit akan dikirim ke email terdaftar Anda untuk verifikasi identitas.", "idc": "Kode OTP 6-digit bakal dikirim ke email terdaftar kamu buat verifikasi identitas."},
    "A 6-digit OTP verification code has been sent to email:": {"id": "Kode verifikasi OTP 6-digit telah dikirimkan ke email:", "idc": "Kode OTP 6-digit udah dikirim ke email:"},
    "A 6-digit OTP verification code will be sent to your registered email to ensure only you can access your account.": {"id": "Kode verifikasi OTP 6-digit akan dikirimkan ke email terdaftar untuk memastikan hanya Anda yang dapat mengakses akun Anda.", "idc": "Kode OTP 6-digit bakal dikirim ke email terdaftar biar akun kamu tetep aman."},
    "A long break without using leave. Lucky you!": {"id": "Libur panjang tanpa perlu ambil cuti. Beruntung sekali!", "idc": "Libur panjang tanpa ambil cuti. Hokinya bagus."},
    "Access denied.": {"id": "Akses ditolak.", "idc": "Aksesnya belum bisa."},
    "Account Details": {"id": "Detail Akun", "idc": "Detail Akun"},
    "Account Protection": {"id": "Proteksi Akun", "idc": "Proteksi Akun"},
    "Account Recovery": {"id": "Pemulihan Akun", "idc": "Pemulihan Akun"},
    "Account Security": {"id": "Keamanan Akun", "idc": "Keamanan Akun"},
    "Account Simulation Mode:": {"id": "Mode Simulasi Akun:", "idc": "Mode Simulasi Akun:"},
    "Action / Operation": {"id": "Aksi / Operasi", "idc": "Aksi / Operasi"},
    "Action Category": {"id": "Kategori Aksi", "idc": "Kategori Aksi"},
    "Actions": {"id": "Aksi", "idc": "Aksi"},
    "Active": {"id": "Aktif", "idc": "Aktif"},
    "Add Company": {"id": "Tambah Perusahaan", "idc": "Tambah Company"},
    "Add Department": {"id": "Tambah departemen", "idc": "Tambah Divisi"},
    "Add Employee": {"id": "Tambah Karyawan", "idc": "Tambah Karyawan"},
    "Add Holiday": {"id": "Tambah Hari Libur", "idc": "Tambah Hari Libur"},
    "Add Leave Type": {"id": "Tambah jenis cuti", "idc": "Tambah tipe cuti"},
    "Add notes if needed.": {"id": "Tambahkan catatan bila diperlukan.", "idc": "Tambah catatan kalau perlu."},
    "Add People to your phone/laptop home screen for quick access & clean view.": {"id": "Pasang People ke layar utama HP / Laptop untuk akses cepat & notifikasi tanpa address bar.", "idc": "Pasang People ke homescreen HP / Laptop buat akses cepet."},
    "Add to Home Screen": {"id": "Pasang ke Layar Utama", "idc": "Pasang ke Layar Utama"},
    "Adjust Leave Quota": {"id": "Penyesuaian Kuota Cuti", "idc": "Penyesuaian Kuota Cuti"},
    "Admin users cannot be deleted.": {"id": "Tidak bisa menghapus admin.", "idc": "Admin ga bisa dihapus."},
    "admin@company.com": {"id": "admin@perusahaan.com", "idc": "admin@company.com"},
    "All": {"id": "Semua", "idc": "Semua"},
    "All Categories": {"id": "Semua Kategori", "idc": "Semua Kategori"},
    "All Heads": {"id": "Semua kepala", "idc": "Semua Head"},
    "All team members are present this week": {"id": "Semua tim hadir minggu ini", "idc": "Semua tim masuk minggu ini"},
    "All Users": {"id": "Semua User", "idc": "Semua User"},
    "Allocated": {"id": "Alokasi", "idc": "Alokasi"},
    "Allocation for all leave types": {"id": "Alokasi seluruh jenis cuti", "idc": "Alokasi semua tipe cuti"},
    "Approval": {"id": "Approval", "idc": "Approval"},
    "Approval confirmation": {"id": "Konfirmasi persetujuan", "idc": "Konfirmasi approval"},
    "Approval Date": {"id": "Tgl approval", "idc": "Tgl approval"},
    "Approval history archived.": {"id": "Riwayat approval berhasil diarsipkan!", "idc": "Riwayat approval udah diarsip."},
    "Approval history unarchived.": {"id": "Riwayat approval berhasil dikembalikan dari arsip!", "idc": "Riwayat approval udah dibalikin dari arsip."},
    "Approval level added.": {"id": "Level approval berhasil ditambahkan!", "idc": "Level approval udah ditambah."},
    "Approval level deleted.": {"id": "Level approval berhasil dihapus!", "idc": "Level approval udah dihapus."},
    "Approval Time:": {"id": "Waktu Approval:", "idc": "Waktu Approval:"},
    "Approval workflow": {"id": "Alur approval", "idc": "Alur approval"},
    "Approve leave request?": {"id": "Setujui pengajuan cuti?", "idc": "Approve pengajuan cuti?"},
    "Approve Leave Request": {"id": "Approve Cuti", "idc": "Approve Cuti"},
    "Approved": {"id": "Disetujui", "idc": "Disetujui"},
    "Approved by:": {"id": "Disetujui oleh:", "idc": "Disetujui sama:"},
    "Approver Notes:": {"id": "Catatan Approver:", "idc": "Catatan Approver:"},
    "Archive Employee": {"id": "Arsipkan Karyawan", "idc": "Arsipkan Karyawan"},
    "Archive leave type": {"id": "Arsipkan jenis cuti", "idc": "Arsipin jenis cuti"},
    "Archive leave type?": {"id": "Arsipkan jenis cuti?", "idc": "Arsipin jenis cuti?"},
    "Archive Leave Type": {"id": "Arsipkan Jenis Cuti", "idc": "Arsipin Tipe Cuti"},
    "Archive Approval History": {"id": "Arsipkan Riwayat Approval", "idc": "Arsip Riwayat Approval"},
    "Archived": {"id": "Diarsipkan", "idc": "Diarsip"},
    "Are you sure you want to cancel this leave request?": {"id": "Apakah Anda yakin ingin membatalkan pengajuan cuti ini?", "idc": "Yakin mau batalin pengajuan cuti ini?"},
    "Are you sure you want to delete holiday": {"id": "Yakin ingin menghapus hari libur", "idc": "Yakin mau hapus hari libur"},
    "As needed": {"id": "Sesuai kebutuhan", "idc": "Sesuai kebutuhan"},
    "At least 8 characters": {"id": "Minimal 8 karakter", "idc": "Minimal 8 karakter"},
    "At least 8 characters (letters & numbers)": {"id": "Minimal 8 karakter (huruf & angka)", "idc": "Minimal 8 karakter (huruf & angka)"},
    "Audit Log Details": {"id": "Rincian Log Audit", "idc": "Rincian Log Audit"},
    "Audit Logs": {"id": "Audit log", "idc": "Audit Log"},
    "Audit Logs & Activity Trail": {"id": "Audit Log & Jejak Aktivitas", "idc": "Audit Log & Jejak Aktivitas"},
    "Authentication & Logins": {"id": "Autentikasi & Login", "idc": "Autentikasi & Login"},
    "Auto Holiday": {"id": "Auto Libur", "idc": "Auto Libur"},
    "Automatic 🎉": {"id": "Otomatis 🎉", "idc": "Auto 🎉"},
    "Automatically connect team leave schedule to Google Calendar, Apple Calendar, or Outlook.": {"id": "Hubungkan jadwal cuti tim ke Google Calendar, Apple Calendar, atau Outlook secara otomatis.", "idc": "Sambungin jadwal cuti tim ke Google Calendar, Apple Calendar, atau Outlook otomatis."},
    "Cancel Leave Request": {"id": "Batalkan Cuti", "idc": "Batalin Cuti"},
    "Change Language": {"id": "Ubah Bahasa", "idc": "Ganti Bahasa"},
    "Close": {"id": "Tutup", "idc": "Tutup"},
    "Company & SMTP": {"id": "Perusahaan & SMTP", "idc": "Company & SMTP"},
    "Data Operations & Changes": {"id": "Operasi & Perubahan Data", "idc": "Operasi & Perubahan Data"},
    "Date Range": {"id": "Rentang Tanggal", "idc": "Rentang Tanggal"},
    "Delete Department": {"id": "Hapus Departemen", "idc": "Hapus Divisi"},
    "Delete Leave Type": {"id": "Hapus Jenis Cuti", "idc": "Hapus Tipe Cuti"},
    "Delete Profile Photo": {"id": "Hapus Foto Profil", "idc": "Hapus Foto Profil"},
    "Download System Backup": {"id": "Unduh Backup Sistem", "idc": "Download Backup Sistem"},
    "Edit Company": {"id": "Edit Perusahaan", "idc": "Edit Company"},
    "Edit Department": {"id": "Edit Departemen", "idc": "Edit Divisi"},
    "Edit Employee": {"id": "Edit Karyawan", "idc": "Edit Karyawan"},
    "Edit Leave Type": {"id": "Edit Jenis Cuti", "idc": "Edit Tipe Cuti"},
    "Employee Import Completed": {"id": "Import Karyawan Selesai", "idc": "Import Karyawan Selesai"},
    "Employees & Profile": {"id": "Karyawan & Profil", "idc": "Karyawan & Profil"},
    "Export Excel (.xlsx)": {"id": "Ekspor Excel (.xlsx)", "idc": "Ekspor Excel (.xlsx)"},
    "Export Excel Report": {"id": "Ekspor Laporan Excel", "idc": "Ekspor Laporan Excel"},
    "Filter": {"id": "Filter", "idc": "Filter"},
    "From": {"id": "Dari", "idc": "Dari"},
    "History Import Completed": {"id": "Import Riwayat Selesai", "idc": "Import Riwayat Selesai"},
    "IP & Device": {"id": "IP & Perangkat", "idc": "IP & Perangkat"},
    "IP Address": {"id": "IP Address", "idc": "IP Address"},
    "IP, target, details...": {"id": "IP, target, detail...", "idc": "IP, target, detail..."},
    "Leave & Approvals": {"id": "Cuti & Approval", "idc": "Cuti & Approval"},
    "Login Failed": {"id": "Login Gagal", "idc": "Login Gagal"},
    "Login Successful": {"id": "Login Berhasil", "idc": "Login Berhasil"},
    "Logout": {"id": "Logout", "idc": "Logout"},
    "No audit logs found": {"id": "Belum ada log audit yang sesuai", "idc": "Belum ada log audit yang sesuai"},
    "Operation Details": {"id": "Rincian Operasi", "idc": "Rincian Operasi"},
    "Operation Time": {"id": "Waktu Operasi", "idc": "Waktu Operasi"},
    "Payload & Data Details (JSON)": {"id": "Payload & Rincian Data (JSON)", "idc": "Payload & Rincian Data (JSON)"},
    "Permanently Delete Employee": {"id": "Hapus Karyawan Permanen", "idc": "Hapus Karyawan Permanen"},
    "Record of all operational activities and system data changes for Administrators.": {"id": "Rekaman seluruh aktivitas operasional dan perubahan data sistem khusus Administrator.", "idc": "Rekaman semua aktivitas operasional dan perubahan data sistem khusus Administrator."},
    "Reject Leave Request": {"id": "Tolak Cuti", "idc": "Tolak Cuti"},
    "Reset Filter": {"id": "Reset Filter", "idc": "Reset Filter"},
    "Restore Leave Type": {"id": "Pulihkan Jenis Cuti", "idc": "Balikin Jenis Cuti"},
    "Search Keywords": {"id": "Cari Kata Kunci", "idc": "Cari Kata Kunci"},
    "Security: CSRF Verification Failed": {"id": "Keamanan: CSRF Gagal", "idc": "Keamanan: CSRF Gagal"},
    "Submit Leave Request": {"id": "Pengajuan Cuti", "idc": "Pengajuan Cuti"},
    "Switch Active Company": {"id": "Ganti Perusahaan Aktif", "idc": "Ganti Company Aktif"},
    "Sync Public Holidays": {"id": "Sinkronisasi Hari Libur", "idc": "Sync Hari Libur"},
    "System": {"id": "Sistem", "idc": "Sistem"},
    "System / Anonymous": {"id": "Sistem / Anonim", "idc": "Sistem / Anonim"},
    "System, Backup & Import": {"id": "Sistem, Backup & Import", "idc": "Sistem, Backup & Import"},
    "Target": {"id": "Target", "idc": "Target"},
    "Target Entity": {"id": "Target Entitas", "idc": "Target Entitas"},
    "Time (WIB)": {"id": "Waktu (WIB)", "idc": "Waktu (WIB)"},
    "To": {"id": "Sampai", "idc": "Sampai"},
    "Today's Activity": {"id": "Aktivitas Hari Ini", "idc": "Aktivitas Hari Ini"},
    "Total Filtered Logs": {"id": "Total Log Terfilter", "idc": "Total Log Terfilter"},
    "Try adjusting your filters or date range search.": {"id": "Coba sesuaikan filter atau rentang tanggal pencarian.", "idc": "Coba sesuaikan filter atau rentang tanggal pencarian."},
    "Unarchive Approval History": {"id": "Buka Arsip Approval", "idc": "Buka Arsip Approval"},
    "Unarchive Employee": {"id": "Buka Arsip Karyawan", "idc": "Buka Arsip Karyawan"},
    "Update Approval Workflow": {"id": "Update Alur Approval", "idc": "Update Alur Approval"},
    "Update Profile": {"id": "Update Profil", "idc": "Update Profil"},
    "Update SMTP Settings": {"id": "Update Pengaturan SMTP", "idc": "Update Pengaturan SMTP"},
    "Upload Profile Photo": {"id": "Upload Foto Profil", "idc": "Upload Foto Profil"},
    "User / Actor": {"id": "User / Aktor", "idc": "User / Aktor"},
    "User Agent / Browser": {"id": "User Agent / Browser", "idc": "User Agent / Browser"},
    "View Details": {"id": "Lihat Rincian", "idc": "Lihat Rincian"},
    "Year-End Leave Balance Rollover": {"id": "Tutup Buku Saldo Tahunan", "idc": "Tutup Buku Saldo Tahunan"},
    "Back": {"id": "Kembali", "idc": "Balik"},
    "Back to Sign In": {"id": "Kembali ke Halaman Masuk", "idc": "Balik ke Login"},
    "Balance Details": {"id": "Detail saldo", "idc": "Detail Saldo"},
    "By": {"id": "Oleh", "idc": "Sama"},
    "BY:": {"id": "OLEH:", "idc": "SAMA:"},
    "By:": {"id": "Oleh:", "idc": "Sama:"},
    "Calendar": {"id": "Kalender", "idc": "Kalender"},
    "Calendar Sync (.ics)": {"id": "Sinkronisasi Kalender (.ics)", "idc": "Sync Kalender (.ics)"},
    "Calendar synchronization link updated.": {"id": "Link sinkronisasi kalender berhasil diperbarui.", "idc": "Link sync kalender udah di-refresh."},
    "Cancel": {"id": "Batal", "idc": "Batal"},
    "Cancel Request": {"id": "Batalkan Pengajuan", "idc": "Batalin Pengajuan"},
    "Cancelled": {"id": "Dibatalkan", "idc": "Dibatalkan"},
    "Category": {"id": "Kategori", "idc": "Kategori"},
    "Change Email": {"id": "Ubah Email", "idc": "Ganti Email"},
    "Change Password": {"id": "Ubah Password", "idc": "Ganti Password"},
    "Check your email inbox and enter the 6-digit OTP code to verify your password reset request.": {"id": "Periksa kotak masuk email Anda dan masukkan 6-digit kode OTP untuk memverifikasi permintaan reset kata sandi.", "idc": "Cek inbox email kamu dan masukin 6 digit kode OTP buat verifikasi reset password."},
    "Choose your account password verification method": {"id": "Pilih metode verifikasi kata sandi akun Anda", "idc": "Pilih metode verifikasi password akun kamu"},
    "Click on a label to view balance details.": {"id": "Klik label untuk melihat rincian saldo.", "idc": "Klik label buat liat rincian saldo."},
    "Code expires in 15 minutes.": {"id": "Kode berlaku selama 15 menit.", "idc": "Kode berlaku 15 menit."},
    "Colleagues who are currently on leave or scheduled within the next 7 days.": {"id": "Rekan kerja yang sedang atau akan cuti dalam 7 hari ke depan.", "idc": "Temen kantor yang lagi atau mau cuti 7 hari ke depan."},
    "Collective Leave": {"id": "Cuti Bersama", "idc": "Cuti Bersama"},
    "Company": {"id": "Perusahaan", "idc": "Company"},
    "Company already exists.": {"id": "Perusahaan sudah ada.", "idc": "Company-nya udah ada."},
    "Company Holiday": {"id": "Libur Perusahaan", "idc": "Libur Perusahaan"},
    "Company is not available.": {"id": "Perusahaan tidak tersedia.", "idc": "Company-nya ga tersedia."},
    "Company Name": {"id": "Nama Perusahaan", "idc": "Nama Company"},
    "Company name is required.": {"id": "Nama perusahaan harus diisi.", "idc": "Nama company wajib diisi."},
    "Company not found.": {"id": "Perusahaan tidak ditemukan.", "idc": "Company ga ketemu."},
    "Company SMTP settings updated.": {"id": "Pengaturan SMTP perusahaan berhasil diperbarui!", "idc": "Pengaturan SMTP perusahaan udah diperbarui."},
    "Company Special Holiday": {"id": "Libur Khusus Perusahaan", "idc": "Libur Khusus Perusahaan"},
    "Configure leave policies, quotas, and organization approval workflows.": {"id": "Atur kebijakan leave, kuota, dan alur persetujuan organisasi.", "idc": "Atur kebijakan cuti, kuota, dan alur approval organisasi."},
    "Confirm": {"id": "Konfirmasi", "idc": "Konfirmasi"},
    "Confirm New Password": {"id": "Konfirmasi Kata Sandi Baru", "idc": "Konfirmasi Password Baru"},
    "Confirm password": {"id": "Konfirmasi password", "idc": "Konfirmasi password"},
    "Consecutive Days Off": {"id": "Hari Libur Beruntun", "idc": "Hari Libur Beruntun"},
    "Contains letters and numbers": {"id": "Mengandung huruf dan angka", "idc": "Ada huruf dan angka"},
    "Copied!": {"id": "Tersalin!", "idc": "Tersalin!"},
    "Copy": {"id": "Salin", "idc": "Salin"},
    "Copy Link": {"id": "Salin Link", "idc": "Salin Link"},
    "Create a strong new password.": {"id": "Buat kata sandi baru yang kuat.", "idc": "Bikin password baru yang kuat."},
    "Create New Password": {"id": "Buat Kata Sandi Baru", "idc": "Bikin Password Baru"},
    "CREATED": {"id": "DIBUAT", "idc": "DIBUAT"},
    "Created": {"id": "Dibuat", "idc": "Dibuat"},
    "Current password": {"id": "Password saat ini", "idc": "Password saat ini"},
    "Current password is incorrect.": {"id": "Password saat ini salah.", "idc": "Password lama salah."},
    "Custom Domain": {"id": "Domain custom", "idc": "Custom Domain"},
    "Dashboard": {"id": "Dashboard", "idc": "Dashboard"},
    "Database & System Backup": {"id": "Backup Database & Sistem", "idc": "Backup Database & Sistem"},
    "Date": {"id": "Tanggal", "idc": "Tanggal"},
    "Date and holiday name are required.": {"id": "Tanggal dan nama hari libur wajib diisi.", "idc": "Tanggal dan nama hari libur wajib diisi ya."},
    "Date format is invalid.": {"id": "Format tanggal tidak valid.", "idc": "Format tanggalnya ga valid."},
    "Day": {"id": "Hari", "idc": "Hari"},
    "days": {"id": "hari", "idc": "hari"},
    "Days": {"id": "Hari", "idc": "Hari"},
    "days available": {"id": "hari tersedia", "idc": "hari tersedia"},
    "Days per Year": {"id": "Hari per Tahun", "idc": "Hari per Tahun"},
    "Delegate": {"id": "Delegasi", "idc": "Backup"},
    "Delegate is not available.": {"id": "Delegate tidak tersedia.", "idc": "Backup-nya ga tersedia."},
    "Delegation / Backup": {"id": "Delegasi / Backup", "idc": "Delegasi / Backup"},
    "Delete department?": {"id": "Hapus departemen?", "idc": "Hapus divisi?"},
    "Delete holiday": {"id": "Hapus hari libur", "idc": "Hapus hari libur"},
    "Delete leave type?": {"id": "Hapus jenis cuti?", "idc": "Hapus tipe cuti?"},
    "Delete Photo": {"id": "Hapus Foto", "idc": "Hapus Foto"},
    "Department (for employee)": {"id": "Departemen (untuk employee)", "idc": "Divisi (untuk employee)"},
    "Department Head": {"id": "Kepala Departemen", "idc": "Head Divisi"},
    "Department Head (optional)": {"id": "Kepala Departemen (opsional)", "idc": "Head Divisi (opsional)"},
    "Department Name": {"id": "Nama Departemen", "idc": "Nama Divisi"},
    "Department name is required.": {"id": "Nama departemen harus diisi.", "idc": "Nama divisi wajib diisi."},
    "Departments": {"id": "Departemen", "idc": "Divisi"},
    "Details will appear here.": {"id": "Rincian akan muncul di sini.", "idc": "Rincian bakal muncul di sini."},
    "Did not receive the code?": {"id": "Tidak menerima kode?", "idc": "Ga dapet kodenya?"},
    "Did not receive the email?": {"id": "Tidak menerima email?", "idc": "Ga dapet emailnya?"},
    "Direct Login Link:": {"id": "Link Akses Masuk Langsung:", "idc": "Link Akses Masuk Langsung:"},
    "Display delegate field on request form.": {"id": "Tampilkan field delegasi pada form pengajuan.", "idc": "Tampilin field delegasi di form pengajuan."},
    "Document Status": {"id": "Status Dokumen", "idc": "Status Dokumen"},
    "Done": {"id": "Selesai", "idc": "Selesai"},
    "Download .ics file": {"id": "Unduh file .ics", "idc": "Download file .ics"},
    "Download a complete backup of the database and system attachments anytime.": {"id": "Unduh salinan cadangan lengkap database dan berkas lampiran sistem kapan saja.", "idc": "Download backup lengkap database dan file sistem kapan aja."},
    "Download ZIP (Full: SQL + JSON + Files)": {"id": "Download ZIP (Lengkap: SQL + JSON + Berkas)", "idc": "Download ZIP (Lengkap: SQL + JSON + File)"},
    "Edit Company": {"id": "Edit Perusahaan", "idc": "Edit Company"},
    "Edit Department": {"id": "Edit Departemen", "idc": "Edit Divisi"},
    "Edit Employee": {"id": "Edit Karyawan", "idc": "Edit Karyawan"},
    "Edit Leave Type": {"id": "Edit Jenis Cuti", "idc": "Edit Tipe Cuti"},
    "Email Identity Verification": {"id": "Verifikasi Identitas via Email", "idc": "Verifikasi Identitas via Email"},
    "Email is already registered.": {"id": "Email sudah terdaftar.", "idc": "Email-nya udah terdaftar."},
    "Email or password is incorrect.": {"id": "Email atau password salah.", "idc": "Email atau passwordnya salah."},
    "Email Sent Successfully!": {"id": "Email Berhasil Dikirim!", "idc": "Email Berhasil Dikirim!"},
    "Email Settings": {"id": "Pengaturan email", "idc": "Pengaturan Email"},
    "email@company.com": {"id": "email@perusahaan.com", "idc": "email@company.com"},
    "Employee deletion must be done via the Delete button on the Admin page.": {"id": "Penghapusan karyawan harus dilakukan melalui tombol Hapus di halaman Admin.", "idc": "Hapus karyawan harus lewat tombol Hapus di halaman Admin ya."},
    "Employee Information": {"id": "Informasi Karyawan", "idc": "Informasi Karyawan"},
    "Employees": {"id": "Karyawan", "idc": "Karyawan"},
    "Employees can choose a backup when requesting leave.": {"id": "Karyawan bisa memilih backup saat mengajukan cuti.", "idc": "Karyawan bisa milih backup pas ngajuin cuti."},
    "Enable leave delegation": {"id": "Aktifkan delegasi cuti", "idc": "Aktifin delegasi cuti"},
    "End date": {"id": "Tanggal selesai", "idc": "Tanggal selesai"},
    "End date must be after or equal to start date.": {"id": "Tanggal selesai harus setelah atau sama dengan tanggal mulai.", "idc": "Tanggal selesai harus sama/lebih akhir dari tanggal mulai."},
    "Enter current password": {"id": "Masukkan password saat ini", "idc": "Masukin password saat ini"},
    "Enter Now": {"id": "Masuk Sekarang", "idc": "Masuk Sekarang"},
    "Enter password": {"id": "Masukkan password", "idc": "Masukin password"},
    "Enter the 6-digit OTP code from email": {"id": "Masukkan 6 digit kode OTP dari email", "idc": "Masukin 6 digit kode OTP dari email"},
    "Enter Verification Code": {"id": "Masukkan Kode Verifikasi", "idc": "Masukin Kode Verifikasi"},
    "Enter workspace as": {"id": "Masuk ke workspace sebagai", "idc": "Masuk ke workspace sebagai"},
    "Enter your current password and set a new password directly without OTP.": {"id": "Masukkan password saat ini dan tentukan password baru langsung tanpa perlu OTP.", "idc": "Masukin password saat ini terus bikin password baru langsung tanpa perlu OTP."},
    "Enter your registered work email address. We will send an OTP verification code.": {"id": "Masukkan alamat email kerja yang terdaftar di sistem. Kami akan mengirimkan kode verifikasi OTP.", "idc": "Masukin email kerja yang terdaftar. Nanti kami kirim kode OTP-nya."},
    "Export Data": {"id": "Ekspor data", "idc": "Ekspor Data"},
    "Fast access & native app experience.": {"id": "Akses cepat & pengalaman seperti aplikasi bawaan.", "idc": "Akses cepet & serasa aplikasi bawaan."},
    "Find the most efficient break opportunities throughout the year.": {"id": "Temukan peluang waktu istirahat yang paling efisien sepanjang tahun.", "idc": "Cari momen libur paling cuan buat setahun ini."},
    "First Page": {"id": "Halaman Pertama", "idc": "Halaman Pertama"},
    "For workspace security, changing password requires verifying a 6-digit code sent to your registered email.": {"id": "Untuk keamanan workspace, perubahan kata sandi memerlukan verifikasi kode 6-digit yang dikirim ke email terdaftar.", "idc": "Biar workspace aman, ganti password wajib verifikasi kode 6-digit yang dikirim ke email terdaftar."},
    "Forgot Password": {"id": "Lupa Password", "idc": "Lupa Password"},
    "Forgot password?": {"id": "Lupa password?", "idc": "Lupa password?"},
    "Forgot Password? (Email OTP)": {"id": "Lupa Password? (OTP Email)", "idc": "Lupa Password? (OTP Email)"},
    "Full Day": {"id": "Full Day", "idc": "Full Day"},
    "Full Name": {"id": "Nama Lengkap", "idc": "Nama Lengkap"},
    "get": {"id": "dapat libur", "idc": "dapet libur"},
    "Got it": {"id": "Mengerti", "idc": "Paham"},
    "Grant Leave": {"id": "Grant cuti", "idc": "Grant cuti"},
    "has few long weekends 😭": {"id": "sepi long weekend-nya 😭", "idc": "sepi long weekend-nya 😭"},
    "Head": {"id": "Kepala", "idc": "Head"},
    "History": {"id": "Riwayat", "idc": "Riwayat"},
    "Holiday Category": {"id": "Kategori Libur", "idc": "Kategori Libur"},
    "Holiday Date": {"id": "Tanggal Libur", "idc": "Tanggal Libur"},
    "Holiday deleted! 🗑️": {"id": "Hari libur berhasil dihapus! 🗑️", "idc": "Hari libur udah dihapus! 🗑️"},
    "Holiday Name": {"id": "Nama Hari Libur", "idc": "Nama Hari Libur"},
    "Holiday updated! ✅": {"id": "Hari libur berhasil diperbarui! ✅", "idc": "Hari libur udah di-update! ✅"},
    "Holidays": {"id": "Libur", "idc": "Libur"},
    "Holidays & Long Weekend": {"id": "Hari libur & Long Weekend", "idc": "Hari libur & Long Weekend"},
    "Holidays List": {"id": "Daftar Hari Libur", "idc": "Daftar Hari Libur"},
    "Home": {"id": "Beranda", "idc": "Beranda"},
    "Inbox": {"id": "Inbox", "idc": "Inbox"},
    "Install App": {"id": "Install App", "idc": "Install App"},
    "Install App (PWA)": {"id": "Install Aplikasi (PWA)", "idc": "Install Aplikasi (PWA)"},
    "Install on iPhone / iPad": {"id": "Install di iPhone / iPad", "idc": "Install di iPhone / iPad"},
    "Install People by Triont": {"id": "Install People by Triont", "idc": "Install People by Triont"},
    "Install to Home Screen": {"id": "Install ke Layar Utama", "idc": "Install ke Layar Utama"},
    "Invalid action.": {"id": "Aksi tidak valid.", "idc": "Aksinya ga valid."},
    "Job Title / Role": {"id": "Jabatan / Role", "idc": "Jabatan / Role"},
    "JSON (.json)": {"id": "JSON (.json)", "idc": "JSON (.json)"},
    "Language updated.": {"id": "Bahasa berhasil diperbarui.", "idc": "Bahasa udah diganti."},
    "Last Page": {"id": "Halaman Terakhir", "idc": "Halaman Terakhir"},
    "Last updated": {"id": "Terakhir diperbarui", "idc": "Terakhir di-update"},
    "LAST UPDATED": {"id": "TERAKHIR DIPERBARUI", "idc": "TERAKHIR DI-UPDATE"},
    "Last Updated": {"id": "Terakhir Diperbarui", "idc": "Terakhir Di-update"},
    "Leave": {"id": "Cuti", "idc": "Cuti"},
    "Leave Balances": {"id": "Saldo cuti", "idc": "Saldo Cuti"},
    "Leave balances for this year have not been allocated to your account yet.": {"id": "Saldo cuti untuk tahun ini belum dialokasikan untuk akun Anda.", "idc": "Saldo cuti buat tahun ini belum dialokasikan ke akun kamu."},
    "Leave composition": {"id": "Komposisi leave", "idc": "Komposisi cuti"},
    "Leave date": {"id": "Tanggal cuti", "idc": "Tanggal cuti"},
    "leave days": {"id": "hari cuti", "idc": "hari cuti"},
    "Leave Details": {"id": "Rincian Cuti", "idc": "Rincian Cuti"},
    "Leave grant saved.": {"id": "Grant cuti berhasil disimpan.", "idc": "Grant cutinya udah disimpan."},
    "Leave Name": {"id": "Nama Cuti", "idc": "Nama Cuti"},
    "Leave name is required.": {"id": "Nama cuti harus diisi.", "idc": "Nama cuti wajib diisi."},
    "Leave planner": {"id": "Perencana cuti", "idc": "Planner cuti"},
    "Leave Request & Approval Slip": {"id": "Bukti Pengajuan & Persetujuan Cuti", "idc": "Bukti Pengajuan & Approval Cuti"},
    "Leave request approved!": {"id": "Pengajuan cuti berhasil disetujui!", "idc": "Pengajuan cuti udah di-approve!"},
    "Leave request cancelled successfully.": {"id": "Pengajuan cuti berhasil dibatalkan.", "idc": "Pengajuan cuti berhasil dibatalkan."},
    "Leave request rejected!": {"id": "Pengajuan cuti berhasil ditolak!", "idc": "Pengajuan cuti ditolak!"},
    "Leave request submitted. Waiting for approval.": {"id": "Pengajuan cuti berhasil dikirim! Menunggu persetujuan.", "idc": "Pengajuan cuti udah dikirim. Tinggal nunggu approval."},
    "Leave settings": {"id": "Pengaturan cuti", "idc": "Pengaturan cuti"},
    "Leave Slip": {"id": "Bukti Cuti", "idc": "Bukti Cuti"},
    "Leave type deleted.": {"id": "Jenis cuti berhasil dihapus.", "idc": "Tipe cutinya udah dihapus."},
    "Leave type is not available.": {"id": "Jenis cuti tidak tersedia.", "idc": "Tipe cutinya ga tersedia."},
    "Leave Types": {"id": "Jenis cuti", "idc": "Jenis Cuti"},
    "leave types shown": {"id": "jenis cuti ditampilkan", "idc": "tipe cuti ditampilin"},
    "Level and role are required.": {"id": "Level dan role harus diisi.", "idc": "Level dan role wajib diisi."},
    "Link Copied!": {"id": "Link Disalin!", "idc": "Link Disalin!"},
    "Link Sent Successfully!": {"id": "Link Berhasil Dikirim!", "idc": "Link Berhasil Dikirim!"},
    "List of national holidays, collective leave, and smart leave strategies throughout the year": {"id": "Daftar hari libur nasional, cuti bersama, dan strategi ambil cuti hemat sepanjang tahun", "idc": "Daftar libur nasional, cuti bersama, dan trik libur hemat setahun"},
    "Login as": {"id": "Login sebagai", "idc": "Login sebagai"},
    "Login as Employee": {"id": "Login sebagai Karyawan", "idc": "Login sebagai Karyawan"},
    "Long Weekend History": {"id": "Riwayat Long Weekend", "idc": "Riwayat Long Weekend"},
    "Long Weekend Plans": {"id": "Rencana Long Weekend", "idc": "Rencana Long Weekend"},
    "Make sure national holidays are synced or add custom holidays.": {"id": "Pastikan data hari libur nasional sudah tersinkronkan atau tambahkan hari libur kustom.", "idc": "Pastikan data libur nasional udah disinkronkan atau tambah libur sendiri."},
    "Manage Employee Status": {"id": "Kelola Status Karyawan", "idc": "Kelola Status Karyawan"},
    "Manage Leave Balances": {"id": "Atur Saldo Cuti", "idc": "Atur Saldo Cuti"},
    "Manage organizational structure and person in charge of each unit.": {"id": "Kelola struktur organisasi dan penanggung jawab setiap unit.", "idc": "Kelola struktur organisasi dan PIC tiap unit."},
    "Mandatory document attachment on request": {"id": "Wajib lampiran dokumen saat pengajuan", "idc": "Wajib lampiran dokumen pas pengajuan"},
    "Member Count": {"id": "Jumlah Anggota", "idc": "Jumlah Anggota"},
    "Menu": {"id": "Menu", "idc": "Menu"},
    "Monitor quota allocation, usage, and remaining leave balances of all employees.": {"id": "Pantau alokasi kuota, penggunaan, dan sisa saldo cuti seluruh karyawan.", "idc": "Pantau alokasi kuota, pemakaian, dan sisa saldo cuti seluruh karyawan."},
    "Monitor your leave balances and items that need attention today.": {"id": "Pantau saldo leave dan hal yang butuh perhatian hari ini.", "idc": "Pantau saldo cuti dan hal yang butuh perhatian hari ini."},
    "Name": {"id": "Nama", "idc": "Nama"},
    "name@company.com": {"id": "nama@perusahaan.com", "idc": "nama@company.com"},
    "National Holiday": {"id": "Libur Nasional", "idc": "Libur Nasional"},
    "National holidays and collective leave list synchronized! ✅": {"id": "Daftar hari libur nasional dan cuti bersama berhasil disinkronkan! ✅", "idc": "Daftar libur nasional dan cuti bersama udah disinkronkan! ✅"},
    "Needs Approval": {"id": "Butuh persetujuan", "idc": "Butuh Persetujuan"},
    "New holiday added! ✅": {"id": "Hari libur baru berhasil ditambahkan! ✅", "idc": "Hari libur baru udah ditambah! ✅"},
    "New password": {"id": "Password baru", "idc": "Password baru"},
    "New Password": {"id": "Kata Sandi Baru", "idc": "Password Baru"},
    "New passwords do not match.": {"id": "Konfirmasi password baru tidak cocok.", "idc": "Konfirmasi password barunya belum sama."},
    "Next": {"id": "Berikutnya", "idc": "Berikutnya"},
    "No colleagues are scheduled on leave in the next 7 days.": {"id": "Tidak ada rekan kerja yang sedang atau akan cuti dalam 7 hari ke depan.", "idc": "Ga ada yang cuti 7 hari ke depan."},
    "No delegate": {"id": "Tidak ada delegasi", "idc": "Ga ada backup"},
    "No Head": {"id": "Tanpa kepala", "idc": "Tanpa Head"},
    "No leave balance yet": {"id": "Belum ada saldo cuti", "idc": "Belum ada saldo cuti"},
    "No leave requests yet.": {"id": "Belum ada pengajuan cuti.", "idc": "Belum ada pengajuan cuti."},
    "No long weekend data for year": {"id": "Belum ada data long weekend di tahun", "idc": "Belum ada data long weekend di tahun"},
    "No pending requests.": {"id": "Tidak ada pengajuan yang menunggu.", "idc": "Ga ada pengajuan yang nunggu."},
    "No policy description yet.": {"id": "Belum ada deskripsi kebijakan.", "idc": "Belum ada deskripsi kebijakan."},
    "of": {"id": "dari", "idc": "dari"},
    "off non-stop! 🔥": {"id": "non-stop! 🔥", "idc": "non-stop! 🔥"},
    "Official Verified Document": {"id": "Dokumen Resmi Terverifikasi", "idc": "Dokumen Resmi Terverifikasi"},
    "Only pending leave requests can be cancelled.": {"id": "Hanya pengajuan cuti yang berstatus pending yang dapat dibatalkan.", "idc": "Cuma pengajuan pending yang bisa dibatalin."},
    "Open in New Tab": {"id": "Buka di Tab Baru", "idc": "Buka di Tab Baru"},
    "Open inbox": {"id": "Buka inbox", "idc": "Buka inbox"},
    "Open simulation session or copy quick access link.": {"id": "Buka sesi simulasi atau salin link akses cepat.", "idc": "Buka sesi simulasi atau salin link akses cepat."},
    "Open Sync Settings": {"id": "Buka Pengaturan Sync", "idc": "Buka Pengaturan Sync"},
    "optional": {"id": "opsional", "idc": "opsional"},
    "OTP Code (6 Digits)": {"id": "Kode OTP (6 Digit)", "idc": "Kode OTP (6 Digit)"},
    "OTP Verification via Email": {"id": "Verifikasi OTP via Email", "idc": "Verifikasi OTP via Email"},
    "Password must be at least 8 characters and include letters and numbers.": {"id": "Password minimal 8 karakter dan harus berisi huruf serta angka.", "idc": "Password minimal 8 karakter, pakai huruf dan angka ya."},
    "Password requirements:": {"id": "Ketentuan password:", "idc": "Syarat password:"},
    "Password updated.": {"id": "Password berhasil diperbarui.", "idc": "Password udah diganti."},
    "Past": {"id": "Sudah Lewat", "idc": "Udah Lewat"},
    "Past / Inactive": {"id": "Sudah Lewat / Tidak Aktif", "idc": "Udah Lewat / Ga Aktif"},
    "Pending": {"id": "Menunggu", "idc": "Menunggu"},
    "people": {"id": "orang", "idc": "orang"},
    "People by Triont • HR Management System": {"id": "People by Triont • Sistem Manajemen SDM", "idc": "People by Triont • Sistem Manajemen SDM"},
    "Per page:": {"id": "Per halaman:", "idc": "Per halaman:"},
    "per year": {"id": "per tahun", "idc": "per tahun"},
    "Period": {"id": "Periode", "idc": "Periode"},
    "Period has ended": {"id": "Periode telah berakhir", "idc": "Periode udah berakhir"},
    "Personal Workspace": {"id": "Workspace pribadi", "idc": "Workspace pribadi"},
    "Please complete all required fields.": {"id": "Harap isi semua field yang wajib.", "idc": "Isi semua field wajib dulu ya."},
    "Please enter a new password for your account.": {"id": "Silakan masukkan kata sandi baru untuk akun Anda.", "idc": "Silakan masukin password baru buat akun kamu."},
    "Please enter name, email, and password.": {"id": "Harap isi nama, email, dan password.", "idc": "Isi nama, email, dan password dulu."},
    "Please fill in SMTP configuration first.": {"id": "Harap isi konfigurasi SMTP terlebih dahulu.", "idc": "Isi konfigurasi SMTP dulu ya."},
    "Please sign in first.": {"id": "Silakan login terlebih dahulu.", "idc": "Login dulu ya."},
    "Previous": {"id": "Sebelumnya", "idc": "Sebelumnya"},
    "Primary Language": {"id": "Bahasa utama", "idc": "Bahasa utama"},
    "Print / Save PDF": {"id": "Cetak / Simpan PDF", "idc": "Cetak / Simpan PDF"},
    "Print Leave Slip": {"id": "Cetak Bukti Cuti", "idc": "Cetak Bukti Cuti"},
    "Printed Date:": {"id": "Tanggal Cetak:", "idc": "Tanggal Cetak:"},
    "Profile Picture": {"id": "Foto Profil", "idc": "Foto Profil"},
    "Profile updated.": {"id": "Profil berhasil diperbarui.", "idc": "Profil udah ke-update."},
    "Quota": {"id": "Kuota", "idc": "Kuota"},
    "Reason": {"id": "Alasan", "idc": "Alasan"},
    "Recent Requests": {"id": "Pengajuan terkini", "idc": "Pengajuan Terkini"},
    "Recipient Employee": {"id": "Karyawan Penerima", "idc": "Karyawan Penerima"},
    "records": {"id": "data", "idc": "data"},
    "Reject leave request?": {"id": "Tolak pengajuan cuti?", "idc": "Tolak pengajuan cuti?"},
    "Rejected": {"id": "Ditolak", "idc": "Ditolak"},
    "Remaining": {"id": "Sisa", "idc": "Sisa"},
    "Remember Old Password": {"id": "Ingat Password Lama", "idc": "Inget Password Lama"},
    "Remember your password?": {"id": "Ingat password Anda?", "idc": "Inget password kamu?"},
    "Repeat new password": {"id": "Ulangi kata sandi baru", "idc": "Ulangi password baru"},
    "Request": {"id": "Ajukan", "idc": "Ajukan"},
    "REQUEST APPROVED": {"id": "PENGAJUAN DISETUJUI", "idc": "PENGAJUAN DISETUJUI"},
    "Request duration:": {"id": "Durasi pengajuan:", "idc": "Durasi pengajuan:"},
    "Request Features": {"id": "Fitur Pengajuan", "idc": "Fitur Pengajuan"},
    "Request Reason:": {"id": "Alasan Pengajuan:", "idc": "Alasan Pengajuan:"},
    "Requests waiting for you": {"id": "Pengajuan yang menunggu Anda", "idc": "Pengajuan yang nunggu kamu"},
    "Resend OTP": {"id": "Kirim Ulang OTP", "idc": "Kirim Ulang OTP"},
    "Reset calendar feed link? Old links connected to Google/Apple Calendar will stop working.": {"id": "Reset link feed kalender? Link lama yang tersambung di Google/Apple Calendar tidak akan berfungsi lagi.", "idc": "Reset link feed kalender? Link lama yang nyambung di Google/Apple Calendar ga bakal berfungsi lagi."},
    "Reset new link": {"id": "Reset link baru", "idc": "Bikin link baru"},
    "Reset password securely.": {"id": "Reset kata sandi dengan aman.", "idc": "Reset kata sandi dengan aman."},
    "Reset your password": {"id": "Reset kata sandi Anda", "idc": "Reset password kamu"},
    "Return to Admin Account": {"id": "Kembali ke Akun Admin", "idc": "Balik ke Akun Admin"},
    "Returned to Super Admin session.": {"id": "Kembali ke sesi Super Admin.", "idc": "Balik ke sesi Super Admin."},
    "Save & Sign In": {"id": "Simpan & Masuk", "idc": "Simpan & Login"},
    "Save Holiday": {"id": "Simpan Hari Libur", "idc": "Simpan Hari Libur"},
    "Save Profile": {"id": "Simpan profil", "idc": "Simpan profil"},
    "Search departments": {"id": "Cari departemen", "idc": "Cari divisi"},
    "Search leave types": {"id": "Cari jenis cuti", "idc": "Cari tipe cuti"},
    "Security check failed. Please try again.": {"id": "Pemeriksaan keamanan gagal. Silakan coba lagi.", "idc": "Cek keamanan gagal. Coba ulang ya."},
    "Select dates": {"id": "Pilih tanggal", "idc": "Pilih tanggal"},
    "Select dates from the calendar.": {"id": "Pilih tanggal dari kalender.", "idc": "Pilih tanggal dari kalender."},
    "Select leave type": {"id": "Pilih jenis leave", "idc": "Pilih tipe cuti"},
    "Select or allocate a leave type to view annual quota details.": {"id": "Pilih atau alokasikan jenis cuti untuk melihat rincian kuota tahunan.", "idc": "Pilih atau alokasikan tipe cuti buat liat rincian kuota tahunan."},
    "Selected dates fall entirely on weekends or public holidays (0 working days).": {"id": "Tanggal yang dipilih merupakan akhir pekan atau hari libur (0 hari kerja).", "idc": "Tanggal yang dipilih libur/weekend semua (0 hari kerja)."},
    "Send 6-digit code to": {"id": "Kirim kode 6 digit ke", "idc": "Kirim kode 6 digit ke"},
    "Send direct link to reset password": {"id": "Kirim tautan langsung untuk mengatur ulang kata sandi", "idc": "Kirim link langsung buat atur ulang password"},
    "Send OTP & Change Password": {"id": "Kirim OTP & Ubah Password", "idc": "Kirim OTP & Ubah Password"},
    "Send OTP Code": {"id": "Kirim Kode OTP", "idc": "Kirim Kode OTP"},
    "Send OTP Code to Email": {"id": "Kirim Kode OTP ke Email", "idc": "Kirim Kode OTP ke Email"},
    "Send Password Reset": {"id": "Kirim Reset Password", "idc": "Kirim Reset Password"},
    "Send password reset instructions to email": {"id": "Kirim instruksi reset kata sandi ke email", "idc": "Kirim instruksi reset kata sandi ke email"},
    "Send Password Reset Link": {"id": "Kirim Link Reset Password", "idc": "Kirim Link Reset Password"},
    "Send Password Reset Link to": {"id": "Kirim Link Reset Password ke", "idc": "Kirim Link Reset Password ke"},
    "Send Reset Email": {"id": "Kirim Email Reset", "idc": "Kirim Email Reset"},
    "Send Reset Link": {"id": "Kirim Link Reset", "idc": "Kirim Link Reset"},
    "Sending...": {"id": "Sedang mengirim...", "idc": "Lagi dikirim..."},
    "Set New Password": {"id": "Setel Kata Sandi Baru", "idc": "Setel Password Baru"},
    "Settings": {"id": "Pengaturan", "idc": "Pengaturan"},
    "Showing": {"id": "Menampilkan", "idc": "Nampilin"},
    "Showing 0 records": {"id": "Menampilkan 0 data", "idc": "Nampilin 0 data"},
    "Showing all": {"id": "Menampilkan semua", "idc": "Nampilin semua"},
    "Sign in": {"id": "Masuk", "idc": "Login"},
    "Sign In": {"id": "Masuk", "idc": "Login"},
    "Sign in now": {"id": "Masuk sekarang", "idc": "Login sekarang"},
    "Sign out": {"id": "Keluar", "idc": "Keluar"},
    "Sign out from People?": {"id": "Logout dari People?", "idc": "Logout dari People?"},
    "SQL Dump (.sql)": {"id": "SQL Dump (.sql)", "idc": "SQL Dump (.sql)"},
    "Start date": {"id": "Tanggal mulai", "idc": "Tanggal mulai"},
    "Starts": {"id": "Mulai", "idc": "Mulai"},
    "Starts Tomorrow": {"id": "Mulai Besok", "idc": "Mulai Besok"},
    "Status": {"id": "Status", "idc": "Status"},
    "Step 1: Get OTP Code": {"id": "Langkah 1: Dapatkan Kode OTP", "idc": "Langkah 1: Dapetin Kode OTP"},
    "Step 2: Enter 6-Digit OTP Code": {"id": "Langkah 2: Masukkan Kode OTP 6-Digit", "idc": "Langkah 2: Masukin Kode OTP 6-Digit"},
    "Submit leave request?": {"id": "Kirim pengajuan cuti?", "idc": "Kirim pengajuan cuti ya?"},
    "Submit request": {"id": "Kirim pengajuan", "idc": "Kirim pengajuan"},
    "Subscribe to team leaves & public holidays in Google / Apple / Outlook": {"id": "Langganan jadwal cuti tim & hari libur langsung di Google / Apple / Outlook", "idc": "Langganan cuti tim & hari libur langsung di Google / Apple / Outlook"},
    "Subscription Guide:": {"id": "Petunjuk Langganan:", "idc": "Cara Langganan:"},
    "Supports JPG, PNG, WEBP. Max 3MB.": {"id": "Mendukung format JPG, PNG, WEBP. Maksimal 3MB.", "idc": "Support JPG, PNG, WEBP. Maks 3MB."},
    "Sync Calendar": {"id": "Sync Kalender", "idc": "Sync Kalender"},
    "Sync National Holidays": {"id": "Sinkronkan Libur Nasional", "idc": "Sinkronkan Libur Nasional"},
    "System": {"id": "Sistem", "idc": "Sistem"},
    "System & HR Authorization": {"id": "Otorisasi Sistem & HR", "idc": "Otorisasi Sistem & HR"},
    "Take": {"id": "Ambil", "idc": "Ambil"},
    "Take leave": {"id": "Ambil cuti", "idc": "Ambil cuti"},
    "Team Calendar": {"id": "Kalender tim", "idc": "Kalender tim"},
    "The approval status has changed. Reload the page and try again.": {"id": "Status approval sudah berubah. Muat ulang halaman dan coba lagi.", "idc": "Status approval-nya udah berubah. Refresh halaman lalu coba lagi."},
    "The leave grant data is invalid.": {"id": "Data grant cuti tidak valid.", "idc": "Data grant cutinya ga valid."},
    "The leave request will be approved for": {"id": "Pengajuan cuti akan disetujui untuk", "idc": "Pengajuan cuti bakal di-approve untuk"},
    "The leave request will be approved.": {"id": "Pengajuan cuti akan disetujui.", "idc": "Pengajuan cuti bakal di-approve."},
    "The leave request will be rejected for": {"id": "Pengajuan cuti akan ditolak untuk", "idc": "Pengajuan cuti bakal ditolak untuk"},
    "The password reset link is valid for 60 minutes and the employee can click it to create a new password directly.": {"id": "Tautan reset password berlaku selama 60 menit dan karyawan dapat langsung mengkliknya untuk membuat password baru.", "idc": "Link reset password berlaku 60 menit dan karyawan bisa langsung klik buat bikin password baru."},
    "The request will be routed to the approver based on the company approval flow.": {"id": "Pengajuan akan diteruskan ke approver sesuai flow approval perusahaan.", "idc": "Pengajuan bakal diterusin ke approver sesuai flow approval company."},
    "The system will send an email containing a direct link (valid for 60 minutes) to the employee registered email so they can create a new password directly without OTP.": {"id": "Sistem akan mengirimkan email berisi tautan langsung (berlaku 60 menit) ke alamat email terdaftar karyawan agar mereka dapat langsung membuat kata sandi baru tanpa perlu OTP.", "idc": "Sistem bakal ngirim email link langsung (berlaku 60 menit) ke email karyawan biar bisa langsung bikin password baru tanpa perlu OTP."},
    "The total allocation cannot be lower than used and pending leave.": {"id": "Total kuota tidak boleh lebih kecil dari kuota terpakai dan pending.", "idc": "Total kuota ga boleh lebih kecil dari yang kepakai dan pending."},
    "Theme Color": {"id": "Warna Tema", "idc": "Warna Tema"},
    "This leave grant has already been processed.": {"id": "Grant cuti ini sudah diproses.", "idc": "Grant cuti ini udah diproses."},
    "This leave request has been officially approved by manager / HR.": {"id": "Pengajuan cuti ini telah sah disetujui oleh atasan / HR.", "idc": "Pengajuan cuti ini udah sah disetujui sama manager / HR."},
    "This leave type is already in use and has been archived.": {"id": "Jenis cuti sudah dipakai dan telah diarsipkan.", "idc": "Tipe cutinya udah pernah dipakai, jadi diarsipkan."},
    "This link can be opened in a new browser tab while logged in as Super Admin.": {"id": "Link ini dapat dibuka di tab browser baru selama Anda login sebagai Super Admin.", "idc": "Link ini bisa dibuka di tab baru selama kamu login sebagai Super Admin."},
    "This request has already been processed.": {"id": "Pengajuan ini sudah diproses.", "idc": "Pengajuan ini udah diproses."},
    "Timezone": {"id": "Zona Waktu", "idc": "Zona Waktu"},
    "Today": {"id": "Hari Ini", "idc": "Hari Ini"},
    "Total Duration": {"id": "Total Durasi", "idc": "Total Durasi"},
    "Total Employees": {"id": "Total Karyawan", "idc": "Total Karyawan"},
    "Total Quota": {"id": "Total Kuota", "idc": "Total Kuota"},
    "Try another year": {"id": "Coba pilih tahun lain deh", "idc": "Coba pilih tahun lain"},
    "Unlimited": {"id": "Tanpa kuota", "idc": "Tanpa kuota"},
    "Upcoming & Active Plans": {"id": "Rencana Mendatang & Aktif", "idc": "Rencana Mendatang & Aktif"},
    "Update Password": {"id": "Perbarui Password", "idc": "Update Password"},
    "Upload label, e.g. Doctor Certificate": {"id": "Label upload, mis. Surat Dokter", "idc": "Label upload, mis. Surat Dokter"},
    "Use at least 8 characters with a mix of letters and numbers to keep your workspace account secure.": {"id": "Gunakan kombinasi minimal 8 karakter dengan huruf dan angka untuk menjaga keamanan akun workspace Anda.", "idc": "Pakai minimal 8 karakter kombinasi huruf dan angka biar akun workspace kamu aman."},
    "Use the Print button above to print a physical document or save it as a PDF file.": {"id": "Gunakan tombol Cetak di atas untuk mencetak dokumen fisik atau menyimpannya sebagai file PDF.", "idc": "Pake tombol Cetak di atas buat cetak dokumen fisik atau simpen jadi file PDF."},
    "Used": {"id": "Dipakai", "idc": "Kepakai"},
    "Verify & Continue": {"id": "Verifikasi & Lanjutkan", "idc": "Verifikasi & Lanjut"},
    "Verify & Save": {"id": "Verifikasi & Simpan", "idc": "Verifikasi & Simpan"},
    "Verify OTP": {"id": "Verifikasi OTP", "idc": "Verifikasi OTP"},
    "Verify OTP & Save Password": {"id": "Verifikasi OTP & Simpan Password", "idc": "Verifikasi OTP & Simpan Password"},
    "Verify OTP Code": {"id": "Verifikasi Kode OTP", "idc": "Verifikasi Kode OTP"},
    "Verify Password Change OTP": {"id": "Verifikasi OTP Ganti Password", "idc": "Verifikasi OTP Ganti Password"},
    "Verify your identity.": {"id": "Verifikasi identitas Anda.", "idc": "Verifikasi identitas kamu."},
    "View history": {"id": "Lihat riwayat", "idc": "Liat riwayat"},
    "View on Calendar": {"id": "Lihat di Kalender", "idc": "Liat di Kalender"},
    "View team calendar": {"id": "Lihat kalender tim", "idc": "Liat kalender tim"},
    "View team leave plans to keep scheduling balanced.": {"id": "Lihat rencana leave tim agar penjadwalan tetap seimbang.", "idc": "Liat rencana cuti tim biar jadwal tetep aman."},
    "Welcome": {"id": "Selamat datang", "idc": "Halo"},
    "Who is on Leave This Week": {"id": "Siapa Cuti Minggu Ini", "idc": "Siapa Cuti Minggu Ini"},
    "will be deactivated and cannot be selected for new requests. Previous leave history remains safe.": {"id": "akan dinonaktifkan dan tidak dapat dipilih untuk pengajuan baru. Riwayat cuti sebelumnya tetap aman.", "idc": "bakal dinonaktifin dan ga bisa dipilih buat cuti baru. Riwayat cuti sebelumnya tetep aman."},
    "without annual quota": {"id": "tanpa kuota tahunan", "idc": "tanpa kuota tahunan"},
    "Work Email": {"id": "Email Kerja", "idc": "Email Kerja"},
    "Working Days": {"id": "Hari Kerja", "idc": "Hari Kerja"},
    "Year": {"id": "Tahun", "idc": "Tahun"},
    "You already have a leave request on those dates.": {"id": "Anda sudah memiliki pengajuan cuti di tanggal tersebut.", "idc": "Kamu udah punya pengajuan di tanggal itu."},
    "You are currently logged in as": {"id": "Anda sedang login sebagai", "idc": "Kamu lagi login sebagai"},
    "You are not currently in account simulation mode.": {"id": "Anda tidak sedang dalam mode simulasi akun.", "idc": "Kamu ga lagi di mode simulasi akun."},
    "You cannot request leave in the past.": {"id": "Tidak bisa mengajukan cuti di masa lalu.", "idc": "Ga bisa ajukan cuti di tanggal yang udah lewat."},
    "You do not have permission to cancel this leave request.": {"id": "Anda tidak memiliki izin untuk membatalkan pengajuan ini.", "idc": "Ga punya izin buat batalin pengajuan ini."},
    "You have signed out.": {"id": "Anda telah logout.", "idc": "Kamu udah logout."},
    "Your Calendar Feed URL": {"id": "URL Feed Kalender Anda", "idc": "Link Feed Kalender Kamu"},
    "Your request status": {"id": "Status pengajuan Anda", "idc": "Status pengajuan kamu"},
    "Your session will be closed and you will need to sign in again to access workspace.": {"id": "Session kamu akan ditutup dan kamu perlu login lagi untuk masuk workspace.", "idc": "Sesi kamu bakal ditutup dan kamu harus login lagi buat masuk workspace."},
}

# Reverse lookup map for backward compatibility with legacy Indonesian keys
_REVERSE_MAP = {}
for _en_key, _trans in TRANSLATIONS.items():
    for _lang in ('id', 'idc'):
        _val = _trans.get(_lang)
        if _val and _val not in _REVERSE_MAP:
            _REVERSE_MAP[_val] = {'en': _en_key, 'id': _trans.get('id', _val), 'idc': _trans.get('idc', _val)}

def normalize_language(language):
    return language if language in SUPPORTED_LANGUAGES else 'en'

def get_client_translations():
    client_dict = {'en': {}, 'id': {}, 'idc': {}}
    for en_key, trans in TRANSLATIONS.items():
        id_val = trans.get('id', en_key)
        idc_val = trans.get('idc', id_val)
        
        client_dict['en'][en_key] = en_key
        client_dict['id'][en_key] = id_val
        client_dict['idc'][en_key] = idc_val

        if id_val and id_val != en_key:
            client_dict['en'][id_val] = en_key
            client_dict['id'][id_val] = id_val
            client_dict['idc'][id_val] = idc_val
        if idc_val and idc_val != en_key and idc_val != id_val:
            client_dict['en'][idc_val] = en_key
            client_dict['id'][idc_val] = id_val
            client_dict['idc'][idc_val] = idc_val
    return client_dict

def translate(message, language=None):
    if not message:
        return message
    language = normalize_language(language or session.get('language', 'en'))

    # 1. Direct lookup in canonical English TRANSLATIONS
    if message in TRANSLATIONS:
        if language == 'en':
            return message
        return TRANSLATIONS[message].get(language, TRANSLATIONS[message].get('id', message))

    # 2. Reverse lookup in case an Indonesian key is provided
    if message in _REVERSE_MAP:
        if language == 'en':
            return _REVERSE_MAP[message].get('en', message)
        return _REVERSE_MAP[message].get(language, _REVERSE_MAP[message].get('id', message))

    # 3. Dynamic Regex Transformations
    if language == 'en':
        translated = message
        translated = re.sub(r'^Selamat datang, (.+)!$', r'Welcome, !', translated)
        translated = re.sub(r'^Cuti (.+) Anda tidak mencukupi\. Sisa: (\d+) hari\.$', r'Your  balance is insufficient. Remaining:  days.', translated)
        translated = re.sub(r'^Cuti (.+) disetujui', r'Leave for  approved', translated)
        translated = re.sub(r'^Cuti (.+) ditolak', r'Leave for  rejected', translated)
        translated = re.sub(r'^Level (\d+) disetujui - menunggu approval level (\d+)\.$', r'Level  approved, waiting for approval level .', translated)
        translated = re.sub(r'^Perusahaan (.+) berhasil ditambahkan!$', r'Company  added.', translated)
        translated = re.sub(r'^Perusahaan (.+) berhasil diperbarui!$', r'Company  updated.', translated)
        translated = re.sub(r'^Karyawan (.+) berhasil ditambahkan!$', r'Employee  added.', translated)
        translated = re.sub(r'^Karyawan (.+) berhasil diperbarui!$', r'Employee  updated.', translated)
        translated = re.sub(r'^Karyawan (.+) berhasil diarsipkan / dinonaktifkan\.$', r'Employee  archived / deactivated.', translated)
        translated = re.sub(r'^Karyawan (.+) berhasil dihapus permanen\.$', r'Employee  deleted permanently.', translated)
        translated = re.sub(r'^Karyawan (.+) berhasil diaktifkan kembali\.$', r'Employee  reactivated.', translated)
        translated = re.sub(r'^Karyawan (.+) berhasil dihapus\.$', r'Employee  deleted.', translated)
        translated = re.sub(r'^Jenis cuti (.+) berhasil ditambahkan!$', r'Leave type  added.', translated)
        translated = re.sub(r'^Jenis cuti (.+) berhasil diperbarui!$', r'Leave type  updated.', translated)
        translated = re.sub(r'^Jenis cuti (.+) berhasil diarsipkan\.$', r'Leave type  archived.', translated)
        translated = re.sub(r'^Jenis cuti (.+) berhasil dipulihkan dari arsip\.$', r'Leave type  restored from archive.', translated)
        translated = re.sub(r'^Departemen (.+) berhasil ditambahkan!$', r'Department  added.', translated)
        translated = re.sub(r'^Departemen (.+) berhasil diperbarui!$', r'Department  updated.', translated)
        translated = re.sub(r'^Departemen (.+) berhasil dihapus!$', r'Department  deleted.', translated)
        translated = re.sub(r'^Email uji coba berhasil dikirim ke (.+)! ✅$', r'Test email sent to ! ✅', translated)
        translated = re.sub(r'^Gagal mengirim email test: (.+)$', r'Failed to send test email: ', translated)
        return translated

    if language in ('id', 'idc'):
        translated = message
        translated = re.sub(r'^Welcome, (.+)!$', r'Selamat datang, !', translated)
        translated = re.sub(r'^Company (.+) added\.$', r'Perusahaan  berhasil ditambahkan!', translated)
        translated = re.sub(r'^Company (.+) updated\.$', r'Perusahaan  berhasil diperbarui!', translated)
        translated = re.sub(r'^Employee (.+) added\.$', r'Karyawan  berhasil ditambahkan!', translated)
        translated = re.sub(r'^Employee (.+) updated\.$', r'Karyawan  berhasil diperbarui!', translated)
        translated = re.sub(r'^Employee (.+) archived / deactivated\.$', r'Karyawan  berhasil diarsipkan / dinonaktifkan.', translated)
        translated = re.sub(r'^Employee (.+) deleted permanently\.$', r'Karyawan  berhasil dihapus permanen.', translated)
        translated = re.sub(r'^Employee (.+) reactivated\.$', r'Karyawan  berhasil diaktifkan kembali.', translated)
        translated = re.sub(r'^Leave type (.+) added\.$', r'Jenis cuti  berhasil ditambahkan!', translated)
        translated = re.sub(r'^Leave type (.+) updated\.$', r'Jenis cuti  berhasil diperbarui!', translated)
        translated = re.sub(r'^Department (.+) added\.$', r'Departemen  berhasil ditambahkan!', translated)
        translated = re.sub(r'^Department (.+) updated\.$', r'Departemen  berhasil diperbarui!', translated)
        translated = re.sub(r'^Department (.+) deleted\.$', r'Departemen  berhasil dihapus!', translated)

        if language == 'idc':
            translated = re.sub(r'^Selamat datang, (.+)!$', r'Halo, !', translated)
            translated = re.sub(r'^Cuti (.+) Anda tidak mencukupi\. Sisa: (\d+) hari\.$', r'Saldo  kamu kurang. Sisa:  hari.', translated)
            translated = re.sub(r'^Level (\d+) disetujui - menunggu approval level (\d+)\.$', r'Level  approved, nunggu approval level .', translated)
            translated = re.sub(r'^Perusahaan (.+) berhasil ditambahkan!$', r'Company  udah ditambah.', translated)
            translated = re.sub(r'^Perusahaan (.+) berhasil diperbarui!$', r'Company  udah di-update.', translated)
            translated = re.sub(r'^Karyawan (.+) berhasil ditambahkan!$', r'Orang  udah ditambah.', translated)
            translated = re.sub(r'^Karyawan (.+) berhasil diperbarui!$', r'Orang  udah di-update.', translated)
            translated = re.sub(r'^Karyawan (.+) berhasil diarsipkan / dinonaktifkan\.$', r'Orang  udah diarsip / dinonaktifkan.', translated)
            translated = re.sub(r'^Karyawan (.+) berhasil dihapus permanen\.$', r'Orang  udah dihapus permanen.', translated)
            translated = re.sub(r'^Karyawan (.+) berhasil diaktifkan kembali\.$', r'Orang  udah diaktifin lagi.', translated)
            translated = re.sub(r'^Karyawan (.+) berhasil dihapus\.$', r'Orang  udah dihapus.', translated)
            translated = re.sub(r'^Jenis cuti (.+) berhasil ditambahkan!$', r'Tipe cuti  udah ditambah.', translated)
            translated = re.sub(r'^Jenis cuti (.+) berhasil diperbarui!$', r'Tipe cuti  udah di-update.', translated)
            translated = re.sub(r'^Jenis cuti (.+) berhasil diarsipkan\.$', r'Tipe cuti  udah diarsip.', translated)
            translated = re.sub(r'^Jenis cuti (.+) berhasil dipulihkan dari arsip\.$', r'Tipe cuti  udah dibalikin dari arsip.', translated)
            translated = re.sub(r'^Departemen (.+) berhasil ditambahkan!$', r'Divisi  udah ditambah.', translated)
            translated = re.sub(r'^Departemen (.+) berhasil diperbarui!$', r'Divisi  udah di-update.', translated)
            translated = re.sub(r'^Departemen (.+) berhasil dihapus!$', r'Divisi  udah dihapus.', translated)
            translated = re.sub(r'^Email uji coba berhasil dikirim ke (.+)! ✅$', r'Email test berhasil dikirim ke ! ✅', translated)
            translated = re.sub(r'^Gagal mengirim email test: (.+)$', r'Gagal kirim email test: ', translated)
        return translated

    return message
