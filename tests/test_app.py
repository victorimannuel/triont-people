import io
import json
import re
import unittest
from unittest.mock import patch
from datetime import date, datetime, timedelta
from config import Config
from extensions import db
from app import create_app
from core.time_util import utcnow
from models import AuditLog, User, Company, Department, LeaveType, LeaveRequest, LeaveBalance, LeaveGrant, PublicHoliday, ApprovalConfig, PasswordReset, NotificationOutbox
from services.holiday_service import calculate_long_weekends, ensure_company_holidays

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    AUTO_CREATE_DB = False

class PeopleAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()
        self._seed_test_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _seed_test_data(self):
        self.company_a = Company(name='Company A', primary_color='#0d9488', is_active=True)
        self.company_b = Company(name='Company B', primary_color='#1e40af', is_active=True)
        db.session.add_all([self.company_a, self.company_b])
        db.session.flush()

        self.lt_annual_a = LeaveType(company_id=self.company_a.id, name='Cuti Tahunan', days_per_year=12, is_active=True)
        self.lt_annual_b = LeaveType(company_id=self.company_b.id, name='Cuti Tahunan', days_per_year=12, is_active=True)
        db.session.add_all([self.lt_annual_a, self.lt_annual_b])
        db.session.flush()

        self.superadmin_user = User(name='Super Admin', email='superadmin@test.com', role='superadmin', company_id=self.company_a.id)
        self.superadmin_user.set_password('SuperAdminPass123')

        self.admin_user = User(name='Company Admin', email='admin@test.com', role='admin', company_id=self.company_a.id)
        self.admin_user.set_password('AdminPass123')

        self.manager_user = User(name='Manager Bob', email='manager@test.com', role='manager', company_id=self.company_a.id)
        self.manager_user.set_password('ManagerPass123')

        self.employee_user = User(name='Alice Employee', email='alice@test.com', role='employee', company_id=self.company_a.id)
        self.employee_user.set_password('AlicePass123')

        self.emp_b = User(name='Charlie B', email='charlie@test.com', role='employee', company_id=self.company_b.id)
        self.emp_b.set_password('CharliePass123')

        db.session.add_all([self.superadmin_user, self.admin_user, self.manager_user, self.employee_user, self.emp_b])
        db.session.flush()

        self.employee_user.manager_id = self.manager_user.id
        this_year = date.today().year

        self.bal_alice = LeaveBalance(company_id=self.company_a.id, employee_id=self.employee_user.id, leave_type_id=self.lt_annual_a.id, year=this_year, total_days=12, used_days=0, pending_days=0)
        self.bal_charlie = LeaveBalance(company_id=self.company_b.id, employee_id=self.emp_b.id, leave_type_id=self.lt_annual_b.id, year=this_year, total_days=12, used_days=0, pending_days=0)
        self.apprv_cfg = ApprovalConfig(company_id=self.company_a.id, leave_type_id=self.lt_annual_a.id, level=1, approver_role='manager')
        db.session.add_all([self.bal_alice, self.bal_charlie, self.apprv_cfg])

        db.session.commit()

    def _login(self, user, password=None):
        self.client.get('/auth/logout')
        passwords = {
            'superadmin@test.com': 'SuperAdminPass123',
            'admin@test.com': 'AdminPass123',
            'manager@test.com': 'ManagerPass123',
            'alice@test.com': 'AlicePass123',
            'charlie@test.com': 'CharliePass123',
        }
        pwd = password or passwords.get(user.email, 'AdminPass123')
        self.client.post('/auth/login', data={'email': user.email, 'password': pwd, '_csrf_token': 'test-token'})

    def test_login_flow(self):
        from datetime import timedelta
        self.assertEqual(self.app.config['PERMANENT_SESSION_LIFETIME'], timedelta(days=7))
        res = self.client.post('/auth/login', data={'email': 'alice@test.com', 'password': 'AlicePass123', '_csrf_token': 'test-token'})
        self.assertEqual(res.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.permanent)

    def test_csrf_audit_log_records_blocked_result(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        res = self.client.post("/api/graphql", json={"query": "{ __typename }"})
        self.assertEqual(res.status_code, 400)
        log = AuditLog.query.filter_by(action="security.csrf_failed").first()
        self.assertIsNotNone(log)
        details = log.details_dict
        self.assertEqual(details["method"], "POST")
        self.assertEqual(details["path"], "/api/graphql")
        self.assertEqual(details["result"], "blocked")
        self.assertEqual(details["result_status"], 400)

    def test_custom_domain_guide_has_test_form(self):
        self._login(self.admin_user)
        res = self.client.get('/admin/custom-domain-guide')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Test domain', res.data)
        self.assertIn(b'people-triton.imannuelvictor.com', res.data)

    def test_custom_domain_test_reports_ready(self):
        self._login(self.admin_user)
        with patch('routes.admin.resolve_domain_ips', side_effect=[['104.21.1.1'], ['104.21.1.1']]), \
             patch('routes.admin.check_https_domain', return_value={'ok': True, 'status_code': 200, 'reason': 'OK'}):
            res = self.client.post('/admin/custom-domain-guide/test', data={'domain': 'https://people.client.com/login'})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'people.client.com', res.data)
        self.assertIn(b'Domain looks ready.', res.data)
        log = AuditLog.query.filter_by(action='admin.custom_domain_tested').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details_dict['result'], 'ready')

    def test_custom_domain_test_blocks_unsafe_hosts(self):
        self._login(self.admin_user)
        res = self.client.post('/admin/custom-domain-guide/test', data={'domain': 'http://localhost/admin'})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Domain is invalid.', res.data)

    def test_apply_leave_and_balance_deduction(self):
        self._login(self.employee_user)
        # Apply leave for tomorrow + 1 day
        start_d = date(date.today().year, 10, 5)
        end_d = date(date.today().year, 10, 6)
        res = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'start_date': start_d.isoformat(),
            'end_date': end_d.isoformat(),
            'reason': 'Family gathering',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)
        req = LeaveRequest.query.filter_by(employee_id=self.employee_user.id).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.duration_days, 2.0)
        self.assertEqual(req.status, 'pending')

        # Verify pending days increased
        bal = LeaveBalance.query.filter_by(employee_id=self.employee_user.id, leave_type_id=self.lt_annual_a.id).first()
        self.assertEqual(bal.pending_days, 2.0)

    def test_successful_leave_request_shows_result_popup(self):
        self._login(self.employee_user)
        res = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'start_date': date(date.today().year, 10, 5).isoformat(),
            'end_date': date(date.today().year, 10, 6).isoformat(),
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'id="leave-result-dialog"', res.data)
        self.assertIn(b'Leave request submitted', res.data)
        self.assertNotIn(b'Leave request submitted. Waiting for approval.</span>', res.data)

    def test_leave_request_without_allocated_balance_shows_result_popup(self):
        db.session.delete(self.bal_alice)
        db.session.commit()
        self._login(self.employee_user)
        res = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'start_date': date(date.today().year, 10, 5).isoformat(),
            'end_date': date(date.today().year, 10, 5).isoformat(),
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'id="leave-result-dialog"', res.data)
        self.assertIn(b'No leave balance has been allocated.', res.data)
        self.assertIsNone(LeaveRequest.query.filter_by(employee_id=self.employee_user.id).first())

    def test_exhausted_leave_balance_shows_result_popup(self):
        self.bal_alice.used_days = self.bal_alice.total_days
        db.session.commit()
        self._login(self.employee_user)
        res = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'start_date': date(date.today().year, 10, 5).isoformat(),
            'end_date': date(date.today().year, 10, 5).isoformat(),
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Your leave balance is exhausted.', res.data)
        self.assertIsNone(LeaveRequest.query.filter_by(employee_id=self.employee_user.id).first())

    def test_insufficient_leave_balance_shows_result_popup(self):
        self.bal_alice.total_days = 1
        db.session.commit()
        self._login(self.employee_user)
        res = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'start_date': date(date.today().year, 10, 5).isoformat(),
            'end_date': date(date.today().year, 10, 6).isoformat(),
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Insufficient leave balance. Available: 1 days. Requested: 2 days.', res.data)
        self.assertIsNone(LeaveRequest.query.filter_by(employee_id=self.employee_user.id).first())

    def test_approval_workflow(self):
        # Create pending request
        start_d = date(date.today().year, 11, 1)
        end_d = date(date.today().year, 11, 2)
        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=start_d,
            end_date=end_d,
            duration_days=2.0,
            status='pending',
            current_approval_level=1,
            max_approval_level=1
        )
        db.session.add(req)
        self.bal_alice.pending_days = 2.0
        db.session.commit()

        # Manager approves
        self._login(self.manager_user)
        res = self.client.post(f'/approve/{req.id}', data={
            'action': 'approve',
            'expected_level': '1',
            'notes': 'Approved by manager',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)
        db.session.refresh(req)
        db.session.refresh(self.bal_alice)
        self.assertEqual(req.status, 'approved')
        self.assertEqual(self.bal_alice.used_days, 2.0)
        self.assertEqual(self.bal_alice.pending_days, 0.0)

    def test_inbox_pending_approvals_view(self):
        # Create pending request for Alice
        start_d = date(date.today().year, 11, 10)
        end_d = date(date.today().year, 11, 11)
        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=start_d,
            end_date=end_d,
            duration_days=2.0,
            status='pending',
            current_approval_level=1,
            max_approval_level=1,
            reason='Family event vacation'
        )
        db.session.add(req)
        db.session.commit()

        # 1. Manager logs in and views /approvals
        self._login(self.manager_user)
        res_mgr = self.client.get('/approvals')
        self.assertEqual(res_mgr.status_code, 200)
        self.assertIn(b'Alice Employee', res_mgr.data)
        self.assertIn(b'Cuti Tahunan', res_mgr.data)
        self.assertIn(b'Family event vacation', res_mgr.data)
        self.assertIn(f'action="/approve/{req.id}"'.encode('utf-8'), res_mgr.data)
        self.assertIn(b'<span class="approval-inbox-badge', res_mgr.data)
        self.assertIn(b'aria-label="1 pending approval requests"', res_mgr.data)

        # 2. Admin logs in and views /approvals
        self._login(self.admin_user)
        res_adm = self.client.get('/approvals')
        self.assertEqual(res_adm.status_code, 200)
        self.assertIn(b'Alice Employee', res_adm.data)
        self.assertIn(b'<span class="approval-inbox-badge', res_adm.data)
        self.assertIn(b'aria-label="1 pending approval requests"', res_adm.data)

        # 3. Regular employee is restricted from /approvals and does not see the approval badge
        self._login(self.employee_user)
        res_dash = self.client.get('/')
        self.assertEqual(res_dash.status_code, 200)
        self.assertNotIn(b'<span class="approval-inbox-badge', res_dash.data)
        res_emp = self.client.get('/approvals')
        self.assertEqual(res_emp.status_code, 302)

    def test_long_weekend_planner(self):
        ensure_company_holidays(self.company_a.id)
        suggestions, holidays = calculate_long_weekends(self.company_a.id, 2025)
        self.assertGreater(len(holidays), 10)
        self.assertGreater(len(suggestions), 0)

    def test_long_weekend_year_navigation(self):
        self._login(self.admin_user)
        # Test default year
        res_default = self.client.get('/long-weekend')
        self.assertEqual(res_default.status_code, 200)

        # Test specific years (previous and next)
        res_prev = self.client.get('/long-weekend?year=2025')
        self.assertEqual(res_prev.status_code, 200)
        self.assertIn(b'2025', res_prev.data)

        res_next = self.client.get('/long-weekend?year=2027')
        self.assertEqual(res_next.status_code, 200)
        self.assertIn(b'2027', res_next.data)

    def test_holiday_auto_sync_api_and_dynamic_year(self):
        self._login(self.admin_user)
        # Test syncing holidays for year 2028 via endpoint
        res_sync = self.client.post('/admin/holidays/sync', data={
            'year': '2028',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res_sync.status_code, 200)

        # Verify that 2028 holidays exist for company A
        h2028 = PublicHoliday.query.filter(
            PublicHoliday.company_id == self.company_a.id,
            PublicHoliday.holiday_date >= date(2028, 1, 1),
            PublicHoliday.holiday_date <= date(2028, 12, 31)
        ).all()
        self.assertGreater(len(h2028), 0)

        # Verify page renders 2028 with auto-synced data
        res_2028 = self.client.get('/long-weekend?year=2028')
        self.assertEqual(res_2028.status_code, 200)
        self.assertIn(b'2028', res_2028.data)

    def test_custom_holiday_crud(self):
        self._login(self.admin_user)
        res = self.client.post('/admin/holidays/add', data={
            'holiday_date': '2025-11-20',
            'name': 'HUT Perusahaan Test',
            'kind': 'company',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)
        h = PublicHoliday.query.filter_by(company_id=self.company_a.id, name='HUT Perusahaan Test').first()
        self.assertIsNotNone(h)
        self.assertEqual(h.kind, 'company')

        # Delete holiday
        res_del = self.client.post(f'/admin/holidays/{h.id}/delete', data={'_csrf_token': 'test-token'})
        self.assertEqual(res_del.status_code, 302)
        h_after = PublicHoliday.query.filter_by(id=h.id).first()
        self.assertIsNone(h_after)

    def test_multi_tenant_isolation(self):
        # 1. User in company A cannot see company B employees
        self._login(self.admin_user)
        res = self.client.get('/admin/employees')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Alice Employee', res.data)
        self.assertNotIn(b'Charlie B', res.data)

        # 2. Holiday added in Company A does not appear in Company B
        res_add = self.client.post('/admin/holidays/add', data={
            'holiday_date': '2026-11-25',
            'name': 'HUT Khusus Triont Company A',
            'kind': 'company',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res_add.status_code, 302)

        # Company A sees the custom holiday
        res_a_holidays = self.client.get('/long-weekend?year=2026')
        self.assertIn(b'HUT Khusus Triont Company A', res_a_holidays.data)

        # Company B does NOT see Company A's custom holiday
        self._login(self.emp_b)
        res_b_holidays = self.client.get('/long-weekend?year=2026')
        self.assertNotIn(b'HUT Khusus Triont Company A', res_b_holidays.data)

    def test_half_day_leave_workflow_and_overlap_validation(self):
        self._login(self.employee_user)
        test_date = date(date.today().year, 12, 10)

        # 1. Apply Morning Half-Day
        res_m = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'day_part': 'morning',
            'start_date': test_date.isoformat(),
            'end_date': test_date.isoformat(),
            'reason': 'Morning medical appointment',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res_m.status_code, 200)

        req_m = LeaveRequest.query.filter_by(employee_id=self.employee_user.id, start_date=test_date, day_part='morning').first()
        self.assertIsNotNone(req_m)
        self.assertEqual(req_m.duration_days, 0.5)
        self.assertEqual(req_m.day_part, 'morning')

        bal = LeaveBalance.query.filter_by(employee_id=self.employee_user.id, leave_type_id=self.lt_annual_a.id).first()
        self.assertEqual(bal.pending_days, 0.5)

        # 2. Apply Afternoon Half-Day on the same date (should succeed)
        res_a = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'day_part': 'afternoon',
            'start_date': test_date.isoformat(),
            'end_date': test_date.isoformat(),
            'reason': 'Afternoon personal matter',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res_a.status_code, 200)

        req_a = LeaveRequest.query.filter_by(employee_id=self.employee_user.id, start_date=test_date, day_part='afternoon').first()
        self.assertIsNotNone(req_a)
        self.assertEqual(req_a.duration_days, 0.5)

        db.session.refresh(bal)
        self.assertEqual(bal.pending_days, 1.0)

        # 3. Attempt duplicate Morning Half-Day on same date (should fail validation)
        res_dup = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'day_part': 'morning',
            'start_date': test_date.isoformat(),
            'end_date': test_date.isoformat(),
            'reason': 'Duplicate morning request',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res_dup.status_code, 200)
        # Should not create a 3rd request
        all_reqs = LeaveRequest.query.filter_by(employee_id=self.employee_user.id, start_date=test_date).all()
        self.assertEqual(len(all_reqs), 2)

        # 4. Attempt Full Day request overlapping with existing half-day (should fail validation)
        res_full = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'day_part': 'full',
            'start_date': test_date.isoformat(),
            'end_date': test_date.isoformat(),
            'reason': 'Conflicting full day',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res_full.status_code, 200)
        all_reqs = LeaveRequest.query.filter_by(employee_id=self.employee_user.id, start_date=test_date).all()
        self.assertEqual(len(all_reqs), 2)

        # 5. Manager approves both half-day requests
        self._login(self.manager_user)
        for req in (req_m, req_a):
            res_app = self.client.post(f'/approve/{req.id}', data={
                'action': 'approve',
                'expected_level': '1',
                '_csrf_token': 'test-token'
            })
            self.assertEqual(res_app.status_code, 302)

        db.session.refresh(req_m)
        db.session.refresh(req_a)
        db.session.refresh(bal)
        self.assertEqual(req_m.status, 'approved')
        self.assertEqual(req_a.status, 'approved')
        self.assertEqual(bal.used_days, 1.0)
        self.assertEqual(bal.pending_days, 0.0)

    def test_admin_delete_employee_with_fk_constraints(self):
        # Create a test employee who is a department head and has grants/audit logs
        dept = Department(name='Engineering', company_id=self.company_a.id)
        db.session.add(dept)
        db.session.flush()

        emp_to_delete = User(name='Delete Me', email='delete_me@test.com', role='employee', company_id=self.company_a.id, department_id=dept.id)
        emp_to_delete.set_password('Pass12345')
        db.session.add(emp_to_delete)
        db.session.flush()

        dept.head_id = emp_to_delete.id
        self.employee_user.manager_id = emp_to_delete.id

        grant = LeaveGrant(
            company_id=self.company_a.id,
            employee_id=emp_to_delete.id,
            leave_type_id=self.lt_annual_a.id,
            year=date.today().year,
            mode='add',
            amount=5.0,
            old_total=12.0,
            new_total=17.0,
            actor_id=self.admin_user.id,
            request_token='test-grant-del-token'
        )
        db.session.add(grant)
        db.session.commit()

        # Admin soft deletes the employee
        self._login(self.admin_user)
        res = self.client.post(f'/admin/employees/delete/{emp_to_delete.id}', data={'action': 'delete'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify user is soft-deleted, historical grants remain intact in DB, and constraints are unlinked
        deleted_user = db.session.get(User, emp_to_delete.id)
        self.assertIsNotNone(deleted_user)
        self.assertTrue(deleted_user.is_deleted)
        self.assertFalse(deleted_user.is_active)
        self.assertIsNotNone(deleted_user.deleted_at)

        # Historical leave grant is preserved
        grant_in_db = db.session.get(LeaveGrant, grant.id)
        self.assertIsNotNone(grant_in_db)

        db.session.refresh(dept)
        self.assertIsNone(dept.head_id)

        db.session.refresh(self.employee_user)
        self.assertIsNone(self.employee_user.manager_id)

        # Restore the employee
        res_restore = self.client.post(f'/admin/employees/restore/{emp_to_delete.id}', follow_redirects=True)
        self.assertEqual(res_restore.status_code, 200)
        db.session.refresh(deleted_user)
        self.assertFalse(deleted_user.is_deleted)
        self.assertTrue(deleted_user.is_active)
        self.assertIsNone(deleted_user.deleted_at)

    def test_audit_trail_automatic_tracking(self):
        # 1. Admin creates a new department via web request
        self._login(self.admin_user)
        res = self.client.post('/admin/departments/add', data={
            'name': 'Finance & Tax',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        dept = Department.query.filter_by(name='Finance & Tax').first()
        self.assertIsNotNone(dept)
        self.assertEqual(dept.created_by_id, self.admin_user.id)
        self.assertEqual(dept.updated_by_id, self.admin_user.id)
        self.assertIsNotNone(dept.created_at)
        self.assertIsNotNone(dept.updated_at)

        # 2. Admin edits the department
        orig_created_at = dept.created_at
        res_edit = self.client.post(f'/admin/departments/edit/{dept.id}', data={
            'name': 'Finance, Accounting & Tax',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)

        db.session.refresh(dept)
        self.assertEqual(dept.name, 'Finance, Accounting & Tax')
        self.assertEqual(dept.created_by_id, self.admin_user.id)
        self.assertEqual(dept.updated_by_id, self.admin_user.id)
        self.assertEqual(dept.created_at, orig_created_at)

        # 3. Employee applies for leave and verify audit trail on LeaveRequest
        self._login(self.employee_user)
        res_apply = self.client.post('/apply', data={
            'leave_type': str(self.lt_annual_a.id),
            'day_part': 'full',
            'start_date': date(date.today().year, 11, 20).isoformat(),
            'end_date': date(date.today().year, 11, 20).isoformat(),
            'reason': 'Audit trail test leave',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res_apply.status_code, 200)

        req = LeaveRequest.query.filter_by(employee_id=self.employee_user.id, reason='Audit trail test leave').first()
        self.assertIsNotNone(req)
        self.assertEqual(req.created_by_id, self.employee_user.id)
        self.assertEqual(req.updated_by_id, self.employee_user.id)
        self.assertIsNotNone(req.created_at)
        self.assertIsNotNone(req.updated_at)

    def test_leave_history_import_preview_and_execute(self):
        self._login(self.admin_user)

        csv_text = (
            "Staff_Email,Leave_Category,Start,End,Lama_Hari,Status_Cuti,Notes\n"
            f"alice@test.com,Cuti Tahunan,10/01/{date.today().year},12/01/{date.today().year},3,Disetujui,Cuti awal tahun\n"
            f"manager@test.com,Cuti Sakit,{date.today().year}-02-15,{date.today().year}-02-15,1,Approved,Rawat jalan\n"
        )

        # 1. Test Preview
        res_preview = self.client.post('/approvals/history/import/preview', data={
            'file': (io.BytesIO(csv_text.encode('utf-8')), 'history_sample.csv')
        }, content_type='multipart/form-data')
        self.assertEqual(res_preview.status_code, 200)
        data = res_preview.get_json()
        self.assertTrue(data['success'])
        self.assertIn('Staff_Email', data['data']['headers'])
        self.assertEqual(data['data']['total_rows'], 2)

        # 2. Test Execute with custom column mapping
        import json
        mapping = {
            'employee': 'Staff_Email',
            'leave_type': 'Leave_Category',
            'start_date': 'Start',
            'end_date': 'End',
            'duration': 'Lama_Hari',
            'status': 'Status_Cuti',
            'reason': 'Notes'
        }

        res_exec = self.client.post('/approvals/history/import/execute', data={
            'file': (io.BytesIO(csv_text.encode('utf-8')), 'history_sample.csv'),
            'mapping': json.dumps(mapping),
            'sync_balances': '1'
        }, content_type='multipart/form-data')
        self.assertEqual(res_exec.status_code, 200)
        result = res_exec.get_json()
        self.assertTrue(result['success'])
        self.assertEqual(result['created'], 2)

        # Verify database
        emp_req = LeaveRequest.query.filter_by(employee_id=self.employee_user.id, reason='Cuti awal tahun').first()
        self.assertIsNotNone(emp_req)
        self.assertEqual(emp_req.status, 'approved')
        self.assertEqual(emp_req.duration_days, 3.0)

        # Verify leave balance deducted
        bal = LeaveBalance.query.filter_by(
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            year=date.today().year
        ).first()
        self.assertIsNotNone(bal)
        self.assertEqual(bal.used_days, 3.0)

    def test_employee_import_preview_and_execute(self):
        self._login(self.admin_user)

        csv_text = (
            "Full_Name,Work_Email,Position,Division,Supervisor,Initial_Pass\n"
            "Budi Santoso,budi@test.com,employee,Operations,admin@test.com,TriontSecure123!\n"
            "Siti Rahma,siti@test.com,manager,Finance,admin@test.com,TriontSecure123!\n"
        )

        # 1. Preview
        res_preview = self.client.post('/admin/employees/import/preview', data={
            'file': (io.BytesIO(csv_text.encode('utf-8')), 'employees_sample.csv')
        }, content_type='multipart/form-data')
        self.assertEqual(res_preview.status_code, 200)
        self.assertTrue(res_preview.get_json()['success'])

        # 2. Execute
        import json
        mapping = {
            'name': 'Full_Name',
            'email': 'Work_Email',
            'role': 'Position',
            'department': 'Division',
            'manager': 'Supervisor',
            'password': 'Initial_Pass'
        }
        res_exec = self.client.post('/admin/employees/import/execute', data={
            'file': (io.BytesIO(csv_text.encode('utf-8')), 'employees_sample.csv'),
            'mapping': json.dumps(mapping),
            'update_existing': '1'
        }, content_type='multipart/form-data')
        self.assertEqual(res_exec.status_code, 200)
        result = res_exec.get_json()
        self.assertTrue(result['success'])
        self.assertEqual(result['created'], 2)

        # Verify users & auto-created department
        budi = User.query.filter_by(email='budi@test.com').first()
        self.assertIsNotNone(budi)
        self.assertEqual(budi.name, 'Budi Santoso')
        self.assertEqual(budi.role, 'employee')
        self.assertEqual(budi.department.name, 'Operations')
        self.assertEqual(budi.manager_id, self.admin_user.id)

    def test_employee_archive_and_unarchive_workflow(self):
        self._login(self.admin_user)
        # 1. Archive employee
        res = self.client.post(f'/admin/employees/delete/{self.employee_user.id}', data={
            'action': 'archive',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)
        db.session.refresh(self.employee_user)
        self.assertFalse(self.employee_user.is_active)

        # 2. Unarchive employee
        res_un = self.client.post(f'/admin/employees/unarchive/{self.employee_user.id}', data={
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res_un.status_code, 302)
        db.session.refresh(self.employee_user)
        self.assertTrue(self.employee_user.is_active)

    def test_approval_history_view_and_filtering(self):
        self._login(self.admin_user)
        # Test approval history page render
        res = self.client.get('/approval-history')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Riwayat approval', res.data)

        # Test with filters
        res_filter = self.client.get(f'/approval-history?year={date.today().year}&status=approved')
        self.assertEqual(res_filter.status_code, 200)

    def test_filter_persistence_and_reset_buttons(self):
        self._login(self.admin_user)

        # 1. Employees list filter persistence & reset button
        res_emp_clean = self.client.get('/admin/employees')
        self.assertEqual(res_emp_clean.status_code, 200)

        res_emp_filtered = self.client.get('/admin/employees?q=Alice&role=employee')
        self.assertEqual(res_emp_filtered.status_code, 200)
        self.assertIn(b'Reset filter', res_emp_filtered.data)
        self.assertIn(b'Alice Employee', res_emp_filtered.data)

        # 2. Leave balances filter persistence & reset button
        res_bal_filtered = self.client.get(f'/admin/leave-balances?q=Alice&year={date.today().year - 1}')
        self.assertEqual(res_bal_filtered.status_code, 200)
        self.assertIn(b'Reset filter', res_bal_filtered.data)

        # 3. Leave types filter persistence & reset button
        res_lt_filtered = self.client.get('/admin/leave-types?q=Tahunan')
        self.assertEqual(res_lt_filtered.status_code, 200)
        self.assertIn(b'Reset filter', res_lt_filtered.data)

        # 4. Departments filter persistence & reset button
        res_dept_filtered = self.client.get('/admin/departments?q=Engineering')
        self.assertEqual(res_dept_filtered.status_code, 200)
        self.assertIn(b'Reset filter', res_dept_filtered.data)

        # 5. History filter persistence & reset button
        self._login(self.employee_user)
        res_hist_filtered = self.client.get('/history?status=pending')
        self.assertEqual(res_hist_filtered.status_code, 200)
        self.assertIn(b'Reset filter', res_hist_filtered.data)

    def test_global_confirm_modal_rendered_and_actions(self):
        self._login(self.admin_user)

        # 1. Verify global modal component is present in base layout
        res_page = self.client.get('/admin/leave-types')
        self.assertEqual(res_page.status_code, 200)
        self.assertIn(b'id="globalConfirmModal"', res_page.data)
        self.assertIn(b'window.showConfirmModal', res_page.data)
        self.assertIn(b'confirmArchiveLeaveType', res_page.data)
        self.assertIn(b'confirmDeleteLeaveType', res_page.data)

        # 2. Verify departments page has confirm hooks
        res_dept = self.client.get('/admin/departments')
        self.assertEqual(res_dept.status_code, 200)
        self.assertIn(b'confirmDeleteDepartment', res_dept.data)

        # 3. Verify companies page has confirm hooks
        res_comp = self.client.get('/admin/companies')
        self.assertEqual(res_comp.status_code, 200)
        self.assertIn(b'confirmDeleteCompany', res_comp.data)

        # 4. Verify approval history page has confirm hooks
        res_app_hist = self.client.get('/approval-history')
        self.assertEqual(res_app_hist.status_code, 200)
        self.assertIn(b'confirmDeleteApprovalHistory', res_app_hist.data)

        # 5. Verify employee history page has cancel confirm hook
        self._login(self.employee_user)
        res_hist = self.client.get('/history')
        self.assertEqual(res_hist.status_code, 200)
        self.assertIn(b'confirmCancelLeaveRequest', res_hist.data)

    def test_topbar_sticky_layout_does_not_create_a_root_scroll_container(self):
        self._login(self.admin_user)

        res = self.client.get('/admin/employees')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'.app-topbar { position:sticky;', res.data)
        self.assertIn(b'class="app-topbar no-print', res.data)
        self.assertNotIn(b'html, body { width:100%; max-width:100%; overflow-x:hidden; }', res.data)
        self.assertNotIn(b'id="app-shell" class="app-shell min-h-[100dvh] max-w-full overflow-x-clip', res.data)

    def test_custom_error_pages_403_404_500(self):
        # 1. Test 404 Not Found (HTML)
        res_404 = self.client.get('/non-existent-random-route-999')
        self.assertEqual(res_404.status_code, 404)
        self.assertIn(b'404', res_404.data)
        self.assertTrue(b'Halaman Tidak Ditemukan' in res_404.data or b'Page Not Found' in res_404.data)
        self.assertTrue(b'Kembali' in res_404.data or b'Back' in res_404.data)

        # 2. Test 404 JSON response
        res_404_json = self.client.get('/api/unknown-endpoint', headers={'Accept': 'application/json'})
        self.assertEqual(res_404_json.status_code, 404)
        self.assertTrue(res_404_json.is_json)
        self.assertEqual(res_404_json.get_json().get('status_code'), 404)

        # 3. Test 403 Forbidden template rendering & JSON response
        with self.app.test_request_context():
            from flask import render_template
            res_403_html = render_template('errors/403.html')
            self.assertIn('403', res_403_html)
            self.assertTrue('Akses Ditolak' in res_403_html or 'Access Denied' in res_403_html)

        # 4. Test 500 Internal Server Error template rendering & JSON response
        with self.app.test_request_context():
            from flask import render_template
            res_500_html = render_template('errors/500.html')
            self.assertIn('500', res_500_html)
            self.assertTrue('Terjadi Kesalahan Server' in res_500_html or 'Internal Server Error' in res_500_html)

    def test_bulk_actions_employees_leave_types_departments(self):
        self._login(self.admin_user)

        # 1. Verify Bulk UI elements exist on employees page
        res_emp_ui = self.client.get('/admin/employees')
        self.assertEqual(res_emp_ui.status_code, 200)
        self.assertIn(b'bulkActionBar', res_emp_ui.data)
        self.assertIn(b'selectAllCheckbox', res_emp_ui.data)
        self.assertIn(b'executeBulkAction', res_emp_ui.data)

        # 2. Bulk Archive Employees
        res_bulk_archive = self.client.post('/admin/employees/bulk-action', data={
            '_csrf_token': 'test-token',
            'action': 'archive',
            'ids': [str(self.employee_user.id)]
        }, follow_redirects=True)
        self.assertEqual(res_bulk_archive.status_code, 200)
        db.session.refresh(self.employee_user)
        self.assertFalse(self.employee_user.is_active)
        self.assertFalse(self.employee_user.is_deleted)

        # 3. Bulk Unarchive Employees
        res_bulk_unarchive = self.client.post('/admin/employees/bulk-action', data={
            '_csrf_token': 'test-token',
            'action': 'unarchive',
            'ids': [str(self.employee_user.id)]
        }, follow_redirects=True)
        self.assertEqual(res_bulk_unarchive.status_code, 200)
        db.session.refresh(self.employee_user)
        self.assertTrue(self.employee_user.is_active)

        # 4. Bulk Delete Employees (Soft delete)
        res_bulk_del = self.client.post('/admin/employees/bulk-action', data={
            '_csrf_token': 'test-token',
            'action': 'delete',
            'ids': [str(self.employee_user.id)]
        }, follow_redirects=True)
        self.assertEqual(res_bulk_del.status_code, 200)
        db.session.refresh(self.employee_user)
        self.assertTrue(self.employee_user.is_deleted)

        # 5. Bulk Restore Employees
        res_bulk_restore = self.client.post('/admin/employees/bulk-action', data={
            '_csrf_token': 'test-token',
            'action': 'restore',
            'ids': [str(self.employee_user.id)]
        }, follow_redirects=True)
        self.assertEqual(res_bulk_restore.status_code, 200)
        db.session.refresh(self.employee_user)
        self.assertFalse(self.employee_user.is_deleted)
        self.assertTrue(self.employee_user.is_active)

        # 6. Bulk Action on Leave Types
        res_lt_ui = self.client.get('/admin/leave-types')
        self.assertEqual(res_lt_ui.status_code, 200)
        self.assertIn(b'bulkActionBar', res_lt_ui.data)

        res_lt_archive = self.client.post('/admin/leave-types/bulk-action', data={
            '_csrf_token': 'test-token',
            'action': 'archive',
            'ids': [str(self.lt_annual_a.id)]
        }, follow_redirects=True)
        self.assertEqual(res_lt_archive.status_code, 200)
        db.session.refresh(self.lt_annual_a)
        self.assertFalse(self.lt_annual_a.is_active)

        res_lt_restore = self.client.post('/admin/leave-types/bulk-action', data={
            '_csrf_token': 'test-token',
            'action': 'unarchive',
            'ids': [str(self.lt_annual_a.id)]
        }, follow_redirects=True)
        self.assertEqual(res_lt_restore.status_code, 200)
        db.session.refresh(self.lt_annual_a)
        self.assertTrue(self.lt_annual_a.is_active)

        # 7. Bulk Action on Departments
        dept = Department(name='Engineering', company_id=self.company_a.id)
        db.session.add(dept)
        db.session.commit()

        res_dept_ui = self.client.get('/admin/departments')
        self.assertEqual(res_dept_ui.status_code, 200)
        self.assertIn(b'bulkActionBar', res_dept_ui.data)

        res_dept_del = self.client.post('/admin/departments/bulk-action', data={
            '_csrf_token': 'test-token',
            'action': 'delete',
            'ids': [str(dept.id)]
        }, follow_redirects=True)
        self.assertEqual(res_dept_del.status_code, 200)
        db.session.refresh(dept)
        self.assertTrue(dept.is_deleted)

        res_dept_restore = self.client.post('/admin/departments/bulk-action', data={
            '_csrf_token': 'test-token',
            'action': 'restore',
            'ids': [str(dept.id)]
        }, follow_redirects=True)
        self.assertEqual(res_dept_restore.status_code, 200)
        db.session.refresh(dept)
        self.assertFalse(dept.is_deleted)

    def test_admin_employees_toggle_archive(self):
        self._login(self.admin_user)
        # 1. Active tab
        res_active = self.client.get('/admin/employees?status=active')
        self.assertEqual(res_active.status_code, 200)
        self.assertIn(f'openEditEmployee({self.employee_user.id}'.encode('utf-8'), res_active.data)

        # 2. Archive Alice
        self.client.post(f'/admin/employees/delete/{self.employee_user.id}', data={
            'action': 'archive',
            '_csrf_token': 'test-token'
        })
        db.session.refresh(self.employee_user)
        self.assertFalse(self.employee_user.is_active)
        self.assertFalse(self.employee_user.is_deleted)

        # Active tab should not have Alice in table actions
        res_active_after = self.client.get('/admin/employees?status=active')
        self.assertEqual(res_active_after.status_code, 200)
        self.assertNotIn(f'openEditEmployee({self.employee_user.id}'.encode('utf-8'), res_active_after.data)

        # Archived tab should have Alice in table actions
        res_archived = self.client.get('/admin/employees?status=archived')
        self.assertEqual(res_archived.status_code, 200)
        self.assertIn(f'openEditEmployee({self.employee_user.id}'.encode('utf-8'), res_archived.data)

        # Also support legacy query ?archived=1
        res_archived_legacy = self.client.get('/admin/employees?archived=1')
        self.assertEqual(res_archived_legacy.status_code, 200)
        self.assertIn(f'openEditEmployee({self.employee_user.id}'.encode('utf-8'), res_archived_legacy.data)

        # 3. Soft delete Alice
        self.client.post(f'/admin/employees/delete/{self.employee_user.id}', data={
            'action': 'delete',
            '_csrf_token': 'test-token'
        })
        db.session.refresh(self.employee_user)
        self.assertTrue(self.employee_user.is_deleted)

        # Deleted tab should show Alice with restore button
        res_deleted = self.client.get('/admin/employees?status=deleted')
        self.assertEqual(res_deleted.status_code, 200)
        self.assertIn(f'/admin/employees/restore/{self.employee_user.id}'.encode('utf-8'), res_deleted.data)

        # Active and archived tabs should not have Alice
        self.assertNotIn(f'openEditEmployee({self.employee_user.id}'.encode('utf-8'), self.client.get('/admin/employees?status=active').data)
        self.assertNotIn(f'openEditEmployee({self.employee_user.id}'.encode('utf-8'), self.client.get('/admin/employees?status=archived').data)

        # 4. Restore Alice
        self.client.post(f'/admin/employees/restore/{self.employee_user.id}', follow_redirects=True)
        db.session.refresh(self.employee_user)
        self.assertFalse(self.employee_user.is_deleted)
        self.assertTrue(self.employee_user.is_active)

        # Alice is back in active tab
        self.assertIn(f'openEditEmployee({self.employee_user.id}'.encode('utf-8'), self.client.get('/admin/employees?status=active').data)

    def test_admin_leave_balances_overview(self):
        self._login(self.admin_user)
        res = self.client.get('/admin/leave-balances')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Saldo cuti', res.data)
        self.assertIn(self.employee_user.name.encode('utf-8'), res.data)

        # Test filtering by year and query
        res_filtered = self.client.get(f'/admin/leave-balances?year={date.today().year}&q=Alice')
        self.assertEqual(res_filtered.status_code, 200)
        self.assertIn(self.employee_user.name.encode('utf-8'), res_filtered.data)

    def test_leave_type_sequence_controls_dashboard_order(self):
        sick = LeaveType(company_id=self.company_a.id, name='Sick Leave', days_per_year=0, is_active=True, sort_order=10)
        self.lt_annual_a.sort_order = 20
        db.session.add(sick)
        db.session.flush()
        db.session.add(LeaveBalance(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=sick.id,
            year=date.today().year,
            total_days=0,
            used_days=0,
            pending_days=0,
        ))
        db.session.commit()

        self._login(self.employee_user)
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        balances_json = re.search(r'const balances = (.*?);', html).group(1)
        rendered_balances = json.loads(balances_json)
        self.assertEqual([b['name'] for b in rendered_balances], ['Sick Leave', 'Cuti Tahunan'])

        self._login(self.admin_user)
        res = self.client.post('/admin/leave-types/reorder', json={
            'ids': [self.lt_annual_a.id, sick.id]
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['ok'])
        db.session.refresh(self.lt_annual_a)
        db.session.refresh(sick)
        self.assertLess(self.lt_annual_a.sort_order, sick.sort_order)

        self._login(self.employee_user)
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        balances_json = re.search(r'const balances = (.*?);', html).group(1)
        rendered_balances = json.loads(balances_json)
        self.assertEqual([b['name'] for b in rendered_balances], ['Cuti Tahunan', 'Sick Leave'])

    def test_leave_type_archive_and_unarchive_workflow(self):
        self._login(self.admin_user)

        # 1. Initial list has annual leave in table
        res = self.client.get('/admin/leave-types')
        self.assertEqual(res.status_code, 200)
        self.assertIn(f'<p class="font-semibold text-gray-900">{self.lt_annual_a.name}</p>'.encode('utf-8'), res.data)

        # 2. Archive leave type
        res_archive = self.client.post(f'/admin/leave-types/archive/{self.lt_annual_a.id}', follow_redirects=True)
        self.assertEqual(res_archive.status_code, 200)
        
        with self.app.app_context():
            lt = db.session.get(LeaveType, self.lt_annual_a.id)
            self.assertFalse(lt.is_active)

        # 3. Active list should no longer show it in table
        res_active = self.client.get('/admin/leave-types')
        self.assertEqual(res_active.status_code, 200)
        self.assertNotIn(f'<p class="font-semibold text-gray-900">{self.lt_annual_a.name}</p>'.encode('utf-8'), res_active.data)

        # 4. Archived list should show it in table
        res_archived = self.client.get('/admin/leave-types?archived=1')
        self.assertEqual(res_archived.status_code, 200)
        self.assertIn(f'<p class="font-semibold text-gray-900">{self.lt_annual_a.name}</p>'.encode('utf-8'), res_archived.data)

        # 5. Unarchive leave type
        res_unarchive = self.client.post(f'/admin/leave-types/unarchive/{self.lt_annual_a.id}', follow_redirects=True)
        self.assertEqual(res_unarchive.status_code, 200)

        with self.app.app_context():
            lt = db.session.get(LeaveType, self.lt_annual_a.id)
            self.assertTrue(lt.is_active)

        # 6. Active list shows it again in table
        res_active_again = self.client.get('/admin/leave-types')
        self.assertEqual(res_active_again.status_code, 200)
        self.assertIn(f'<p class="font-semibold text-gray-900">{self.lt_annual_a.name}</p>'.encode('utf-8'), res_active_again.data)

        # 7. Soft delete leave type
        res_del = self.client.post(f'/admin/leave-types/delete/{self.lt_annual_a.id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        with self.app.app_context():
            lt = db.session.get(LeaveType, self.lt_annual_a.id)
            self.assertTrue(lt.is_deleted)

        # 8. Deleted list shows it with restore button
        res_deleted = self.client.get('/admin/leave-types?status=deleted')
        self.assertEqual(res_deleted.status_code, 200)
        self.assertIn(f'confirmRestoreLeaveType({self.lt_annual_a.id}'.encode('utf-8'), res_deleted.data)

        # 9. Restore leave type
        res_restore = self.client.post(f'/admin/leave-types/restore/{self.lt_annual_a.id}', follow_redirects=True)
        self.assertEqual(res_restore.status_code, 200)
        with self.app.app_context():
            lt = db.session.get(LeaveType, self.lt_annual_a.id)
            self.assertFalse(lt.is_deleted)
            self.assertTrue(lt.is_active)

    def test_calendar_request_drawer_allows_backdate_input(self):
        self._login(self.employee_user)
        res = self.client.get('/calendar')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'id="drawer-start-date"', res.data)
        self.assertIn(b'id="drawer-end-date"', res.data)
        self.assertNotIn(b'id="drawer-start-date" class="field" type="date" name="start_date" required min=', res.data)
        self.assertNotIn(b'id="drawer-end-date" class="field" type="date" name="end_date" required min=', res.data)

    def test_calendar_submission_errors_return_to_calendar(self):
        self._login(self.employee_user)
        start_d = date(date.today().year, 9, 8)
        res = self.client.post('/apply', data={
            'source': 'calendar',
            'start_date': start_d.isoformat(),
            'end_date': start_d.isoformat(),
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'id="leave-result-dialog"', res.data)
        self.assertIn(b'Please complete all required fields.', res.data)

    def test_calendar_submission_success_returns_to_calendar(self):
        self._login(self.employee_user)
        start_d = date(date.today().year, 9, 9)
        res = self.client.post('/apply', data={
            'source': 'calendar',
            'leave_type': str(self.lt_annual_a.id),
            'start_date': start_d.isoformat(),
            'end_date': start_d.isoformat(),
            'reason': 'Calendar request',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'id="leave-result-dialog"', res.data)
        self.assertIn(b'Leave request submitted', res.data)
        req = LeaveRequest.query.filter_by(employee_id=self.employee_user.id, reason='Calendar request').first()
        self.assertIsNotNone(req)

    def test_calendar_ical_feed_and_token_regeneration(self):
        # 1. Login as employee and create an approved leave request
        self._login(self.employee_user)
        token = self.employee_user.get_calendar_token()
        self.assertTrue(bool(token))
        self.assertGreaterEqual(len(token), 16)

        # Create approved leave
        today = date.today()
        leave = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=today,
            end_date=today + timedelta(days=2),
            duration_days=3,
            status='approved',
            reason='Family trip'
        )
        db.session.add(leave)
        db.session.commit()

        # 2. View calendar page
        res = self.client.get('/calendar')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'calendarSyncModal', res.data)
        self.assertIn(token.encode('utf-8'), res.data)

        # 3. Access public .ics feed endpoint
        res_ics = self.client.get(f'/calendar/feed/{token}.ics')
        self.assertEqual(res_ics.status_code, 200)
        self.assertIn('text/calendar', res_ics.headers.get('Content-Type', ''))
        self.assertIn(b'BEGIN:VCALENDAR', res_ics.data)
        self.assertIn(b'END:VCALENDAR', res_ics.data)
        self.assertIn(b'Alice Employee', res_ics.data)
        self.assertIn(b'Family trip', res_ics.data)

        # 4. Regenerate token
        res_regen = self.client.post('/calendar/sync/regenerate-token', follow_redirects=True)
        self.assertEqual(res_regen.status_code, 200)

        with self.app.app_context():
            user_fresh = db.session.get(User, self.employee_user.id)
            new_token = user_fresh.calendar_token
            self.assertNotEqual(token, new_token)

        # Old token gives 404
        res_old = self.client.get(f'/calendar/feed/{token}.ics')
        self.assertEqual(res_old.status_code, 404)

        # New token works
        res_new = self.client.get(f'/calendar/feed/{new_token}.ics')
        self.assertEqual(res_new.status_code, 200)
        self.assertIn(b'BEGIN:VCALENDAR', res_new.data)

    def test_pwa_manifest_service_worker_and_install_ui(self):
        # 1. Manifest endpoint
        res_manifest = self.client.get('/static/manifest.json')
        self.assertEqual(res_manifest.status_code, 200)
        self.assertIn(b'People by Triont', res_manifest.data)
        self.assertIn(b'standalone', res_manifest.data)

        # 2. Service worker endpoint
        res_sw = self.client.get('/sw.js')
        self.assertEqual(res_sw.status_code, 200)
        self.assertIn('application/javascript', res_sw.headers.get('Content-Type', ''))
        self.assertIn(b'people-pwa-v1', res_sw.data)

        # 3. Base layout PWA Install elements
        self._login(self.employee_user)
        res_page = self.client.get('/')
        self.assertEqual(res_page.status_code, 200)
        self.assertIn(b'pwa-install-sidebar', res_page.data)
        self.assertIn(b'pwa-install-drawer', res_page.data)
        self.assertIn(b'pwa-mobile-banner', res_page.data)
        self.assertIn(b'pwa-ios-modal', res_page.data)

    def test_admin_system_backup_download_zip_and_json(self):
        # 1. Non-admin is redirected with access denied
        self._login(self.employee_user)
        res_unauth = self.client.get('/admin/backup/download?format=zip')
        self.assertEqual(res_unauth.status_code, 302)

        # 2. Admin can download ZIP
        # 2. Admin can download ZIP (contains SQL, JSON, manifest)
        self._login(self.admin_user)
        res_zip = self.client.get('/admin/backup/download?format=zip')
        self.assertEqual(res_zip.status_code, 200)
        self.assertEqual(res_zip.headers.get('Content-Type'), 'application/zip')
        import zipfile
        zip_buf = io.BytesIO(res_zip.data)
        with zipfile.ZipFile(zip_buf, 'r') as z:
            self.assertIn('database_backup.sql', z.namelist())
            self.assertIn('database_backup.json', z.namelist())
            self.assertIn('manifest.json', z.namelist())

        # 3. Admin can download SQL dump
        res_sql = self.client.get('/admin/backup/download?format=sql')
        self.assertEqual(res_sql.status_code, 200)
        self.assertIn(b'INSERT INTO "users"', res_sql.data)
        self.assertIn(b'BEGIN;', res_sql.data)
        self.assertIn(b'COMMIT;', res_sql.data)

        # 4. Admin can download JSON
        res_json = self.client.get('/admin/backup/download?format=json')
        self.assertEqual(res_json.status_code, 200)
        self.assertEqual(res_json.headers.get('Content-Type'), 'application/json')
        backup_dict = json.loads(res_json.data.decode('utf-8'))
        self.assertEqual(backup_dict['version'], '1.0')
        self.assertIn('users', backup_dict)
        self.assertIn('companies', backup_dict)

    def test_leave_report_excel_export(self):
        self._login(self.admin_user)
        # 1. Main export endpoint
        res = self.client.get('/export/excel')
        self.assertEqual(res.status_code, 200)
        self.assertIn('spreadsheetml.sheet', res.headers.get('Content-Type', ''))
        self.assertTrue(len(res.data) > 1000)

        # 2. Admin reports export endpoint with filter
        res_filtered = self.client.get(f'/admin/reports/export?year={date.today().year}')
        self.assertEqual(res_filtered.status_code, 200)
        self.assertIn('spreadsheetml.sheet', res_filtered.headers.get('Content-Type', ''))

    def test_avatar_upload_serve_and_delete(self):
        self._login(self.employee_user)
        # 1. Upload valid image
        dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        res_upload = self.client.post('/settings', data={
            'name': 'Employee User Updated',
            'language': 'en',
            'avatar': (io.BytesIO(dummy_png), 'profile.png')
        }, content_type='multipart/form-data')
        self.assertEqual(res_upload.status_code, 302)

        db.session.refresh(self.employee_user)
        self.assertIsNotNone(self.employee_user.avatar_path)
        self.assertTrue(self.employee_user.avatar_path.startswith('uploads/avatars/'))

        # 2. Serve avatar
        res_avatar = self.client.get(f'/avatar/{self.employee_user.id}')
        self.assertEqual(res_avatar.status_code, 200)
        self.assertEqual(res_avatar.data, dummy_png)

        # 3. Delete avatar
        res_delete = self.client.post('/settings/avatar/delete')
        self.assertEqual(res_delete.status_code, 302)
        db.session.refresh(self.employee_user)
        self.assertIsNone(self.employee_user.avatar_path)

    def test_security_logs_are_global_and_superadmin_only(self):
        db.session.add(AuditLog(
            company_id=self.company_a.id,
            action='security.csrf_failed',
            details=json.dumps({'path': '/api/graphql', 'result': 'blocked', 'result_status': 400})
        ))
        db.session.add(AuditLog(
            company_id=self.company_b.id,
            action='security.suspicious_404',
            details=json.dumps({'path': '/.env', 'result': 'blocked', 'result_status': 404})
        ))
        db.session.add(AuditLog(
            company_id=self.company_a.id,
            actor_id=self.admin_user.id,
            action='admin.employee_updated',
            details=json.dumps({'name': 'Alice Employee'})
        ))
        db.session.commit()

        self._login(self.admin_user)
        audit_res = self.client.get('/admin/audit-logs')
        self.assertEqual(audit_res.status_code, 200)
        audit_html = audit_res.data.decode('utf-8')
        self.assertIn('admin.employee_updated', audit_html)
        self.assertNotIn('security.csrf_failed', audit_html)

        admin_security_res = self.client.get('/admin/security-logs')
        self.assertEqual(admin_security_res.status_code, 302)

        self._login(self.superadmin_user)
        security_res = self.client.get('/admin/security-logs')
        self.assertEqual(security_res.status_code, 200)
        security_html = security_res.data.decode('utf-8')
        self.assertIn('Security Logs', security_html)
        self.assertIn('security.csrf_failed', security_html)
        self.assertIn('security.suspicious_404', security_html)
        self.assertIn('Blocked 400', security_html)
        self.assertNotIn('admin.employee_updated', security_html)

        security_export = self.client.get('/admin/security-logs/export')
        self.assertEqual(security_export.status_code, 200)
        self.assertEqual(security_export.headers.get('Content-Type'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_only_superadmin_can_assign_superadmin_role(self):
        self._login(self.admin_user)
        res = self.client.post(f'/admin/employees/edit/{self.employee_user.id}', data={
            'name': self.employee_user.name,
            'email': self.employee_user.email,
            'role': 'superadmin',
            'company_id': str(self.company_a.id),
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)
        db.session.refresh(self.employee_user)
        self.assertEqual(self.employee_user.role, 'employee')

        self._login(self.superadmin_user)
        res = self.client.post(f'/admin/employees/edit/{self.employee_user.id}', data={
            'name': self.employee_user.name,
            'email': self.employee_user.email,
            'role': 'superadmin',
            'company_id': str(self.company_a.id),
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)
        db.session.refresh(self.employee_user)
        self.assertEqual(self.employee_user.role, 'superadmin')

    def test_suspicious_probe_404_and_forbidden_are_security_logs(self):
        from flask import abort

        @self.app.route('/_test_forbidden')
        def _test_forbidden():
            abort(403)

        self.client.get('/graphql')
        self.client.get('/_test_forbidden')

        probe_log = AuditLog.query.filter_by(action='security.suspicious_404').first()
        self.assertIsNotNone(probe_log)
        self.assertEqual(probe_log.details_dict['path'], '/graphql')
        self.assertEqual(probe_log.details_dict['result_status'], 404)

        forbidden_log = AuditLog.query.filter_by(action='security.forbidden').first()
        self.assertIsNotNone(forbidden_log)
        self.assertEqual(forbidden_log.details_dict['result_status'], 403)

    def test_update_audit_logs_include_before_after_changed_fields(self):
        self._login(self.admin_user)
        res = self.client.post(f'/admin/employees/edit/{self.employee_user.id}', data={
            'name': 'Alice Employee Renamed',
            'email': self.employee_user.email,
            'role': 'employee',
            'company_id': str(self.company_a.id),
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)

        log = AuditLog.query.filter_by(action='admin.employee_updated', target_id=self.employee_user.id).order_by(AuditLog.id.desc()).first()
        self.assertIsNotNone(log)
        details = log.details_dict
        self.assertEqual(details['before']['name'], 'Alice Employee')
        self.assertEqual(details['after']['name'], 'Alice Employee Renamed')
        self.assertEqual(details['changed']['name']['before'], 'Alice Employee')
        self.assertEqual(details['changed']['name']['after'], 'Alice Employee Renamed')

    def test_admin_can_update_employee_email(self):
        self._login(self.admin_user)
        res = self.client.post(f'/admin/employees/edit/{self.employee_user.id}', data={
            'name': self.employee_user.name,
            'email': 'alice.new@test.com',
            'role': 'employee',
            'company_id': str(self.company_a.id),
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)
        db.session.refresh(self.employee_user)
        self.assertEqual(self.employee_user.email, 'alice.new@test.com')

        log = AuditLog.query.filter_by(action='admin.employee_updated', target_id=self.employee_user.id).order_by(AuditLog.id.desc()).first()
        self.assertIsNotNone(log)
        changed = log.details_dict['changed']
        self.assertEqual(changed['email']['before'], 'alice@test.com')
        self.assertEqual(changed['email']['after'], 'alice.new@test.com')

    def test_user_settings_can_update_own_email(self):
        self._login(self.employee_user)
        res = self.client.post('/settings', data={
            'name': self.employee_user.name,
            'email': 'alice.profile@test.com',
            'language': 'en',
            'timezone': 'Asia/Jakarta',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(self.employee_user)
        self.assertEqual(self.employee_user.email, 'alice.profile@test.com')

    def test_user_settings_rejects_duplicate_email(self):
        self._login(self.employee_user)
        res = self.client.post('/settings', data={
            'name': self.employee_user.name,
            'email': self.manager_user.email,
            'language': 'en',
            'timezone': 'Asia/Jakarta',
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(self.employee_user)
        self.assertEqual(self.employee_user.email, 'alice@test.com')
        self.assertIn(b'Email manager@test.com is already used by Manager Bob', res.data)

    def test_admin_employee_duplicate_email_message_names_existing_user(self):
        self._login(self.admin_user)
        res = self.client.post(f'/admin/employees/edit/{self.employee_user.id}', data={
            'name': self.employee_user.name,
            'email': self.manager_user.email,
            'role': 'employee',
            'company_id': str(self.company_a.id),
            '_csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(self.employee_user)
        self.assertEqual(self.employee_user.email, 'alice@test.com')
        self.assertIn(b'Email manager@test.com is already used by Manager Bob', res.data)

    def test_avatar_upload_is_audited(self):
        self._login(self.employee_user)
        dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        res = self.client.post('/settings', data={
            'name': self.employee_user.name,
            'language': 'en',
            'avatar': (io.BytesIO(dummy_png), 'profile.png')
        }, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 302)

        log = AuditLog.query.filter_by(action='user.avatar_uploaded', target_id=self.employee_user.id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details_dict['extension'], 'png')

    def test_import_actions_use_specific_audit_names(self):
        from flask_login import login_user
        from services.import_service import audit_log as import_audit_log

        with self.app.test_request_context('/admin/employees/import/execute'):
            login_user(self.admin_user)
            import_audit_log(action='import.employees_completed', target_type='user', details={'created': 1}, company_id=self.company_a.id)
            import_audit_log(action='import.history_completed', target_type='leave_request', details={'created': 1}, company_id=self.company_a.id)
            db.session.commit()

        self.assertIsNotNone(AuditLog.query.filter_by(action='import.employees_completed').first())
        self.assertIsNotNone(AuditLog.query.filter_by(action='import.history_completed').first())

    def test_admin_audit_logs_access_filter_and_export(self):
        # 1. Non-admin gets redirected
        self._login(self.employee_user)
        res_emp = self.client.get('/admin/audit-logs')
        self.assertEqual(res_emp.status_code, 302)

        # 2. Admin can access audit logs page
        self._login(self.admin_user)
        res_admin = self.client.get('/admin/audit-logs')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn('Audit Log', res_admin.data.decode('utf-8'))

        # 3. Filter by category
        res_filter = self.client.get('/admin/audit-logs?category=auth')
        self.assertEqual(res_filter.status_code, 200)

        # 4. Admin can export audit logs to Excel
        res_export = self.client.get('/admin/audit-logs/export')
        self.assertEqual(res_export.status_code, 200)
        self.assertEqual(res_export.headers.get('Content-Type'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertGreater(len(res_export.data), 1000)

    def test_audit_mixin_and_modal_audit_info_translations(self):
        # 1. Verify model creator_name fallback to 'Sistem' when created_by_id is None
        company = self.company_a
        company.created_by_id = None
        company.updated_by_id = None
        self.assertEqual(company.creator_name, 'Sistem')
        self.assertEqual(company.updater_name, 'Sistem')

        self._login(self.admin_user)
        # 2. Check admin companies page renders audit translations (default EN or ID)
        res_comp = self.client.get('/admin/companies')
        self.assertEqual(res_comp.status_code, 200)
        html_comp = res_comp.data.decode('utf-8')
        self.assertTrue('By:' in html_comp or 'Oleh:' in html_comp)
        self.assertTrue('Created' in html_comp or 'Dibuat' in html_comp)
        self.assertTrue('Last Updated' in html_comp or 'Terakhir Diperbarui' in html_comp)

        # 3. Check admin departments page renders audit translations
        res_dept = self.client.get('/admin/departments')
        self.assertEqual(res_dept.status_code, 200)
        html_dept = res_dept.data.decode('utf-8')
        self.assertTrue('By:' in html_dept or 'Oleh:' in html_dept)

        # 4. Check admin leave types page renders audit translations
        res_lt = self.client.get('/admin/leave-types')
        self.assertEqual(res_lt.status_code, 200)
        html_lt = res_lt.data.decode('utf-8')
        self.assertTrue('By:' in html_lt or 'Oleh:' in html_lt)

        # 5. Check admin employees page renders audit translations
        res_emp = self.client.get('/admin/employees')
        self.assertEqual(res_emp.status_code, 200)
        html_emp = res_emp.data.decode('utf-8')
        self.assertTrue('By:' in html_emp or 'Oleh:' in html_emp)

    def test_timezone_settings_and_archive_leave_type_modal(self):
        self._login(self.admin_user)

        # 1. Check default timezone on settings page
        res_settings = self.client.get('/settings')
        self.assertEqual(res_settings.status_code, 200)
        self.assertIn('Asia/Jakarta', res_settings.data.decode('utf-8'))

        # 2. Update timezone preference to Asia/Jayapura (WIT, UTC+9)
        res_update = self.client.post('/settings', data={
            'name': 'Admin User',
            'language': 'en',
            'timezone': 'Asia/Jayapura',
        }, follow_redirects=True)
        self.assertEqual(res_update.status_code, 200)
        db.session.refresh(self.admin_user)
        self.assertEqual(self.admin_user.timezone_preference, 'Asia/Jayapura')

        # 3. Test timezone conversion utility
        from datetime import datetime, timezone
        from core.time_util import format_user_datetime, to_user_tz
        utc_dt = datetime(2026, 8, 19, 10, 0, 0)  # 10:00 UTC = 17:00 WIB (+7) = 19:00 WIT (+9)
        self.assertEqual(format_user_datetime(utc_dt, '%H:%M', tz_name='Asia/Jakarta'), '17:00')
        self.assertEqual(format_user_datetime(utc_dt, '%H:%M', tz_name='Asia/Jayapura'), '19:00')

        # 4. Check leave types page contains confirmation modal hooks without alert confirm
        res_lt = self.client.get('/admin/leave-types')
        self.assertEqual(res_lt.status_code, 200)
        html_lt = res_lt.data.decode('utf-8')
        self.assertIn('confirmArchiveLeaveType', html_lt)
        self.assertIn('globalConfirmModal', html_lt)
        self.assertNotIn("onsubmit=\"return confirm('Arsipkan", html_lt)

    def test_list_view_pagination_and_show_all(self):
        self._login(self.admin_user)

        # 1. Test pagination helper
        from core.pagination import get_pagination_args
        with self.app.test_request_context('/admin/employees?page=2&per_page=50'):
            p, pp, s = get_pagination_args(20)
            self.assertEqual(p, 2)
            self.assertEqual(pp, 50)
            self.assertEqual(s, '50')

        with self.app.test_request_context('/admin/employees?per_page=all'):
            p, pp, s = get_pagination_args(20)
            self.assertEqual(p, 1)
            self.assertEqual(pp, 100000)
            self.assertEqual(s, 'all')

        # 2. Add 25 employees to test 20-record pagination and show all
        for i in range(25):
            u = User(name=f'Bulk Worker {i}', email=f'bulk_{i}@example.com', role='employee', company_id=self.company_a.id)
            u.set_password('Secret123!')
            db.session.add(u)
        db.session.commit()

        # Check default page 1 returns 20 records and contains pagination controls
        res_emp = self.client.get('/admin/employees')
        self.assertEqual(res_emp.status_code, 200)
        html_emp = res_emp.data.decode('utf-8')
        self.assertTrue('Per halaman:' in html_emp or 'Per page:' in html_emp)
        self.assertIn('per_page=all', html_emp)
        self.assertIn('per_page=20', html_emp)
        self.assertIn('per_page=50', html_emp)

        # Check page 2
        res_page2 = self.client.get('/admin/employees?page=2')
        self.assertEqual(res_page2.status_code, 200)

        # Check per_page=all shows all
        res_all = self.client.get('/admin/employees?per_page=all')
        self.assertEqual(res_all.status_code, 200)
        html_all = res_all.data.decode('utf-8')
        self.assertTrue('Menampilkan semua' in html_all or 'Showing all' in html_all)

        # 3. Check leave balances page pagination
        res_bal = self.client.get('/admin/leave-balances')
        self.assertEqual(res_bal.status_code, 200)
        html_bal = res_bal.data.decode('utf-8')
        self.assertTrue('Per halaman:' in html_bal or 'Per page:' in html_bal)

        # 4. Check audit logs page pagination
        res_logs = self.client.get('/admin/audit-logs')
        self.assertEqual(res_logs.status_code, 200)
        html_logs = res_logs.data.decode('utf-8')
        self.assertTrue('Per halaman:' in html_logs or 'Per page:' in html_logs)

    def test_forgot_password_request_and_cooldown(self):
        # 1. Request OTP with registered email
        res = self.client.post('/auth/forgot-password', data={'email': 'alice@test.com'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b'OTP' in res.data)

        # Check DB record
        reset_entry = PasswordReset.query.filter_by(user_id=self.employee_user.id).order_by(PasswordReset.created_at.desc()).first()
        self.assertIsNotNone(reset_entry)
        self.assertFalse(reset_entry.is_used)
        self.assertEqual(reset_entry.attempts, 0)
        self.assertGreater(reset_entry.expires_at, utcnow())

        # 2. Immediate second request triggers 60s cooldown warning
        res_cd = self.client.post('/auth/forgot-password', data={'email': 'alice@test.com'}, follow_redirects=True)
        self.assertEqual(res_cd.status_code, 200)
        self.assertTrue(b'60' in res_cd.data or b'tunggu' in res_cd.data.lower() or b'wait' in res_cd.data.lower())

        # 3. Non-existent email returns neutral anti-enumeration info message
        with self.client.session_transaction() as sess:
            sess.clear()
        res_unknown = self.client.post('/auth/forgot-password', data={'email': 'unknown_user_99@test.com'}, follow_redirects=True)
        self.assertEqual(res_unknown.status_code, 200)
        self.assertTrue(b'email' in res_unknown.data.lower() or b'otp' in res_unknown.data.lower())

    def test_verify_otp_attempts_lockout_and_success(self):
        # 1. Request OTP
        self.client.post('/auth/forgot-password', data={'email': 'alice@test.com'}, follow_redirects=True)
        reset_entry = PasswordReset.query.filter_by(user_id=self.employee_user.id).order_by(PasswordReset.created_at.desc()).first()

        # 2. Submit wrong OTP -> increment attempts
        res_wrong1 = self.client.post('/auth/verify-otp', data={'otp': '000000'}, follow_redirects=True)
        self.assertEqual(res_wrong1.status_code, 200)
        db.session.refresh(reset_entry)
        self.assertEqual(reset_entry.attempts, 1)
        self.assertTrue(b'4' in res_wrong1.data)

        # 3. Submit wrong OTP 4 more times -> lockout on 5th failure
        for _ in range(3):
            self.client.post('/auth/verify-otp', data={'otp': '111111'}, follow_redirects=True)
        res_lockout = self.client.post('/auth/verify-otp', data={'otp': '222222'}, follow_redirects=True)
        self.assertEqual(res_lockout.status_code, 200)
        db.session.refresh(reset_entry)
        self.assertEqual(reset_entry.attempts, 5)
        self.assertTrue(reset_entry.is_locked)

        # 4. Now create a fresh valid OTP entry and verify successfully
        reset_fresh = PasswordReset(
            user_id=self.employee_user.id,
            expires_at=utcnow() + timedelta(minutes=15),
            created_by_id=self.employee_user.id
        )
        reset_fresh.set_otp('789123')
        db.session.add(reset_fresh)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['reset_email'] = self.employee_user.email

        res_ok = self.client.post('/auth/verify-otp', data={'otp': '789123'}, follow_redirects=True)
        self.assertEqual(res_ok.status_code, 200)
        self.assertTrue(b'new_password' in res_ok.data or b'Password' in res_ok.data)
        db.session.refresh(reset_fresh)
        self.assertIsNotNone(reset_fresh.reset_token)

    def test_reset_password_workflow_and_login(self):
        # 1. Accessing reset password without valid token redirects to forgot-password
        res_unauth = self.client.get('/auth/reset-password', follow_redirects=True)
        self.assertEqual(res_unauth.status_code, 200)
        self.assertTrue(b'forgot' in res_unauth.data.lower() or b'lupa' in res_unauth.data.lower() or b'email' in res_unauth.data.lower())

        # 2. Setup verified session
        reset_entry = PasswordReset(
            user_id=self.employee_user.id,
            expires_at=utcnow() + timedelta(minutes=15),
            created_by_id=self.employee_user.id,
            reset_token='test-valid-reset-token-xyz'
        )
        reset_entry.set_otp('654321')
        db.session.add(reset_entry)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess['reset_token'] = 'test-valid-reset-token-xyz'
            sess['reset_user_id'] = self.employee_user.id
            sess['reset_email'] = self.employee_user.email

        # 3. Test password mismatch
        res_mismatch = self.client.post('/auth/reset-password', data={
            'new_password': 'NewPassword123!',
            'confirm_password': 'DifferentPassword123!'
        }, follow_redirects=True)
        self.assertEqual(res_mismatch.status_code, 200)
        self.assertTrue(b'tidak cocok' in res_mismatch.data or b'match' in res_mismatch.data.lower())

        # 4. Test weak password
        res_weak = self.client.post('/auth/reset-password', data={
            'new_password': 'weak',
            'confirm_password': 'weak'
        }, follow_redirects=True)
        self.assertEqual(res_weak.status_code, 200)
        self.assertTrue(b'8' in res_weak.data)

        # 5. Submit valid new password
        res_success = self.client.post('/auth/reset-password', data={
            'new_password': 'BrandNewPass2026!',
            'confirm_password': 'BrandNewPass2026!'
        }, follow_redirects=True)
        self.assertEqual(res_success.status_code, 200)
        self.assertTrue(b'login' in res_success.data.lower() or b'masuk' in res_success.data.lower() or b'password' in res_success.data.lower())

        # Verify DB state
        db.session.refresh(reset_entry)
        self.assertTrue(reset_entry.is_used)
        self.assertIsNone(reset_entry.reset_token)

        # 6. Test login with old password fails
        res_old_login = self.client.post('/auth/login', data={
            'email': 'alice@test.com',
            'password': 'EmployeePass123'
        }, follow_redirects=True)
        self.assertEqual(res_old_login.status_code, 200)
        self.assertTrue(b'salah' in res_old_login.data.lower() or b'incorrect' in res_old_login.data.lower() or b'invalid' in res_old_login.data.lower())

        # 7. Test login with new password succeeds!
        res_new_login = self.client.post('/auth/login', data={
            'email': 'alice@test.com',
            'password': 'BrandNewPass2026!'
        }, follow_redirects=True)
        self.assertEqual(res_new_login.status_code, 200)
        self.assertTrue(b'Alice' in res_new_login.data or b'dashboard' in res_new_login.data.lower())

    def test_logged_in_password_change_with_otp(self):
        self._login(self.employee_user)

        # -------------------------------------------------------------
        # OPTION 1: Direct Password Change (with Current Password)
        # -------------------------------------------------------------
        # 1a. Wrong current password -> redirects with error flash
        res_wrong_cur = self.client.post('/settings', data={
            'current_password': 'WrongCurrentPassword',
            'new_password': 'NewPassword123!',
            'confirm_password': 'NewPassword123!'
        }, follow_redirects=True)
        self.assertEqual(res_wrong_cur.status_code, 200)
        self.assertTrue(b'Current password is incorrect' in res_wrong_cur.data or b'Password saat ini salah' in res_wrong_cur.data)

        # 1b. Password mismatch
        res_mismatch = self.client.post('/settings', data={
            'current_password': 'AlicePass123',
            'new_password': 'NewPassword123!',
            'confirm_password': 'DifferentPassword123!'
        }, follow_redirects=True)
        self.assertEqual(res_mismatch.status_code, 200)
        self.assertTrue(b'do not match' in res_mismatch.data or b'tidak cocok' in res_mismatch.data)

        # 1c. Valid direct password update -> 200
        res_direct_ok = self.client.post('/settings', data={
            'current_password': 'AlicePass123',
            'new_password': 'AliceDirectPass888!',
            'confirm_password': 'AliceDirectPass888!'
        }, follow_redirects=True)
        self.assertEqual(res_direct_ok.status_code, 200)
        self.assertTrue(b'Password updated' in res_direct_ok.data or b'Password berhasil' in res_direct_ok.data or b'Profile updated' in res_direct_ok.data)

        # Verify DB updated
        db.session.refresh(self.employee_user)
        self.assertTrue(self.employee_user.check_password('AliceDirectPass888!'))

        # -------------------------------------------------------------
        # OPTION 2: Forgot Old Password (Reset via Email OTP)
        # -------------------------------------------------------------
        # 2a. Valid request OTP -> 200
        res_req = self.client.post('/settings/password/request-otp')
        self.assertEqual(res_req.status_code, 200)
        data = res_req.get_json()
        self.assertTrue(data['ok'])

        # Check DB record
        reset_entry = PasswordReset.query.filter_by(user_id=self.employee_user.id).order_by(PasswordReset.created_at.desc()).first()
        self.assertIsNotNone(reset_entry)
        self.assertFalse(reset_entry.is_used)

        # 2b. Immediate 2nd request -> 429 cooldown
        res_cd = self.client.post('/settings/password/request-otp')
        self.assertEqual(res_cd.status_code, 429)

        # 2c. Verify with wrong OTP -> 400
        res_wrong_otp = self.client.post('/settings/password/verify-otp', data={
            'otp': '000000',
            'new_password': 'OtpResetPass999!',
            'confirm_password': 'OtpResetPass999!'
        })
        self.assertEqual(res_wrong_otp.status_code, 400)
        db.session.refresh(reset_entry)
        self.assertEqual(reset_entry.attempts, 1)

        # 2d. Setup known OTP and verify successfully
        reset_entry.set_otp('321987')
        db.session.commit()

        res_ok = self.client.post('/settings/password/verify-otp', data={
            'otp': '321987',
            'new_password': 'OtpResetPass999!',
            'confirm_password': 'OtpResetPass999!'
        })
        self.assertEqual(res_ok.status_code, 200)
        self.assertTrue(res_ok.get_json()['ok'])

        # Verify password in DB
        db.session.refresh(self.employee_user)
        self.assertTrue(self.employee_user.check_password('OtpResetPass999!'))

        # 2e. Login with new OTP-reset password
        self.client.get('/auth/logout')
        res_login = self.client.post('/auth/login', data={
            'email': 'alice@test.com',
            'password': 'OtpResetPass999!'
        }, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)
        self.assertTrue(b'Alice' in res_login.data or b'dashboard' in res_login.data.lower())

    def test_admin_impersonate_user_and_stop_workflow(self):
        # 1. Non-admin cannot impersonate (redirects with access denied)
        self._login(self.employee_user)
        res_forbidden = self.client.post(f'/admin/impersonate/{self.manager_user.id}', follow_redirects=True)
        self.assertEqual(res_forbidden.status_code, 200)
        self.assertTrue(b'Access denied' in res_forbidden.data or b'Akses ditolak' in res_forbidden.data or b'denied' in res_forbidden.data.lower())

        # 2. Super admin impersonates Alice
        self._login(self.admin_user)
        res_impersonate = self.client.post(f'/admin/impersonate/{self.employee_user.id}', follow_redirects=True)
        self.assertEqual(res_impersonate.status_code, 200)

        # Check session & rendered page
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('impersonator_admin_id'), self.admin_user.id)
            self.assertEqual(sess.get('_user_id'), str(self.employee_user.id))

        self.assertTrue(b'Simulasi' in res_impersonate.data or b'Simulation' in res_impersonate.data or b'Alice' in res_impersonate.data)

        # 3. Stop impersonation
        res_stop = self.client.post('/admin/stop-impersonation', follow_redirects=True)
        self.assertEqual(res_stop.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get('impersonator_admin_id'))
            self.assertEqual(sess.get('_user_id'), str(self.admin_user.id))

        self.assertTrue(b'Admin' in res_stop.data or b'karyawan' in res_stop.data.lower() or b'employee' in res_stop.data.lower())

        # 4. Impersonate via GET link (Open in new tab link support)
        res_get_imp = self.client.get(f'/admin/impersonate/{self.employee_user.id}', follow_redirects=True)
        self.assertEqual(res_get_imp.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('impersonator_admin_id'), self.admin_user.id)
            self.assertEqual(sess.get('_user_id'), str(self.employee_user.id))

    def test_admin_send_employee_password_reset(self):
        # 1. Non-admin cannot trigger reset email
        self._login(self.employee_user)
        res_forbidden = self.client.post(f'/admin/employees/{self.manager_user.id}/send-reset-password', follow_redirects=True)
        self.assertEqual(res_forbidden.status_code, 200)
        self.assertTrue(b'Access denied' in res_forbidden.data or b'Akses ditolak' in res_forbidden.data or b'denied' in res_forbidden.data.lower())

        # 2. Super admin sends reset link via AJAX to Alice
        self._login(self.admin_user)
        res_ajax = self.client.post(
            f'/admin/employees/{self.employee_user.id}/send-reset-password',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(res_ajax.status_code, 200)
        data = res_ajax.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('alice@test.com', data.get('employee_email'))

        # 3. Check created PasswordReset record with reset_token
        reset_entry = PasswordReset.query.filter_by(user_id=self.employee_user.id).order_by(PasswordReset.created_at.desc()).first()
        self.assertIsNotNone(reset_entry)
        self.assertFalse(reset_entry.is_used)
        self.assertIsNotNone(reset_entry.reset_token)
        self.assertEqual(reset_entry.created_by_id, self.admin_user.id)

        # 4. Logout admin and simulate Alice opening the direct reset link
        self.client.get('/auth/logout')
        res_link = self.client.get(f'/auth/reset-password?token={reset_entry.reset_token}', follow_redirects=True)
        self.assertEqual(res_link.status_code, 200)
        self.assertTrue(b'Buat Kata Sandi Baru' in res_link.data or b'Create New Password' in res_link.data or b'password' in res_link.data.lower())

        # 5. Alice submits new password
        res_change = self.client.post('/auth/reset-password', data={
            'new_password': 'AliceDirectNewPass1!',
            'confirm_password': 'AliceDirectNewPass1!'
        }, follow_redirects=True)
        self.assertEqual(res_change.status_code, 200)

        # Verify DB and login
        db.session.refresh(reset_entry)
        self.assertTrue(reset_entry.is_used)
        res_alice_login = self.client.post('/auth/login', data={
            'email': 'alice@test.com',
            'password': 'AliceDirectNewPass1!'
        }, follow_redirects=True)
        self.assertEqual(res_alice_login.status_code, 200)

    def test_who_is_out_this_week_widget_on_dashboard(self):
        # Create an approved leave request for employee in next 2 days
        today = date.today()
        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=today,
            end_date=today + timedelta(days=2),
            duration_days=3.0,
            reason="Holiday trip",
            status="approved",
            approved_by=self.manager_user.id,
            approved_at=utcnow()
        )
        db.session.add(req)
        db.session.commit()

        # Login as manager and check dashboard
        self._login(self.manager_user)
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(b'Siapa Cuti Minggu Ini' in res.data or b'Who is on Leave This Week' in res.data)
        self.assertIn(b'Alice Employee', res.data)
        self.assertTrue(b'Hari Ini' in res.data or b'Today' in res.data)

    def test_leave_slip_print_view_and_access_control(self):
        # Create an approved leave request for employee
        today = date.today()
        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=today,
            end_date=today + timedelta(days=1),
            duration_days=2.0,
            reason="Family gathering",
            status="approved",
            approved_by=self.manager_user.id,
            approved_at=utcnow(),
            notes="Enjoy your leave!"
        )
        db.session.add(req)
        db.session.commit()

        # 1. Owner can view leave slip
        self._login(self.employee_user)
        res_owner = self.client.get(f'/leaves/{req.id}/slip')
        self.assertEqual(res_owner.status_code, 200)
        self.assertTrue(b'Slip' in res_owner.data or b'Bukti' in res_owner.data)
        self.assertIn(b'Alice Employee', res_owner.data)
        self.assertIn(b'Family gathering', res_owner.data)
        self.assertIn(b'Enjoy your leave!', res_owner.data)

        # 2. Manager can view leave slip
        self._login(self.manager_user)
        res_manager = self.client.get(f'/leaves/{req.id}/slip')
        self.assertEqual(res_manager.status_code, 200)
        self.assertIn(b'Alice Employee', res_manager.data)

        # 3. Check history page contains the print button
        self._login(self.employee_user)
        res_history = self.client.get('/history')
        self.assertEqual(res_history.status_code, 200)
        self.assertIn(f'/leaves/{req.id}/slip'.encode(), res_history.data)

    def test_annual_leave_balance_rollover(self):
        """Test the /admin/leave-balances/rollover endpoint for reset and carry-forward modes."""
        from_year = date.today().year
        to_year = from_year + 1

        # Seed/update a balance for employee in from_year
        bal = LeaveBalance.query.filter_by(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            year=from_year,
        ).first()
        if bal:
            bal.total_days = 12.0
            bal.used_days = 8.0
            bal.pending_days = 0.0
        else:
            bal = LeaveBalance(
                company_id=self.company_a.id,
                employee_id=self.employee_user.id,
                leave_type_id=self.lt_annual_a.id,
                year=from_year,
                total_days=12.0,
                used_days=8.0,
                pending_days=0.0,
            )
            db.session.add(bal)
        db.session.commit()

        self._login(self.admin_user)

        # --- 1. Reset mode: to_year balance = leave_type.days_per_year (no carry) ---
        token_reset = 'resettoken-abcdefghij1234567890'
        res = self.client.post('/admin/leave-balances/rollover',
            json={'from_year': from_year, 'mode': 'reset', 'leave_type_ids': [self.lt_annual_a.id], 'rollover_token': token_reset},
            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['ok'], data.get('message'))

        dst_bal = LeaveBalance.query.filter_by(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            year=to_year,
        ).first()
        self.assertIsNotNone(dst_bal)
        # Should equal days_per_year (no carry)
        self.assertEqual(dst_bal.total_days, float(self.lt_annual_a.days_per_year))

        # --- 2. Idempotency: same token returns ok=True, skipped=True without duplicate ---
        res_idem = self.client.post('/admin/leave-balances/rollover',
            json={'from_year': from_year, 'mode': 'reset', 'leave_type_ids': [self.lt_annual_a.id], 'rollover_token': token_reset},
            content_type='application/json')
        data_idem = res_idem.get_json()
        self.assertTrue(data_idem['ok'])
        self.assertTrue(data_idem.get('skipped'))

        # --- 3. Carry-forward mode: to_year balance = days_per_year + remaining (capped at 3) ---
        # remaining = 12 - 8 = 4, cap = 3 → carry = 3
        dst_bal.total_days = 0  # reset dst so we can recheck
        dst_bal.used_days = 0
        db.session.commit()

        token_carry = 'carrytoken-abcdefghij1234567890'
        res_cf = self.client.post('/admin/leave-balances/rollover',
            json={'from_year': from_year, 'mode': 'carry_forward', 'max_carry_days': 3, 'leave_type_ids': [self.lt_annual_a.id], 'rollover_token': token_carry},
            content_type='application/json')
        self.assertEqual(res_cf.status_code, 200)
        data_cf = res_cf.get_json()
        self.assertTrue(data_cf['ok'])

        db.session.refresh(dst_bal)
        expected = float(self.lt_annual_a.days_per_year) + 3.0  # capped carry
        self.assertAlmostEqual(dst_bal.total_days, expected, places=1)

        # --- 4. Invalid mode returns 400 ---
        res_bad = self.client.post('/admin/leave-balances/rollover',
            json={'from_year': from_year, 'mode': 'invalid', 'rollover_token': 'validtoken-abcdefghij1234'},
            content_type='application/json')
        self.assertEqual(res_bad.status_code, 400)

    def test_hr_and_manager_approval_permissions_and_fallbacks(self):
        """Test that HR can approve leaves without 403 when config is None or director, and managers can approve their subordinates."""
        # Create an HR user
        hr_user = User(name='HR Staff', email='hr@test.com', role='hr', company_id=self.company_a.id)
        hr_user.set_password('HrPass123')
        db.session.add(hr_user)
        db.session.commit()

        # 1. Leave request for leave type without any ApprovalConfig (config is None)
        lt_special = LeaveType(company_id=self.company_a.id, name='Cuti Khusus', days_per_year=5, is_active=True)
        db.session.add(lt_special)
        db.session.commit()

        bal_special = LeaveBalance(company_id=self.company_a.id, employee_id=self.employee_user.id, leave_type_id=lt_special.id, year=date.today().year, total_days=5, used_days=0, pending_days=1)
        db.session.add(bal_special)

        req1 = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=lt_special.id,
            start_date=date(date.today().year, 12, 1),
            end_date=date(date.today().year, 12, 1),
            duration_days=1.0,
            status='pending',
            current_approval_level=1,
            max_approval_level=1
        )
        db.session.add(req1)
        db.session.commit()

        # HR approves req1 (no ApprovalConfig in DB)
        self._login(hr_user, 'HrPass123')
        res1 = self.client.post(f'/approve/{req1.id}', data={
            'action': 'approve',
            'expected_level': '1',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res1.status_code, 302)
        db.session.refresh(req1)
        self.assertEqual(req1.status, 'approved')

        # 2. Leave request with ApprovalConfig role = 'director'
        cfg_dir = ApprovalConfig(company_id=self.company_a.id, leave_type_id=lt_special.id, level=1, approver_role='director')
        db.session.add(cfg_dir)
        db.session.commit()

        req2 = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=lt_special.id,
            start_date=date(date.today().year, 12, 2),
            end_date=date(date.today().year, 12, 2),
            duration_days=1.0,
            status='pending',
            current_approval_level=1,
            max_approval_level=1
        )
        db.session.add(req2)
        bal_special.pending_days = 1.0
        db.session.commit()

        # HR approves req2 (approver_role = 'director' should not 403 HR)
        res2 = self.client.post(f'/approve/{req2.id}', data={
            'action': 'approve',
            'expected_level': '1',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res2.status_code, 302)
        db.session.refresh(req2)
        self.assertEqual(req2.status, 'approved')

    def test_manager_leave_skips_manager_stage_and_routes_to_hr(self):
        hr_user = User(name='HR Maya', email='hr-maya@test.com', role='hr', company_id=self.company_a.id)
        hr_user.set_password('HrPass123')
        manager_balance = LeaveBalance(
            company_id=self.company_a.id,
            employee_id=self.manager_user.id,
            leave_type_id=self.lt_annual_a.id,
            year=date.today().year,
            total_days=12,
            used_days=0,
            pending_days=0,
        )
        hr_level = ApprovalConfig(
            company_id=self.company_a.id,
            leave_type_id=self.lt_annual_a.id,
            level=2,
            approver_role='hr',
        )
        self.company_a.notifications_enabled = True
        self.company_a.notify_on_submit = True
        db.session.add_all([hr_user, manager_balance, hr_level])
        db.session.commit()

        start_date = date.today() + timedelta(days=21)
        while start_date.weekday() >= 5:
            start_date += timedelta(days=1)

        self._login(self.manager_user)
        submitted = self.client.post('/apply', data={
            'leave_type': self.lt_annual_a.id,
            'day_part': 'full',
            'start_date': start_date.isoformat(),
            'end_date': start_date.isoformat(),
            'reason': 'Manager leave',
            '_csrf_token': 'test-token',
        })
        self.assertEqual(submitted.status_code, 302)
        req = LeaveRequest.query.filter_by(employee_id=self.manager_user.id, reason='Manager leave').first()
        self.assertIsNotNone(req)
        self.assertEqual(req.current_approval_level, 2)
        self.assertEqual(req.max_approval_level, 2)

        hr_email = NotificationOutbox.query.filter_by(
            leave_request_id=req.id,
            recipient_email='hr-maya@test.com',
        ).first()
        self.assertIsNotNone(hr_email)
        self.assertIn('memerlukan persetujuan Anda', hr_email.body)

        from services.notification_outbox_service import queue_notification
        resend_rows = queue_notification(
            self.company_a,
            'submit',
            req,
            recipient_scope='approver',
            force=True,
        )
        self.assertEqual(len(resend_rows), 1)
        self.assertEqual(resend_rows[0].recipient_email, 'hr-maya@test.com')

        self._login(hr_user, 'HrPass123')
        approved = self.client.post(f'/approve/{req.id}', data={
            'action': 'approve',
            'expected_level': '2',
            '_csrf_token': 'test-token',
        })
        self.assertEqual(approved.status_code, 302)
        db.session.refresh(req)
        self.assertEqual(req.status, 'approved')

    def test_legacy_manager_request_resends_to_hr_and_finishes_once(self):
        hr = User(name='HR Maya', email='hr-maya@test.com', role='hr', company_id=self.company_a.id)
        hr.set_password('HrPass123')
        other_hr = User(name='Other HR', email='other-hr@test.com', role='hr', company_id=self.company_b.id)
        other_hr.set_password('HrPass123')
        inactive_hr = User(name='Inactive HR', email='inactive-hr@test.com', role='hr',
                           company_id=self.company_a.id, is_active=False)
        inactive_hr.set_password('HrPass123')
        req = LeaveRequest(
            company_id=self.company_a.id, employee_id=self.manager_user.id,
            leave_type_id=self.lt_annual_a.id, start_date=date(date.today().year, 9, 21),
            end_date=date(date.today().year, 9, 21), duration_days=1,
            status='pending', current_approval_level=1, max_approval_level=2,
        )
        balance = LeaveBalance(company_id=self.company_a.id, employee_id=self.manager_user.id,
                               leave_type_id=self.lt_annual_a.id, year=date.today().year,
                               total_days=12, used_days=0, pending_days=1)
        db.session.add_all([hr, other_hr, inactive_hr, req, balance, ApprovalConfig(
            company_id=self.company_a.id, leave_type_id=self.lt_annual_a.id,
            level=2, approver_role='hr',
        )])
        self.company_a.smtp_host = 'smtp.example.test'
        self.company_a.smtp_user = 'noreply@example.test'
        db.session.commit()
        self._login(self.admin_user)
        from flask import render_template
        with patch('routes.approvals.render_template', wraps=render_template) as rendered:
            self.client.get('/approval-history')
        preview_names = rendered.call_args.kwargs['resend_approver_names'][req.id]
        self.assertEqual(preview_names, ['HR Maya'])
        with patch('services.notification_service._dispatch_email') as smtp:
            result = self.client.post(f'/approval-history/{req.id}/resend-notification',
                                      data={'recipient_scope': 'approver'}, follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'Email resend queued', result.data)
        smtp.assert_not_called()
        rows = NotificationOutbox.query.filter_by(leave_request_id=req.id).all()
        self.assertEqual([row.recipient_email for row in rows], ['hr-maya@test.com'])
        self.assertIn('Kirim ulang: Perlu tindakan', rows[0].subject)
        self.assertIn('Persetujuan HR (tahap 2 dari 2)', rows[0].body)
        self.assertIn('Approve (Setujui) atau Reject (Tolak)', rows[0].body)
        self.assertIn('https://people.thehyouman.com/approvals', rows[0].body)
        db.session.refresh(req)
        self.assertEqual(req.current_approval_level, 1)  # Resend never changes workflow state.
        self.assertEqual(req.status, 'pending')
        self._login(hr, 'HrPass123')
        approved = self.client.post(f'/approve/{req.id}', data={'action': 'approve', 'expected_level': '1'})
        self.assertEqual(approved.status_code, 302)
        db.session.refresh(req)
        db.session.refresh(balance)
        self.assertEqual(req.status, 'approved')
        self.assertEqual(req.current_approval_level, 2)
        self.assertEqual(balance.used_days, 1)
        self.assertEqual(balance.pending_days, 0)
        self.client.post(f'/approve/{req.id}', data={'action': 'approve', 'expected_level': '1'})
        db.session.refresh(balance)
        self.assertEqual(balance.used_days, 1)

        self._login(self.admin_user)
        before = NotificationOutbox.query.filter_by(leave_request_id=req.id).count()
        completed = self.client.post(f'/approval-history/{req.id}/resend-notification',
                                     data={'recipient_scope': 'approver'}, follow_redirects=True)
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(b'This request is no longer pending.' in completed.data)
        self.assertEqual(NotificationOutbox.query.filter_by(leave_request_id=req.id).count(), before)

    def test_calendar_cross_month_leave_display(self):
        """Test that leave spanning across two months is properly displayed on both month calendar views."""
        this_year = date.today().year
        # Cross-month leave: Aug 28 to Sept 4
        req_cross = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=date(this_year, 8, 28),
            end_date=date(this_year, 9, 4),
            duration_days=8.0,
            status='approved',
            current_approval_level=1,
            max_approval_level=1
        )
        db.session.add(req_cross)
        db.session.commit()

        self._login(self.admin_user)

        # 1. View August calendar
        res_aug = self.client.get(f'/calendar?month=8&year={this_year}')
        self.assertEqual(res_aug.status_code, 200)
        self.assertIn(b'Alice Employee', res_aug.data)

        # 2. View September calendar (must still show Alice Employee for Sept 1-4)
        res_sep = self.client.get(f'/calendar?month=9&year={this_year}')
        self.assertEqual(res_sep.status_code, 200)
        self.assertIn(b'Alice Employee', res_sep.data)

    def test_submit_leave_notification_dispatches_to_manager(self):
        """Submit notifications go to requester, approver, and active same-company users only."""
        from services.notification_service import send_notification
        this_year = date.today().year
        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=date(this_year, 11, 1),
            end_date=date(this_year, 11, 2),
            duration_days=2.0,
            status='pending',
            current_approval_level=1,
            max_approval_level=1
        )
        db.session.add(req)
        db.session.commit()

        self.company_a.notifications_enabled = True
        self.company_a.notify_on_submit = True
        db.session.commit()

        with patch('services.notification_service._dispatch_email', return_value=True) as dispatch:
            send_notification(self.company_a, 'submit', req)

        recipients = [call.args[1] for call in dispatch.call_args_list]
        self.assertIn('alice@test.com', recipients)
        self.assertIn('manager@test.com', recipients)
        self.assertIn('admin@test.com', recipients)
        self.assertIn('superadmin@test.com', recipients)
        self.assertNotIn('charlie@test.com', recipients)
        self.assertEqual(len(recipients), len(set(recipients)))
        bodies = {call.args[1]: call.args[3] for call in dispatch.call_args_list}
        self.assertIn('Approve (Setujui) atau Reject (Tolak)', bodies['manager@test.com'])
        self.assertIn('Tidak diperlukan tindakan approval', bodies['admin@test.com'])
        self.assertNotIn('/approvals', bodies['admin@test.com'])

    def test_leave_notification_outbox_defers_smtp_and_worker_delivers_each_recipient(self):
        from services.notification_outbox_service import queue_notification, process_next_notification
        this_year = date.today().year
        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=date(this_year, 11, 5),
            end_date=date(this_year, 11, 5),
            duration_days=1.0,
            status='pending',
            current_approval_level=1,
            max_approval_level=1,
        )
        db.session.add(req)
        db.session.commit()
        self.company_a.notifications_enabled = True
        self.company_a.notify_on_submit = True
        db.session.commit()

        with patch('services.notification_service._dispatch_email') as dispatch:
            queued = queue_notification(self.company_a, 'submit', req)
        self.assertEqual(dispatch.call_count, 0)
        self.assertEqual(len(queued), 4)
        db.session.commit()

        with patch('services.notification_outbox_service._dispatch_email', return_value=True) as dispatch:
            while process_next_notification():
                pass
        self.assertEqual(dispatch.call_count, 4)
        self.assertEqual(NotificationOutbox.query.filter_by(status='sent').count(), 4)

    def test_admin_can_resend_leave_notification_to_current_approver_or_all_company_users(self):
        this_year = date.today().year
        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=date(this_year, 11, 6),
            end_date=date(this_year, 11, 6),
            duration_days=1.0,
            status='pending',
            current_approval_level=1,
            max_approval_level=1,
        )
        db.session.add(req)
        self.company_a.smtp_host = 'smtp.example.test'
        self.company_a.smtp_user = 'noreply@example.test'
        db.session.commit()

        self._login(self.admin_user)
        history = self.client.get('/approval-history')
        self.assertEqual(history.status_code, 200)
        self.assertIn(b'resendNotificationModal', history.data)
        self.assertIn(b'Notify all people', history.data)
        self.assertIn(b'Notify current approver', history.data)
        self.assertIn(b'btn-primary px-4 py-2.5 text-sm', history.data)
        self.assertIn(b'<i class="fa-solid fa-paper-plane"></i>Resend</button>', history.data)
        self.assertIn(b"replace('/0/', '/' + id + '/')", history.data)
        self.assertIn(b"approverOption.classList.toggle('hidden', status !== 'pending')", history.data)

        approver_resend = self.client.post(
            f'/approval-history/{req.id}/resend-notification',
            data={'recipient_scope': 'approver'},
            follow_redirects=True,
        )
        self.assertEqual(approver_resend.status_code, 200)
        self.assertIn(b'id="resend-result-dialog"', approver_resend.data)
        self.assertIn(b'Email resend queued', approver_resend.data)
        approver_rows = NotificationOutbox.query.filter_by(leave_request_id=req.id).all()
        self.assertEqual(len(approver_rows), 1)
        self.assertEqual(approver_rows[0].event, 'submit')
        self.assertEqual(approver_rows[0].recipient_email, 'manager@test.com')

        all_resend = self.client.post(
            f'/approval-history/{req.id}/resend-notification',
            data={'recipient_scope': 'all'},
            follow_redirects=True,
        )
        self.assertEqual(all_resend.status_code, 200)
        recipients = [item.recipient_email for item in NotificationOutbox.query.filter_by(leave_request_id=req.id).all()]
        self.assertEqual(recipients.count('manager@test.com'), 2)
        self.assertIn('alice@test.com', recipients)
        self.assertIn('admin@test.com', recipients)
        self.assertIn('superadmin@test.com', recipients)
        self.assertNotIn('charlie@test.com', recipients)
        audit = AuditLog.query.filter_by(action='leave.notification_resent', target_id=req.id).order_by(AuditLog.id.desc()).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.details_dict['recipient_scope'], 'all')

        self._login(self.manager_user)
        denied = self.client.post(f'/approval-history/{req.id}/resend-notification', data={'recipient_scope': 'approver'})
        self.assertEqual(denied.status_code, 302)

    def test_notification_outbox_retries_failed_delivery(self):
        from services.notification_outbox_service import process_next_notification
        item = NotificationOutbox(
            company_id=self.company_a.id,
            leave_request_id=1,
            event='submit',
            recipient_email='alice@test.com',
            subject='Test',
            body='Test message',
        )
        db.session.add(item)
        db.session.commit()

        with patch('services.notification_outbox_service._dispatch_email', return_value=False):
            self.assertTrue(process_next_notification())
        db.session.refresh(item)
        self.assertEqual(item.status, 'retry')
        self.assertEqual(item.attempts, 1)
        self.assertGreater(item.available_at, item.created_at)

    def test_approve_leave_notification_dispatches_to_same_company_users(self):
        """Approval notifications inform requester and other active users in the same company."""
        from services.notification_service import send_notification
        this_year = date.today().year
        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=date(this_year, 11, 3),
            end_date=date(this_year, 11, 4),
            duration_days=2.0,
            status='approved',
            current_approval_level=1,
            max_approval_level=1,
            approved_by=self.manager_user.id,
            approved_at=utcnow()
        )
        db.session.add(req)
        db.session.commit()

        self.company_a.notifications_enabled = True
        self.company_a.notify_on_approve = True
        db.session.commit()

        with patch('services.notification_service._dispatch_email', return_value=True) as dispatch:
            send_notification(self.company_a, 'approve', req)

        recipients = [call.args[1] for call in dispatch.call_args_list]
        self.assertIn('alice@test.com', recipients)
        self.assertIn('manager@test.com', recipients)
        self.assertIn('admin@test.com', recipients)
        self.assertIn('superadmin@test.com', recipients)
        self.assertNotIn('charlie@test.com', recipients)
        self.assertEqual(len(recipients), len(set(recipients)))

    def test_employee_can_apply_backdated_leave(self):
        """Employees can submit leave requests for past dates."""
        self._login(self.employee_user)
        start_d = date.today() - timedelta(days=14)
        end_d = date.today() - timedelta(days=10)

        res = self.client.post('/apply', data={
            'leave_type': self.lt_annual_a.id,
            'day_part': 'full',
            'start_date': start_d.isoformat(),
            'end_date': end_d.isoformat(),
            'reason': 'Backdated leave entry',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)

        req = LeaveRequest.query.filter_by(
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=start_d,
            end_date=end_d,
        ).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, 'pending')

    def test_cancel_pending_leave_request(self):
        """Test employee self-service cancellation of pending leave request."""
        this_year = date.today().year
        bal = LeaveBalance.query.filter_by(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            year=this_year
        ).first()
        bal.pending_days = 2.0
        db.session.commit()

        req = LeaveRequest(
            company_id=self.company_a.id,
            employee_id=self.employee_user.id,
            leave_type_id=self.lt_annual_a.id,
            start_date=date(this_year, 11, 10),
            end_date=date(this_year, 11, 11),
            duration_days=2.0,
            status='pending',
            current_approval_level=1,
            max_approval_level=1
        )
        db.session.add(req)
        db.session.commit()

        self._login(self.employee_user)

        # Cancel request
        res = self.client.post(f'/leaves/{req.id}/cancel', data={
            'reason': 'Salah tanggal',
            '_csrf_token': 'test-token'
        })
        self.assertEqual(res.status_code, 302)

        db.session.refresh(req)
        db.session.refresh(bal)
        self.assertEqual(req.status, 'cancelled')
        self.assertIn('Salah tanggal', req.notes)
        self.assertEqual(bal.pending_days, 0.0)

        # Cannot cancel again
        res2 = self.client.post(f'/leaves/{req.id}/cancel', data={'_csrf_token': 'test-token'})
        self.assertEqual(res2.status_code, 302)

    def test_working_days_calculation_excludes_weekends_and_holidays(self):
        """Test calculate_working_duration properly excludes weekends and public holidays."""
        from services.leave_service import calculate_working_duration
        from models.holiday import PublicHoliday

        # Friday (2026-10-02) to Monday (2026-10-05) -> Fri, Sat, Sun, Mon = 2 working days
        fri = date(2026, 10, 2)
        mon = date(2026, 10, 5)
        dur1 = calculate_working_duration(fri, mon, company_id=self.company_a.id)
        self.assertEqual(dur1, 2.0)

        # Half day morning
        dur_half = calculate_working_duration(fri, mon, company_id=self.company_a.id, day_part='morning')
        self.assertEqual(dur_half, 0.5)

        # Add holiday on Friday Oct 2
        hol = PublicHoliday(
            company_id=self.company_a.id,
            name='Hari Libur Khusus',
            holiday_date=fri,
            is_active=True
        )
        db.session.add(hol)
        db.session.commit()

        dur2 = calculate_working_duration(fri, mon, company_id=self.company_a.id)
        self.assertEqual(dur2, 1.0)

if __name__ == '__main__':
    unittest.main()
