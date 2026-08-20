from extensions import db
from models.company import Company
from models.user import Department, User
from models.leave import LeaveType

def seed_initial_data():
    if Company.query.first():
        return

    # Create admin company
    admin_company = Company(name='Admin', primary_color='#0d9488', is_active=True,
                            notifications_enabled=True, smtp_host='smtp.gmail.com',
                            smtp_port=587, smtp_user='admin@example.com',
                            smtp_password='password', notify_on_approve=True,
                            notify_on_reject=True, notify_on_submit=True)
    db.session.add(admin_company)
    db.session.flush()

    # Create default employee company
    emp_company = Company(name='Employee', primary_color='#0d9488', is_active=True,
                          notifications_enabled=False)
    db.session.add(emp_company)
    db.session.flush()

    # Create leave types per company
    leave_types = [
        LeaveType(name='Cuti Tahunan', description='Cuti tahunan reguler', days_per_year=12, color='#0d9488', is_active=True),
        LeaveType(name='Cuti Sakit', description='Cuti karena sakit', days_per_year=0, color='#ef4444', is_active=True),
        LeaveType(name='Cuti Melahirkan', description='Cuti melahirkan', days_per_year=90, color='#ec4899', is_active=True),
    ]
    for company in [admin_company, emp_company]:
        for lt in leave_types:
            leave_type = LeaveType(name=lt.name, description=lt.description, days_per_year=lt.days_per_year,
                                   color=lt.color, is_active=True, company_id=company.id)
            db.session.add(leave_type)
    db.session.flush()

    # Create users
    users_data = [
        {'name': 'Admin User', 'email': 'admin@gwcuti.app', 'role': 'admin', 'company_id': admin_company.id},
        {'name': 'Manager User', 'email': 'manager@gwcuti.app', 'role': 'manager', 'company_id': admin_company.id},
        {'name': 'HR User', 'email': 'hr@gwcuti.app', 'role': 'hr', 'company_id': admin_company.id},
        {'name': 'Employee User', 'email': 'employee@gwcuti.app', 'role': 'employee', 'company_id': emp_company.id},
        {'name': 'Bob Sunshine', 'email': 'bob@gwcuti.app', 'role': 'manager', 'company_id': emp_company.id},
    ]
    for user_data in users_data:
        user = User(name=user_data['name'], email=user_data['email'], role=user_data['role'],
                     company_id=user_data['company_id'], department_id=None)
        user.set_password(user_data['email'].split('@')[1] + '123')
        db.session.add(user)
    db.session.flush()

    # Create manager/subordinate relation
    employee_user = User.query.filter_by(email='employee@gwcuti.app').first()
    bob_user = User.query.filter_by(email='bob@gwcuti.app').first()
    if employee_user and bob_user:
        employee_user.manager_id = bob_user.id

    # Create departments
    admin_dept = Department(name='IT', company_id=admin_company.id)
    db.session.add(admin_dept)
    dept = Department(name='Sales', company_id=emp_company.id)
    db.session.add(dept)

    db.session.commit()
