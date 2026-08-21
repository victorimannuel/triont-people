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

- [ ] **Confirm Modal untuk Destructive Action**:
  - [ ] Tambah confirmation dialog sebelum soft delete / permanent delete / restore.
  - [ ] Modal menampilkan nama item yang akan dihapus supaya tidak accidental.
  - [ ] Reuse satu modal global (bukan per-row) dengan JS untuk inject konten dinamis.

- [ ] **Consistent Error Pages**:
  - [ ] Custom page untuk 403 (Forbidden), 404 (Not Found), dan 500 (Internal Server Error).
  - [ ] Desain sesuai branding Triont People dengan tombol "Kembali ke Dashboard".

- [ ] **Filter Persistence**:
  - [ ] Filter aktif (search, role, department, dll) tersimpan di URL query string sehingga tidak hilang saat navigate back.
  - [ ] Tombol "Reset filter" yang jelas untuk clear semua filter sekaligus.

- [ ] **Bulk Actions**:
  - [ ] Checkbox per-row dan "Select All" di list view.
  - [ ] Action bar muncul di atas tabel ketika ada item dipilih: Archive, Delete, Restore.
  - [ ] Cover semua list: Employees, Leave Types, Departments.
