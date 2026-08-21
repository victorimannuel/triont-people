# Triton People — Agent & Development Guidelines

This document outlines the workspace structure, test verification, and production deployment instructions for **Triton People**.

---

## 📂 1. Workspace & Repository Structure

- **Main Repository Path**: `/home/victor/projects/triton/people/triton-people`
- **Python Virtualenv**: `/home/victor/projects/triton/people/triton-people/.venv/bin/python`
- **Archive & Backup**: `/home/victor/projects/triton/people/archive/`

---

## 🧪 2. Automated Testing Suite

Always run and verify the test suite before any deployment:

```bash
cd /home/victor/projects/triton/people/triton-people
/home/victor/projects/triton/people/triton-people/.venv/bin/python -m unittest discover -s tests -v
```

Ensure all 40 test cases pass (`OK`).

---

## 🚀 3. Production Deployment (Ansible)

Production deployment is automated using Ansible playbooks located in `imeco-infra`.

### Steps:
1. Navigate to the Ansible directory:
   ```bash
   cd /home/victor/projects/imeco/imeco-infra/ansible
   ```

2. Execute the deployment playbook:
   ```bash
   ansible-playbook playbooks/deploy-people.yml
   ```

### Deployment Configuration:
- **Playbook**: `/home/victor/projects/imeco/imeco-infra/ansible/playbooks/deploy-people.yml`
- **Source Directory**: `/home/victor/projects/triton/people/triton-people`
- **Target Host**: `imeco-prod`
- **Remote App Directory**: `/opt/imeco-infra/apps/people-by-triton`
- **Live URL**: `https://people.thehyouman.com`

---

## 🔍 4. Post-Deployment Verification

Verify the live server responds with `HTTP/1.1 200 OK`:

```bash
curl -s -I https://people.thehyouman.com/auth/login
```

---

## 📝 5. Commit Guidelines (Conventional Commits)

Always use the **Conventional Commits** format for all commits in this repository:
- `feat:` for new features (e.g. `feat(audit): add single-row filter toolbar`)
- `fix:` for bug fixes (e.g. `fix(i18n): sync translations dictionary`)
- `refactor:` for code restructuring or rebranding (e.g. `refactor(branding): update branding from Triton to Triont`)
- `perf:` for performance optimizations / database indexing (e.g. `perf(audit): add database indexes for audit logs table`)
- `ui:` / `style:` for UI/UX styling and layout adjustments
- `test:` for adding or updating unit tests
- `chore:` for configuration, build, and dependency maintenance

> **Important**: Do **NOT** use OCA Odoo commit tags (`[IMP]`, `[FIX]`, `[ADD]`, etc.) in this workspace. OCA tags are exclusively reserved for Odoo projects.

