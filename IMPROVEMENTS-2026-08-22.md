# Improvements — 2026-08-22

## Roadmap

- [ ] **Toast Popup Notifikasi untuk Semua Action**:
  - [ ] Pastikan setiap CRUD (tambah, edit, hapus, restore) menampilkan toast notifikasi yang konsisten.
  - [ ] Cover semua entitas: Employees, Leave Types, Departments, Companies, Approval History.
  - [ ] Cover action khusus: grant leave, archive/unarchive, soft delete, restore, import data.
  - [ ] Toast kategori: `success` (hijau), `danger` (merah), `info` (kuning) — auto-dismiss 5 detik, bisa tutup manual.

- [ ] **Walkthrough & Cleanup Codebase**:
  - [ ] Audit seluruh route di `routes/admin.py`, `routes/approvals.py`, `routes/leaves.py`, dan `routes/auth.py` untuk boilerplate yang berulang.
  - [ ] Refactor query pattern yang duplikat (misal: filter `company_id + is_deleted + is_active` yang berulang di banyak tempat).
  - [ ] Cek dan pastikan semua `flash()` message sudah terjemahkan lewat `translate()`.
  - [ ] Validasi konsistensi naming convention (variable, function, route) antar modul.
  - [ ] Hapus kode mati (dead code), komentar tidak relevan, atau import yang tidak dipakai.

- [ ] **Optimasi**:
  - [ ] Audit query N+1 pada halaman list (employees, leave types, approval history).
  - [ ] Tambah database index yang belum ada untuk kolom yang sering di-filter (`is_deleted`, `is_active`, `company_id`, `status`).
  - [ ] Evaluasi lazy loading vs eager loading pada relasi yang sering diakses.
  - [ ] Cek penggunaan `paginate()` vs `.all()` — pastikan tidak ada query tanpa limit di halaman yang bisa banyak data.

- [x] **Confirm Modal untuk Destructive Action**:
  - [x] Tambah confirmation dialog sebelum soft delete / permanent delete / restore.
  - [x] Modal menampilkan nama item yang akan dihapus supaya tidak accidental.
  - [x] Reuse satu modal global (bukan per-row) dengan JS untuk inject konten dinamis.

- [x] **Consistent Error Pages**:
  - [x] Custom page untuk 403 (Forbidden), 404 (Not Found), dan 500 (Internal Server Error).
  - [x] Desain sesuai branding Triont People dengan tombol "Kembali ke Dashboard".

- [x] **Filter Persistence**:
  - [x] Filter aktif (search, role, department, dll) tersimpan di URL query string sehingga tidak hilang saat navigate back.
  - [x] Tombol "Reset filter" yang jelas untuk clear semua filter sekaligus.

- [x] **Bulk Actions**:
  - [x] Checkbox per-row dan "Select All" di list view.
  - [x] Action bar muncul di atas tabel ketika ada item dipilih: Archive, Delete, Restore.
  - [x] Cover semua list: Employees, Leave Types, Departments.

- [ ] **Konfigurasi & Manajemen Hari Libur Nasional**:
  - [ ] UI Config / Pengaturan Hari Libur Nasional & Cuti Bersama yang komprehensif per perusahaan.
  - [ ] Fleksibilitas konfigurasi cuti bersama (opsi apakah cuti bersama otomatis memotong saldo cuti tahunan atau menjadi hari libur perusahaan).
  - [x] Auto-sync kalender libur SKB 3 Menteri / integrasi dataset/API hari libur nasional Indonesia (Live API Nager.Date ID + Fixed statutory generator + multi-year fallback).
  - [ ] Dukungan import/export daftar hari libur per tahun (CSV/Excel).

- [x] **Navigasi Multi-Tahun di Menu Holidays (Tahun Sebelum & Sesudah)**:
  - [x] Navigasi tahun dinamis dengan tombol *Previous Year* (`<`) dan *Next Year* (`>`) di menu Holidays (`/long-weekend`).
  - [x] Dropdown pemilihan tahun yang fleksibel (rentang tahun otomatis & dinamis) untuk melihat arsip libur tahun lalu dan proyeksi libur tahun mendatang.
  - [x] Kalkulasi rekomendasi Long Weekend dan Harpitnas secara akurat untuk tahun berapapun yang dipilih.

