# People by Triton (Clean & Modular Architecture)

Clean, modular, and maintainable Flask-based Human Resource & Leave Management System.

---

## 🏗️ Architecture & Directory Structure

```text
people-clean/
├── app.py                      # Application factory (create_app) & runtime entry point
├── wsgi.py                     # Production WSGI entry point (for Gunicorn/uWSGI)
├── config.py                   # Environment configuration class
├── extensions.py               # Flask extension instances (SQLAlchemy, LoginManager, Migrate)
├── requirements.txt            # Python dependencies
├── core/                       # Core cross-cutting concerns
│   ├── auth.py                 # User loader, role_required decorator, password validation
│   ├── csrf.py                 # CSRF token generation & validation middleware
│   └── i18n.py                 # Multi-language translation engine (en, id, idc)
├── models/                     # Domain data models (SQLAlchemy ORM)
│   ├── __init__.py             # Model exports registry
│   ├── company.py              # Company & SMTP configuration model
│   ├── user.py                 # User & Department models
│   ├── leave.py                # LeaveType, LeaveRequest, LeaveBalance, LeaveGrant models
│   ├── approval.py             # Multi-level ApprovalConfig model
│   ├── holiday.py              # PublicHoliday model
│   └── audit.py                # AuditLog model
├── services/                   # Business logic layer
│   ├── __init__.py
│   ├── leave_service.py        # Balance provisioning & duration calculation
│   ├── holiday_service.py      # Indonesian national holiday dataset & smart long-weekend engine
│   ├── notification_service.py # Multi-tenant SMTP email dispatcher
│   ├── audit_service.py        # Structured audit logger
│   └── seed_service.py         # Database initialization & default seeding
├── routes/                     # HTTP route controllers / Flask Blueprints
│   ├── __init__.py             # Blueprint aggregator & registration
│   ├── common.py               # Main blueprint instance
│   ├── auth.py                 # Authentication routes (/auth/login, /auth/logout)
│   ├── dashboard.py            # Dashboard, workspace settings, excel export
│   ├── leaves.py               # Leave application, my history, long weekend planner
│   ├── calendar.py             # Team calendar view & holiday badges
│   ├── approvals.py            # Approval inbox, decision actions, and history
│   └── admin.py                # Admin management (Employees, Leave Types, Divisi, Companies, SMTP)
├── tests/                      # Automated test suite
│   ├── __init__.py
│   └── test_app.py             # End-to-end integration & unit test suite
├── templates/                  # Jinja2 HTML templates
└── static/                     # Static assets (CSS, JS, Fonts)
```

---

## 🧪 Running Automated Tests

To run the full test suite:

```bash
python -m unittest discover -s tests -v
```

---

## 🚀 Running the Application

### Development Mode:
```bash
python app.py
```

### Production Mode (Gunicorn):
```bash
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```
