# Panduan & Langkah Deployment Produksi - Triton People

Dokumen ini berisi panduan teknis dan langkah-langkah standar untuk menjalankan pengujian dan mendeploy aplikasi **Triton People** ke server produksi.

---

## 📋 1. Struktur Lingkungan Kerja

| Komponen | Lokasi / Nilai |
| :--- | :--- |
| **Workspace Repo** | `/home/victor/projects/triont/people/triont-people` |
| **Virtual Environment** | `/home/victor/projects/triont/people/triont-people/.venv` |
| **Ansible Infra Repo** | `/home/victor/projects/triont/triont-infra/ansible` |
| **Ansible Playbook** | `playbooks/deploy-people.yml` |
| **Server Target** | `imeco-prod` |
| **Server Path** | `/opt/imeco-infra/apps/people-by-triton` |
| **URL Produksi** | `https://people.thehyouman.com` |

---

## 🧪 2. Langkah Pengujian (Pre-Deploy Test)

Sebelum melakukan deployment, selalu jalankan test suite otomatis untuk memastikan tidak ada regresi fitur atau error skema database:

```bash
cd /home/victor/projects/triont/people/triont-people
/home/victor/projects/triont/people/triont-people/.venv/bin/python -m unittest discover -s tests -v
```

*Pastikan seluruh test berstatus **OK** (9/9 passed).*

---

## 🚀 3. Langkah Deployment ke Produksi

Deployment menggunakan otomasi Ansible yang menyinkronkan kode dan merestart container Docker di server produksi:

```bash
# 1. Pindah ke direktori ansible imeco-infra
cd /home/victor/projects/triont/triont-infra/ansible

# 2. Jalankan playbook deploy
ansible-playbook playbooks/deploy-people.yml
```

### Apa yang Dilakukan Playbook Ini?
1. Mengumpulkan fakta server `imeco-prod`.
2. Menyinkronkan file aplikasi dari `/home/victor/projects/triont/people/triont-people/` ke remote server.
3. Me-render konfigurasi Docker Compose dan Environment.
4. Membangun (*build*) image web dan merestart service Docker via Docker Compose (`community.docker.docker_compose_v2`).
5. Memastikan status container `healthy` & `running`.

---

## 🔍 4. Verifikasi Pasca-Deployment (Post-Deploy Check)

Periksa endpoint login produksi untuk memastikan server merespons dengan status `200 OK`:

```bash
curl -s -I https://people.thehyouman.com/auth/login
```

Atau buka langsung di browser:
👉 **[https://people.thehyouman.com](https://people.thehyouman.com)**
