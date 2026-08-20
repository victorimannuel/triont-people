# Triton People — Next Improvements & Backlog (2026-08-20)

Dokumen ini mencatat daftar rencana perbaikan, modernisasi, dan peningkatan fitur untuk pengembangan iterasi berikutnya pada **People by Triton** per tanggal **20 Agustus 2026**.

---

## 🚀 1. UI & Translasi (Frontend)
- [x] **Standarisasi `{{ t(...) }}` pada Seluruh Template Dashboard** (`templates/dashboard.html`):
  - [x] Membungkus seluruh label statis (*"Workspace pribadi"*, *"Selamat datang"*, *"Komposisi leave"*, *"Detail saldo"*, *"Pengajuan terkini"*, *"Butuh persetujuan"*, *"Belum ada pengajuan cuti"*, dll.) dengan helper `{{ t(...) }}`.
  - [x] Memastikan server-side rendering langsung menghasilkan bahasa Inggris saat user memilih bahasa `EN`.
- [x] **Audit String Template Admin & Modals**:
  - [x] Melakukan cross-check menyeluruh pada modal konfirmasi, tooltip, dan pesan error form agar 100% terdaftar di kamus bahasa (`core/i18n.py` dan `templates/base.html`).

---

## 📊 2. Fitur UX & Kolaborasi Tim
- [x] **Widget "Siapa Cuti Minggu Ini" di Dashboard**:
  - [x] Menampilkan daftar ringkas rekan tim yang sedang atau akan cuti dalam 7 hari ke depan pada dashboard utama.
  - [x] Mempermudah koordinasi tugas dan delegasi backup tanpa harus membuka halaman kalender tim penuh.
- [x] **Slip Bukti Pengajuan Cuti Siap Cetak (Print View / PDF)**:
  - [x] Tombol *"Cetak Bukti Cuti"* pada detail pengajuan yang telah berstatus disetujui (`approved`).
  - [x] Menghasilkan layout print formal yang menyertakan informasi pemohon, tanggal cuti, alasan, nama & timestamp approval dari atasan/HR.

---

## ⚙️ 3. Operasional HR & Batch Tools
- [ ] **Annual Balance Rollover / Reset (Tutup Buku Saldo Tahunan)**:
  - Fitur batch di menu [Admin Saldo Cuti](file:///home/victor/projects/triton/people/triton-people/templates/admin/leave_balances.html) untuk mereset kuota cuti tahunan atau mentransfer sisa cuti (*carry-forward*) ke tahun berikutnya secara otomatis bagi seluruh karyawan aktif.

---

## 🛠️ 4. Code Quality & Modernisasi (Backend)
- [ ] **Migrasi `datetime.utcnow()` ke `datetime.now(timezone.utc)`**:
  - Mengganti seluruh penggunaan `datetime.utcnow()` yang berstatus *deprecated* di Python 3.12/3.13 pada:
    - `models/base.py`
    - `routes/admin.py`
    - `routes/approvals.py`
    - `services/`
  - Menghilangkan warning `DeprecationWarning` dari log test runner dan production output.
- [ ] **Penanganan SQLite / SQLAlchemy Foreign Key Warnings**:
  - Menyesuaikan definisi `ForeignKeyConstraint` dengan parameter `use_alter=True` untuk relasi siklik antara tabel `companies`, `departments`, dan `users` saat eksekusi test drop/create table.

---

## 🔐 5. Auth & Keamanan (Reset Password via OTP Email)
- [x] **Fitur Lupa Password & Verifikasi OTP ke Email**:
  - [x] **Halaman Permintaan OTP** (`/auth/forgot-password`): Karyawan memasukkan email akun yang terdaftar.
  - [x] **Pengiriman Kode OTP**: Sistem menghasilkan 6-digit OTP acak (masa berlaku 15 menit) dan mengirimkannya melalui server SMTP perusahaan.
  - [x] **Verifikasi & Form Reset Password** (`/auth/verify-otp` & `/auth/reset-password`): Input 6-digit OTP dan input password baru yang tervalidasi.
  - [x] **Keamanan & Rate Limiting**: Proteksi percobaan salah berulang (max 5x attempt lock) dan cooldown pengiriman ulang OTP (resend cooldown 60 detik).
  - [x] **Audit Trail**: Mencatat seluruh aktivitas request OTP, verifikasi, dan reset password ke Audit Log.


