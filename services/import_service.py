import io
import csv
import re
from datetime import datetime, date, timedelta
from openpyxl import load_workbook, Workbook
from extensions import db
from models.user import User, Department
from models.leave import LeaveRequest, LeaveType, LeaveBalance
from models.audit import AuditLog
from services.audit_service import audit_log

# Helper: parse various date representations into python date object
def parse_flexible_date(val):
    if val is None or val == '':
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, (int, float)):
        # Excel date serial (origin 1899-12-30)
        try:
            excel_epoch = datetime(1899, 12, 30)
            return (excel_epoch + timedelta(days=float(val))).date()
        except Exception:
            pass

    s = str(val).strip()
    # Try ISO YYYY-MM-DD
    for fmt in [
        '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y',
        '%Y/%m/%d', '%d.%m.%Y', '%Y.%m.%d',
        '%d %b %Y', '%d %B %Y', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S'
    ]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    # Regex search for d/m/y or y-m-d
    match = re.search(r'(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})', s)
    if match:
        p1, p2, p3 = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if p1 > 1000: # Y-M-D
            try:
                return date(p1, p2, p3)
            except ValueError:
                pass
        elif p3 > 1000: # D-M-Y or M-D-Y
            try:
                return date(p3, p2, p1)
            except ValueError:
                try:
                    return date(p3, p1, p2)
                except ValueError:
                    pass

    return None

def parse_file_headers_and_preview(file_stream, filename):
    """
    Parses headers and first 10 rows of data from an Excel or CSV file.
    Returns: { 'headers': [...], 'rows': [[...], ...], 'total_rows': N }
    """
    filename_lower = filename.lower()
    headers = []
    rows = []

    if filename_lower.endswith(('.xlsx', '.xlsm', '.xltx', '.xltm')):
        wb = load_workbook(file_stream, read_only=True, data_only=True)
        ws = wb.active
        all_data = []
        for row in ws.iter_rows(values_only=True):
            # clean row
            cleaned = [str(c).strip() if c is not None else '' for c in row]
            if any(cleaned):
                all_data.append(cleaned)
        wb.close()

        if not all_data:
            raise ValueError('File Excel kosong atau tidak memiliki data.')

        headers = all_data[0]
        # remove trailing empty headers
        while headers and not headers[-1]:
            headers.pop()

        data_rows = all_data[1:]
        # Pad or slice each row to match header length
        for r in data_rows:
            padded = (r + [''] * len(headers))[:len(headers)]
            rows.append(padded)

    elif filename_lower.endswith('.csv') or filename_lower.endswith('.txt'):
        content = file_stream.read()
        if isinstance(content, bytes):
            # Try utf-8-sig, utf-8, latin1
            for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
                try:
                    decoded = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                decoded = content.decode('utf-8', errors='ignore')
        else:
            decoded = str(content)

        # Sniff delimiter (, or ; or \t)
        sample = decoded[:4096]
        delimiter = ','
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|'])
            delimiter = dialect.delimiter
        except Exception:
            if sample.count(';') > sample.count(','):
                delimiter = ';'
            elif sample.count('\t') > sample.count(','):
                delimiter = '\t'

        reader = csv.reader(io.StringIO(decoded), delimiter=delimiter)
        all_data = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]

        if not all_data:
            raise ValueError('File CSV kosong atau tidak memiliki data.')

        headers = all_data[0]
        data_rows = all_data[1:]
        for r in data_rows:
            padded = (r + [''] * len(headers))[:len(headers)]
            rows.append(padded)
    else:
        raise ValueError('Format file tidak didukung. Harap unggah file .xlsx atau .csv.')

    try:
        file_stream.seek(0)
    except Exception:
        pass

    # Smart Auto-Guess dictionary
    leave_history_guesses = guess_leave_history_mapping(headers)
    employee_guesses = guess_employee_mapping(headers)

    return {
        'headers': headers,
        'preview_rows': rows[:10],
        'total_rows': len(rows),
        'leave_history_guesses': leave_history_guesses,
        'employee_guesses': employee_guesses
    }

def guess_leave_history_mapping(headers):
    """
    Guesses mapping for leave history fields based on header strings.
    """
    mapping = {
        'employee': None,
        'leave_type': None,
        'start_date': None,
        'end_date': None,
        'duration': None,
        'day_part': None,
        'status': None,
        'reason': None,
        'approver': None
    }

    lower_headers = [h.lower().replace('_', ' ').replace('-', ' ').strip() for h in headers]

    for idx, h in enumerate(lower_headers):
        raw_header = headers[idx]
        if not mapping['employee'] and any(k in h for k in ['email', 'karyawan', 'employee', 'nama', 'user', 'name', 'pegawai', 'staff']):
            mapping['employee'] = raw_header
        elif not mapping['leave_type'] and any(k in h for k in ['jenis cuti', 'leave type', 'tipe cuti', 'kategori', 'type', 'jenis', 'alasan cuti']):
            mapping['leave_type'] = raw_header
        elif not mapping['start_date'] and any(k in h for k in ['mulai', 'start', 'from', 'tgl mulai', 'tanggal mulai', 'start date', 'tgl awal']):
            mapping['start_date'] = raw_header
        elif not mapping['end_date'] and any(k in h for k in ['selesai', 'end', 'to', 'sampai', 'tgl selesai', 'tanggal selesai', 'end date', 'tgl akhir']):
            mapping['end_date'] = raw_header
        elif not mapping['duration'] and any(k in h for k in ['durasi', 'duration', 'hari', 'days', 'total hari', 'jumlah hari', 'lama']):
            mapping['duration'] = raw_header
        elif not mapping['day_part'] and any(k in h for k in ['setengah', 'half', 'part', 'tipe waktu', 'waktu']):
            mapping['day_part'] = raw_header
        elif not mapping['status'] and any(k in h for k in ['status', 'state', 'persetujuan', 'approval status']):
            mapping['status'] = raw_header
        elif not mapping['reason'] and any(k in h for k in ['alasan', 'reason', 'keterangan', 'notes', 'catatan', 'keperluan', 'deskripsi']):
            mapping['reason'] = raw_header
        elif not mapping['approver'] and any(k in h for k in ['approver', 'disetujui oleh', 'approved by', 'atasan', 'manager']):
            mapping['approver'] = raw_header

    return mapping

def guess_employee_mapping(headers):
    """
    Guesses mapping for employee master fields based on header strings.
    """
    mapping = {
        'name': None,
        'email': None,
        'role': None,
        'department': None,
        'manager': None,
        'password': None
    }

    lower_headers = [h.lower().replace('_', ' ').replace('-', ' ').strip() for h in headers]

    for idx, h in enumerate(lower_headers):
        raw_header = headers[idx]
        if not mapping['name'] and any(k in h for k in ['nama lengkap', 'full name', 'nama', 'employee name', 'name']):
            mapping['name'] = raw_header
        elif not mapping['email'] and any(k in h for k in ['email', 'surel', 'work email', 'alamat email', 'e-mail']):
            mapping['email'] = raw_header
        elif not mapping['role'] and any(k in h for k in ['role', 'jabatan', 'peran', 'posisi', 'level']):
            mapping['role'] = raw_header
        elif not mapping['department'] and any(k in h for k in ['departemen', 'department', 'divisi', 'unit', 'bagian', 'dept']):
            mapping['department'] = raw_header
        elif not mapping['manager'] and any(k in h for k in ['manager', 'atasan', 'supervisor', 'leader', 'email manager']):
            mapping['manager'] = raw_header
        elif not mapping['password'] and any(k in h for k in ['password', 'kata sandi', 'pass']):
            mapping['password'] = raw_header

    return mapping

def execute_leave_history_import(file_stream, filename, mapping, company_id, current_user_id, sync_balances=True):
    """
    Executes leave history import mapping.
    """
    parsed = parse_file_headers_and_preview(file_stream, filename)
    headers = parsed['headers']
    
    # Reload file stream to parse all rows
    file_stream.seek(0)
    filename_lower = filename.lower()
    all_rows = []

    if filename_lower.endswith(('.xlsx', '.xlsm', '.xltx', '.xltm')):
        wb = load_workbook(file_stream, data_only=True)
        ws = wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if len(raw_rows) > 1:
            for r in raw_rows[1:]:
                cleaned = [c if c is not None else '' for c in r]
                if any(str(c).strip() for c in cleaned):
                    padded = (cleaned + [''] * len(headers))[:len(headers)]
                    all_rows.append(padded)
    else:
        content = file_stream.read()
        if isinstance(content, bytes):
            for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
                try:
                    decoded = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                decoded = content.decode('utf-8', errors='ignore')
        else:
            decoded = str(content)
        sample = decoded[:4096]
        delimiter = ','
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|'])
            delimiter = dialect.delimiter
        except Exception:
            if sample.count(';') > sample.count(','):
                delimiter = ';'
        reader = csv.reader(io.StringIO(decoded), delimiter=delimiter)
        raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if len(raw_rows) > 1:
            for r in raw_rows[1:]:
                padded = (r + [''] * len(headers))[:len(headers)]
                all_rows.append(padded)

    # Pre-cache existing users & leave types for speed & isolation
    users_by_email = {u.email.lower(): u for u in User.query.filter_by(company_id=company_id).all()}
    users_by_name = {u.name.lower().strip(): u for u in User.query.filter_by(company_id=company_id).all()}
    leave_types_by_name = {lt.name.lower().strip(): lt for lt in LeaveType.query.filter_by(company_id=company_id).all()}

    # Header indexes
    header_idx_map = {h: i for i, h in enumerate(headers)}

    def get_val(row, field_key):
        h_name = mapping.get(field_key)
        if h_name and h_name in header_idx_map:
            idx = header_idx_map[h_name]
            if idx < len(row):
                return row[idx]
        return None

    created_count = 0
    skipped_count = 0
    errors = []

    this_year = date.today().year

    for row_num, row in enumerate(all_rows, start=2):
        emp_val = str(get_val(row, 'employee') or '').strip()
        lt_val = str(get_val(row, 'leave_type') or '').strip()
        start_val = get_val(row, 'start_date')
        end_val = get_val(row, 'end_date')
        duration_val = get_val(row, 'duration')
        day_part_val = str(get_val(row, 'day_part') or 'full').strip().lower()
        status_val = str(get_val(row, 'status') or 'approved').strip().lower()
        reason_val = str(get_val(row, 'reason') or 'Imported history').strip()
        approver_val = str(get_val(row, 'approver') or '').strip()

        if not emp_val or not start_val:
            skipped_count += 1
            continue

        # Match employee
        user = users_by_email.get(emp_val.lower())
        if not user:
            user = users_by_name.get(emp_val.lower())
        
        if not user:
            errors.append(f'Baris {row_num}: Karyawan "{emp_val}" tidak ditemukan di sistem.')
            continue

        # Match or create Leave Type
        if not lt_val:
            lt_val = 'Cuti Tahunan'
        
        leave_type = leave_types_by_name.get(lt_val.lower())
        if not leave_type:
            # Auto create leave type
            leave_type = LeaveType(
                company_id=company_id,
                name=lt_val,
                days_per_year=12 if 'tahunan' in lt_val.lower() or 'annual' in lt_val.lower() else 0,
                color='#0d9488',
                icon='fa-calendar-alt',
                requires_approval=True,
                is_active=True
            )
            db.session.add(leave_type)
            db.session.flush()
            leave_types_by_name[lt_val.lower()] = leave_type

        # Parse dates
        start_date = parse_flexible_date(start_val)
        end_date = parse_flexible_date(end_val) if end_val else start_date
        if not end_date:
            end_date = start_date

        if not start_date:
            errors.append(f'Baris {row_num}: Tanggal mulai "{start_val}" tidak valid.')
            continue

        if end_date < start_date:
            end_date = start_date

        # Duration
        try:
            if duration_val is not None and str(duration_val).strip() != '':
                duration_days = float(str(duration_val).replace(',', '.'))
            else:
                # Calculate working days between start_date and end_date
                cur = start_date
                days = 0
                while cur <= end_date:
                    if cur.weekday() < 5: # Mon-Fri
                        days += 1
                    cur += timedelta(days=1)
                duration_days = max(1.0, float(days)) if days > 0 else 1.0
        except ValueError:
            duration_days = 1.0

        # Day part normalization
        if 'pagi' in day_part_val or 'morning' in day_part_val or 'am' in day_part_val:
            day_part = 'morning'
            duration_days = 0.5
        elif 'siang' in day_part_val or 'sore' in day_part_val or 'afternoon' in day_part_val or 'pm' in day_part_val:
            day_part = 'afternoon'
            duration_days = 0.5
        else:
            day_part = 'full'

        # Status normalization
        if any(s in status_val for s in ['setuju', 'approve', 'acc', 'disetujui', 'done', 'taken']):
            norm_status = 'approved'
        elif any(s in status_val for s in ['tolak', 'reject', 'ditolak']):
            norm_status = 'rejected'
        elif any(s in status_val for s in ['tunggu', 'pending', 'menunggu', 'draft']):
            norm_status = 'pending'
        else:
            norm_status = 'approved'

        # Match approver
        approver = None
        if approver_val:
            approver = users_by_email.get(approver_val.lower()) or users_by_name.get(approver_val.lower())
        if not approver and user.manager:
            approver = user.manager

        leave_req = LeaveRequest(
            company_id=company_id,
            employee_id=user.id,
            leave_type_id=leave_type.id,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            day_part=day_part,
            status=norm_status,
            reason=reason_val,
            approved_by=approver.id if approver and norm_status == 'approved' else (current_user_id if norm_status == 'approved' else None),
            approved_at=datetime.combine(start_date, datetime.min.time()) if norm_status == 'approved' else None,
            is_archived=False
        )
        db.session.add(leave_req)
        created_count += 1

        # Optionally sync current year leave balance
        if sync_balances and norm_status == 'approved' and start_date.year == this_year:
            bal = LeaveBalance.query.filter_by(
                company_id=company_id,
                employee_id=user.id,
                leave_type_id=leave_type.id,
                year=this_year
            ).first()
            if not bal:
                bal = LeaveBalance(
                    company_id=company_id,
                    employee_id=user.id,
                    leave_type_id=leave_type.id,
                    year=this_year,
                    total_days=leave_type.days_per_year,
                    used_days=duration_days
                )
                db.session.add(bal)
            else:
                bal.used_days += duration_days

    db.session.commit()

    audit_log(
        action='import.history_completed',
        target_type='leave_request',
        target_id=None,
        details={
            'created': created_count,
            'errors_count': len(errors),
            'filename': filename
        },
        company_id=company_id,
        actor_id=current_user_id
    )

    return {
        'success': True,
        'created': created_count,
        'skipped': skipped_count,
        'errors': errors
    }

def execute_employee_import(file_stream, filename, mapping, company_id, current_user_id, update_existing=True):
    """
    Executes employee master data import mapping.
    """
    parsed = parse_file_headers_and_preview(file_stream, filename)
    headers = parsed['headers']
    
    file_stream.seek(0)
    filename_lower = filename.lower()
    all_rows = []

    if filename_lower.endswith(('.xlsx', '.xlsm', '.xltx', '.xltm')):
        wb = load_workbook(file_stream, data_only=True)
        ws = wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if len(raw_rows) > 1:
            for r in raw_rows[1:]:
                cleaned = [c if c is not None else '' for c in r]
                if any(str(c).strip() for c in cleaned):
                    padded = (cleaned + [''] * len(headers))[:len(headers)]
                    all_rows.append(padded)
    else:
        content = file_stream.read()
        if isinstance(content, bytes):
            for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
                try:
                    decoded = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                decoded = content.decode('utf-8', errors='ignore')
        else:
            decoded = str(content)
        sample = decoded[:4096]
        delimiter = ','
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|'])
            delimiter = dialect.delimiter
        except Exception:
            if sample.count(';') > sample.count(','):
                delimiter = ';'
        reader = csv.reader(io.StringIO(decoded), delimiter=delimiter)
        raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if len(raw_rows) > 1:
            for r in raw_rows[1:]:
                padded = (r + [''] * len(headers))[:len(headers)]
                all_rows.append(padded)

    header_idx_map = {h: i for i, h in enumerate(headers)}

    def get_val(row, field_key):
        h_name = mapping.get(field_key)
        if h_name and h_name in header_idx_map:
            idx = header_idx_map[h_name]
            if idx < len(row):
                return row[idx]
        return None

    departments_by_name = {d.name.lower().strip(): d for d in Department.query.filter_by(company_id=company_id).all()}
    existing_users = {u.email.lower().strip(): u for u in User.query.filter_by(company_id=company_id).all()}
    
    created_count = 0
    updated_count = 0
    errors = []
    manager_relationships_to_set = [] # (user, manager_raw_str)

    this_year = date.today().year
    leave_types = LeaveType.query.filter_by(company_id=company_id, is_active=True).all()

    for row_num, row in enumerate(all_rows, start=2):
        name = str(get_val(row, 'name') or '').strip()
        email = str(get_val(row, 'email') or '').strip()
        role_raw = str(get_val(row, 'role') or 'employee').strip().lower()
        dept_raw = str(get_val(row, 'department') or '').strip()
        manager_raw = str(get_val(row, 'manager') or '').strip()
        pass_raw = str(get_val(row, 'password') or '').strip()

        if not name or not email:
            continue

        # Basic email validate
        if '@' not in email or '.' not in email:
            errors.append(f'Baris {row_num}: Format email "{email}" tidak valid.')
            continue

        # Role normalization
        if 'admin' in role_raw:
            role = 'admin'
        elif 'hr' in role_raw:
            role = 'hr'
        elif 'manager' in role_raw or 'atasan' in role_raw or 'lead' in role_raw or 'spv' in role_raw:
            role = 'manager'
        else:
            role = 'employee'

        # Department resolution
        dept_id = None
        if dept_raw:
            dept = departments_by_name.get(dept_raw.lower())
            if not dept:
                dept = Department(name=dept_raw, company_id=company_id)
                db.session.add(dept)
                db.session.flush()
                departments_by_name[dept_raw.lower()] = dept
            dept_id = dept.id

        user = existing_users.get(email.lower())
        if user:
            if update_existing:
                user.name = name
                user.role = role
                if dept_id:
                    user.department_id = dept_id
                if pass_raw:
                    user.set_password(pass_raw)
                updated_count += 1
                if manager_raw:
                    manager_relationships_to_set.append((user, manager_raw))
        else:
            new_user = User(
                company_id=company_id,
                name=name,
                email=email,
                role=role,
                department_id=dept_id
            )
            initial_password = pass_raw if pass_raw and len(pass_raw) >= 8 else 'Triont123!'
            new_user.set_password(initial_password)
            db.session.add(new_user)
            db.session.flush()
            existing_users[email.lower()] = new_user
            created_count += 1

            if manager_raw:
                manager_relationships_to_set.append((new_user, manager_raw))

            # Initialize leave balances
            for lt in leave_types:
                if lt.days_per_year > 0:
                    db.session.add(LeaveBalance(
                        company_id=company_id,
                        employee_id=new_user.id,
                        leave_type_id=lt.id,
                        year=this_year,
                        total_days=lt.days_per_year
                    ))

    # Second pass: link managers
    users_by_name = {u.name.lower().strip(): u for u in User.query.filter_by(company_id=company_id).all()}
    for target_user, mgr_str in manager_relationships_to_set:
        mgr = existing_users.get(mgr_str.lower()) or users_by_name.get(mgr_str.lower())
        if mgr and mgr.id != target_user.id:
            target_user.manager_id = mgr.id

    db.session.commit()

    audit_log(
        action='import.employees_completed',
        target_type='user',
        target_id=None,
        details={
            'created': created_count,
            'updated': updated_count,
            'filename': filename
        },
        company_id=company_id,
        actor_id=current_user_id
    )

    return {
        'success': True,
        'created': created_count,
        'updated': updated_count,
        'errors': errors
    }
