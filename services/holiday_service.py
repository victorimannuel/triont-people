from datetime import date, datetime, timedelta
from extensions import db
from models.holiday import PublicHoliday

INDONESIAN_HOLIDAYS_DATA = [
    # 2025
    ('2025-01-01', 'Tahun Baru 2025 Masehi', 'national'),
    ('2025-01-27', "Isra Mi'raj Nabi Muhammad SAW", 'national'),
    ('2025-01-28', 'Cuti Bersama Tahun Baru Imlek 2576', 'collective'),
    ('2025-01-29', 'Tahun Baru Imlek 2576 Kongzili', 'national'),
    ('2025-03-28', 'Cuti Bersama Hari Suci Nyepi', 'collective'),
    ('2025-03-29', 'Hari Suci Nyepi (Saka 1947)', 'national'),
    ('2025-03-31', 'Hari Raya Idul Fitri 1446 H', 'national'),
    ('2025-04-01', 'Hari Raya Idul Fitri 1446 H', 'national'),
    ('2025-04-02', 'Cuti Bersama Idul Fitri 1446 H', 'collective'),
    ('2025-04-03', 'Cuti Bersama Idul Fitri 1446 H', 'collective'),
    ('2025-04-04', 'Cuti Bersama Idul Fitri 1446 H', 'collective'),
    ('2025-04-07', 'Cuti Bersama Idul Fitri 1446 H', 'collective'),
    ('2025-04-18', 'Wafat Yesus Kristus (Jumat Agung)', 'national'),
    ('2025-04-20', 'Kebangkitan Yesus Kristus (Paskah)', 'national'),
    ('2025-05-01', 'Hari Buruh Internasional', 'national'),
    ('2025-05-12', 'Hari Raya Waisak 2569 BE', 'national'),
    ('2025-05-13', 'Cuti Bersama Hari Raya Waisak', 'collective'),
    ('2025-05-29', 'Kenaikan Yesus Kristus', 'national'),
    ('2025-05-30', 'Cuti Bersama Kenaikan Yesus Kristus', 'collective'),
    ('2025-06-01', 'Hari Lahir Pancasila', 'national'),
    ('2025-06-06', 'Hari Raya Idul Adha 1446 H', 'national'),
    ('2025-06-09', 'Cuti Bersama Idul Adha 1446 H', 'collective'),
    ('2025-06-27', '1 Muharam Tahun Baru Islam 1447 H', 'national'),
    ('2025-08-17', 'Proklamasi Kemerdekaan RI ke-80', 'national'),
    ('2025-09-05', 'Maulid Nabi Muhammad SAW', 'national'),
    ('2025-12-25', 'Kelahiran Yesus Kristus (Hari Raya Natal)', 'national'),
    ('2025-12-26', 'Cuti Bersama Hari Raya Natal', 'collective'),

    # 2026
    ('2026-01-01', 'Tahun Baru 2026 Masehi', 'national'),
    ('2026-01-16', "Isra Mi'raj Nabi Muhammad SAW", 'national'),
    ('2026-02-17', 'Tahun Baru Imlek 2577 Kongzili', 'national'),
    ('2026-02-18', 'Cuti Bersama Tahun Baru Imlek', 'collective'),
    ('2026-03-19', 'Hari Suci Nyepi (Saka 1948)', 'national'),
    ('2026-03-20', 'Cuti Bersama Hari Suci Nyepi', 'collective'),
    ('2026-03-20', 'Hari Raya Idul Fitri 1447 H', 'national'),
    ('2026-03-21', 'Hari Raya Idul Fitri 1447 H', 'national'),
    ('2026-03-23', 'Cuti Bersama Idul Fitri 1447 H', 'collective'),
    ('2026-03-24', 'Cuti Bersama Idul Fitri 1447 H', 'collective'),
    ('2026-04-03', 'Wafat Yesus Kristus', 'national'),
    ('2026-04-05', 'Kebangkitan Yesus Kristus (Paskah)', 'national'),
    ('2026-05-01', 'Hari Buruh Internasional', 'national'),
    ('2026-05-14', 'Kenaikan Yesus Kristus', 'national'),
    ('2026-05-15', 'Cuti Bersama Kenaikan Yesus Kristus', 'collective'),
    ('2026-05-27', 'Hari Raya Idul Adha 1447 H', 'national'),
    ('2026-05-31', 'Hari Raya Waisak 2570 BE', 'national'),
    ('2026-06-01', 'Hari Lahir Pancasila', 'national'),
    ('2026-06-16', '1 Muharam Tahun Baru Islam 1448 H', 'national'),
    ('2026-08-17', 'Hari Kemerdekaan RI ke-81', 'national'),
    ('2026-08-25', 'Maulid Nabi Muhammad SAW', 'national'),
    ('2026-12-25', 'Hari Raya Natal', 'national'),
    ('2026-12-26', 'Cuti Bersama Hari Raya Natal', 'collective'),

    # 2027
    ('2027-01-01', 'Tahun Baru 2027 Masehi', 'national'),
    ('2027-01-05', "Isra Mi'raj Nabi Muhammad SAW", 'national'),
    ('2027-02-06', 'Tahun Baru Imlek 2578 Kongzili', 'national'),
    ('2027-03-09', 'Hari Suci Nyepi (Saka 1949)', 'national'),
    ('2027-03-10', 'Hari Raya Idul Fitri 1448 H', 'national'),
    ('2027-03-11', 'Hari Raya Idul Fitri 1448 H', 'national'),
    ('2027-03-26', 'Wafat Yesus Kristus', 'national'),
    ('2027-05-01', 'Hari Buruh Internasional', 'national'),
    ('2027-05-06', 'Kenaikan Yesus Kristus', 'national'),
    ('2027-05-16', 'Hari Raya Idul Adha 1448 H', 'national'),
    ('2027-05-20', 'Hari Raya Waisak 2571 BE', 'national'),
    ('2027-06-01', 'Hari Lahir Pancasila', 'national'),
    ('2027-06-06', '1 Muharam Tahun Baru Islam 1449 H', 'national'),
    ('2027-08-15', 'Maulid Nabi Muhammad SAW', 'national'),
    ('2027-08-17', 'Hari Kemerdekaan RI ke-82', 'national'),
    ('2027-12-25', 'Hari Raya Natal', 'national'),

    # 2028 (Preliminary projections)
    ('2028-01-01', 'Tahun Baru 2028 Masehi', 'national'),
    ('2028-01-26', 'Tahun Baru Imlek 2579 Kongzili', 'national'),
    ('2028-02-27', 'Hari Raya Idul Fitri 1449 H', 'national'),
    ('2028-02-28', 'Hari Raya Idul Fitri 1449 H', 'national'),
    ('2028-03-26', 'Hari Suci Nyepi (Saka 1950)', 'national'),
    ('2028-04-14', 'Wafat Yesus Kristus', 'national'),
    ('2028-05-01', 'Hari Buruh Internasional', 'national'),
    ('2028-05-09', 'Hari Raya Waisak 2572 BE', 'national'),
    ('2028-05-25', 'Kenaikan Yesus Kristus', 'national'),
    ('2028-06-01', 'Hari Lahir Pancasila', 'national'),
    ('2028-08-17', 'Hari Kemerdekaan RI ke-83', 'national'),
    ('2028-12-25', 'Hari Raya Natal', 'national'),
]

def get_fixed_holidays_for_year(year):
    """Returns statutory fixed Indonesian annual national holidays."""
    ri_age = max(1, year - 1945)
    return [
        (f"{year}-01-01", f"Tahun Baru {year} Masehi", "national"),
        (f"{year}-05-01", "Hari Buruh Internasional", "national"),
        (f"{year}-06-01", "Hari Lahir Pancasila", "national"),
        (f"{year}-08-17", f"Hari Kemerdekaan RI ke-{ri_age}", "national"),
        (f"{year}-12-25", "Hari Raya Natal", "national"),
    ]

def fetch_holidays_from_api(year):
    """
    Fetches national holidays from public API (Nager.Date / DayoffAPI) for a given year.
    Returns a list of tuples: (date_str, name, kind)
    """
    import urllib.request
    import json

    results = []
    # Primary public API: Nager.Date v3 PublicHolidays for Indonesia
    nager_url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/ID"
    try:
        req = urllib.request.Request(nager_url, headers={'User-Agent': 'TritonPeople/1.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            for item in data:
                d_str = item.get('date')
                name = item.get('localName') or item.get('name')
                kind = 'collective' if 'cuti bersama' in name.lower() else 'national'
                results.append((d_str, name, kind))
            if results:
                return results
    except Exception:
        pass

    return results

def ensure_company_holidays(company_id, year=None):
    """Ensures holidays exist for company. If year is provided, ensures holidays for that year."""
    if not company_id:
        return
    try:
        if year:
            start_d = date(year, 1, 1)
            end_d = date(year, 12, 31)
            count = PublicHoliday.query.filter(
                PublicHoliday.company_id == company_id,
                PublicHoliday.holiday_date >= start_d,
                PublicHoliday.holiday_date <= end_d
            ).count()
            if count == 0:
                sync_company_holidays(company_id, year=year)
        else:
            existing_count = PublicHoliday.query.filter_by(company_id=company_id).count()
            if existing_count == 0:
                sync_company_holidays(company_id)
    except Exception:
        db.session.rollback()
        db.create_all()
        sync_company_holidays(company_id, year=year)

def sync_company_holidays(company_id, year=None):
    """
    Synchronizes company holidays using live API, curated dataset, and annual fixed holidays.
    Returns: (added_count, source_description)
    """
    if not company_id:
        return 0, "None"

    holidays_to_sync = {}  # {date_str: (name, kind)}
    source = "Dataset & API"

    if year:
        # 1. Fetch from live API for requested year
        api_data = fetch_holidays_from_api(year)
        if api_data:
            source = f"Live API ({len(api_data)} libur)"
            for d_str, name, kind in api_data:
                holidays_to_sync[d_str] = (name, kind)

        # 2. Merge matching dates from curated dataset
        for d_str, name, kind in INDONESIAN_HOLIDAYS_DATA:
            if d_str.startswith(f"{year}-") and d_str not in holidays_to_sync:
                holidays_to_sync[d_str] = (name, kind)

        # 3. Always ensure statutory fixed holidays for this year
        for d_str, name, kind in get_fixed_holidays_for_year(year):
            if d_str not in holidays_to_sync:
                holidays_to_sync[d_str] = (name, kind)
    else:
        # Full sync: entire dataset + current year API
        this_year = date.today().year
        for d_str, name, kind in INDONESIAN_HOLIDAYS_DATA:
            holidays_to_sync[d_str] = (name, kind)

        for y in (this_year - 1, this_year, this_year + 1):
            for d_str, name, kind in get_fixed_holidays_for_year(y):
                if d_str not in holidays_to_sync:
                    holidays_to_sync[d_str] = (name, kind)

    added_count = 0
    for d_str, (name, kind) in holidays_to_sync.items():
        try:
            h_date = datetime.strptime(d_str, '%Y-%m-%d').date()
        except ValueError:
            continue

        h = PublicHoliday.query.filter_by(company_id=company_id, holiday_date=h_date).first()
        if not h:
            db.session.add(PublicHoliday(
                company_id=company_id,
                holiday_date=h_date,
                name=name,
                kind=kind,
                is_active=True
            ))
            added_count += 1

    db.session.commit()
    return added_count, source

def calculate_long_weekends(company_id, year):
    ensure_company_holidays(company_id, year=year)
    holidays = PublicHoliday.query.filter_by(company_id=company_id, is_active=True).order_by(PublicHoliday.holiday_date).all()
    holidays_in_year = [h for h in holidays if h.holiday_date.year == year]
    holiday_map = {h.holiday_date: h for h in holidays_in_year}

    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)

    suggestions = []
    seen_ranges = set()

    # 1. Natural long weekends (3+ days off without extra leave)
    cur = start_date
    while cur <= end_date:
        if cur in holiday_map:
            left = cur
            while left > start_date and ((left - timedelta(days=1)).weekday() in (5, 6) or (left - timedelta(days=1)) in holiday_map):
                left -= timedelta(days=1)
            right = cur
            while right < end_date and ((right + timedelta(days=1)).weekday() in (5, 6) or (right + timedelta(days=1)) in holiday_map):
                right += timedelta(days=1)

            total_off = (right - left).days + 1
            if total_off >= 3:
                r_key = (left, right, 0)
                if r_key not in seen_ranges:
                    seen_ranges.add(r_key)
                    h_names = [holiday_map[d].name for d in holiday_map if left <= d <= right]
                    title = ' & '.join(dict.fromkeys(h_names)) or holiday_map[cur].name
                    suggestions.append({
                        'month_name': left.strftime('%B %Y'),
                        'title': title,
                        'leave_needed': 0,
                        'total_off': total_off,
                        'date_range': f"{left.strftime('%d %b')} - {right.strftime('%d %b %Y')}",
                        'strategy': 'Libur panjang otomatis tanpa perlu memotong kuota cuti tahunan! 🎉',
                        'start_date': left,
                        'end_date': right,
                        'is_past': right < date.today(),
                        'sort_date': left
                    })
        cur += timedelta(days=1)

    # 2. Bridge opportunities (Harpitnas):
    for h_date, h_obj in holiday_map.items():
        # Thursday holiday (weekday == 3) -> take Friday
        if h_date.weekday() == 3 and (h_date + timedelta(days=1)) not in holiday_map:
            left = h_date
            right = h_date + timedelta(days=3)
            r_key = (left, right, 1)
            if r_key not in seen_ranges:
                seen_ranges.add(r_key)
                fri_date = h_date + timedelta(days=1)
                suggestions.append({
                    'month_name': left.strftime('%B %Y'),
                    'title': f'{h_obj.name} (Harpitnas)',
                    'leave_needed': 1,
                    'total_off': 4,
                    'date_range': f"{left.strftime('%d %b')} - {right.strftime('%d %b %Y')}",
                    'strategy': f"Ambil 1 hari cuti di hari Jumat ({fri_date.strftime('%d %b')}) untuk menikmati 4 hari libur beruntun! 🔥",
                    'start_date': left,
                    'end_date': right,
                    'is_past': right < date.today(),
                    'sort_date': left
                })

        # Tuesday holiday (weekday == 1) -> take Monday
        if h_date.weekday() == 1 and (h_date - timedelta(days=1)) not in holiday_map:
            left = h_date - timedelta(days=3)
            right = h_date
            r_key = (left, right, 1)
            if r_key not in seen_ranges:
                seen_ranges.add(r_key)
                mon_date = h_date - timedelta(days=1)
                suggestions.append({
                    'month_name': left.strftime('%B %Y'),
                    'title': f'{h_obj.name} (Harpitnas)',
                    'leave_needed': 1,
                    'total_off': 4,
                    'date_range': f"{left.strftime('%d %b')} - {right.strftime('%d %b %Y')}",
                    'strategy': f"Ambil 1 hari cuti di hari Senin ({mon_date.strftime('%d %b')}) untuk menikmati 4 hari libur beruntun! 🔥",
                    'start_date': left,
                    'end_date': right,
                    'is_past': right < date.today(),
                    'sort_date': left
                })

        # Wednesday holiday (weekday == 2) -> bridge Thu-Fri
        if h_date.weekday() == 2:
            left = h_date
            right = h_date + timedelta(days=4)
            r_key = (left, right, 2)
            if r_key not in seen_ranges:
                seen_ranges.add(r_key)
                thu = h_date + timedelta(days=1)
                fri = h_date + timedelta(days=2)
                suggestions.append({
                    'month_name': left.strftime('%B %Y'),
                    'title': f'{h_obj.name} (Combo 5 Hari)',
                    'leave_needed': 2,
                    'total_off': 5,
                    'date_range': f"{left.strftime('%d %b')} - {right.strftime('%d %b %Y')}",
                    'strategy': f"Ambil 2 hari cuti ({thu.strftime('%d %b')} & {fri.strftime('%d %b')}) untuk menikmati libur 5 hari berurutan! 🏖️",
                    'start_date': left,
                    'end_date': right,
                    'is_past': right < date.today(),
                    'sort_date': left
                })

    today = date.today()
    for s in suggestions:
        s['is_past'] = bool(s['end_date'] < today)

    upcoming = [s for s in suggestions if not s['is_past']]
    past = [s for s in suggestions if s['is_past']]

    upcoming.sort(key=lambda x: x['sort_date'])
    past.sort(key=lambda x: x['sort_date'])

    suggestions = upcoming + past
    return suggestions, holidays_in_year
