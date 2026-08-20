# Triton People — Improvements & Backlog (2026-08-21)

Dokumen ini mencatat daftar rencana perbaikan, optimasi performa, dan peningkatan fitur untuk pengembangan **People by Triton** per tanggal **21 Agustus 2026**.

---

## ⚡ 1. Kecepatan & Asset Frontend (Selesai)
- [x] **Pre-compiled Tailwind CSS & Self-Hosted Assets**:
  - [x] Mengganti runtime Play CDN compiler (`cdn.tailwindcss.com` ~3MB) dengan pre-compiled static CSS ([`static/css/tailwind.min.css`](file:///home/victor/projects/triton/people/triton-people/static/css/tailwind.min.css) 49KB).
  - [x] Menyimpan aset FontAwesome 6.5.1, Chart.js, dan TomSelect di folder lokal `static/vendor/` untuk menghilangkan render-blocking dari CDN eksternal.
  - [x] Halaman kini loading instan tanpa jeda kompilasi browser (hemat bandwidth ~98.4%).
  - [x] Build script `npm run build:css` ditambahkan di `package.json`.

---

## 🐛 2. Bug Fixes & Stabilitas Sistem (Selesai)
- [x] **Fix Cuti Lintas Bulan di Kalender Tim** (`routes/calendar.py`):
  - [x] Perbaiki kalkulasi rentang hari cuti yang melintasi pergantian bulan (misal 28 Agustus – 4 September) agar tetap muncul dengan benar di bulan berikutnya (capping `start_d` dan `end_d` ke rentang hari aktif bulan bersangkutan).
- [x] **Notifikasi Email Pengajuan Cuti ke Manager / Atasan** (`services/notification_service.py`):
  - [x] Saat karyawan mengajukan cuti (`event == 'submit'`), sistem kini mengirimkan konfirmasi ke pemohon (`emp.email`) dan notifikasi aksi ke **Atasan Langsung** (`emp.manager.email`) agar dapat segera ditinjau di inbox approval.

---

## 💼 3. Peningkatan Operasional & Fitur Karyawan (Self-Service)
- [ ] **Fitur "Batalkan Pengajuan" Mandiri untuk Karyawan** (`/history`):
  - [ ] Tombol pembatalan untuk pengajuan yang masih berstatus `pending` di halaman Riwayat Cuti karyawan.
  - [ ] Mengembalikan kuota hari yang terkunci di `pending_days` secara otomatis dan mencatat audit log `leave.request_cancel`.
- [ ] **Kalkulasi Hari Kerja Cuti (Exclude Weekend & Hari Libur Nasional)**:
  - [ ] Opsi perhitungan durasi cuti hanya pada hari kerja aktif (Senin–Jumat) dan otomatis mengecualikan tanggal yang tercatat di daftar Hari Libur Nasional (`public_holidays`), sehingga cuti Jumat–Senin tidak memotong kuota Sabtu & Minggu.
- [ ] **Sinkronisasi Kalender Tim (.ics / WebCal Subscription Feed)**:
  - [ ] Endpoint feed `.ics` (`/calendar/feed.ics?token=...`) agar karyawan dapat berlangganan jadwal cuti tim langsung ke Google Calendar, Apple Calendar, atau Outlook di HP/laptop secara realtime.
