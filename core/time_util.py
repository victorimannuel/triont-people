from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask_login import current_user

DEFAULT_TIMEZONE = 'Asia/Jakarta'

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


TIMEZONE_CHOICES = [
    ('Asia/Jakarta', 'WIB - Jakarta, Surabaya, Sumatera (UTC+7)'),
    ('Asia/Makassar', 'WITA - Bali, Balikpapan, Makassar (UTC+8)'),
    ('Asia/Jayapura', 'WIT - Papua, Maluku (UTC+9)'),
    ('Asia/Singapore', 'SGT / MYT - Singapore, Malaysia (UTC+8)'),
    ('Asia/Bangkok', 'ICT - Bangkok, Hanoi (UTC+7)'),
    ('Asia/Tokyo', 'JST - Tokyo, Osaka (UTC+9)'),
    ('Asia/Dubai', 'GST - Dubai, Abu Dhabi (UTC+4)'),
    ('Australia/Sydney', 'AEST / AEDT - Sydney, Melbourne (UTC+10/+11)'),
    ('Europe/London', 'GMT / BST - London (UTC+0/+1)'),
    ('Europe/Paris', 'CET / CEST - Paris, Berlin, Amsterdam (UTC+1/+2)'),
    ('America/New_York', 'EST / EDT - New York, Miami (UTC-5/-4)'),
    ('America/Chicago', 'CST / CDT - Chicago, Texas (UTC-6/-5)'),
    ('America/Los_Angeles', 'PST / PDT - San Francisco, Los Angeles (UTC-8/-7)'),
    ('UTC', 'UTC - Coordinated Universal Time (+0)'),
]

def get_current_user_timezone(user=None):
    if user and getattr(user, 'timezone_preference', None):
        return user.timezone_preference
    if current_user and getattr(current_user, 'is_authenticated', False):
        tz = getattr(current_user, 'timezone_preference', None)
        if tz:
            return tz
    return DEFAULT_TIMEZONE

def to_user_tz(dt, user=None, tz_name=None):
    if dt is None:
        return None
    if tz_name is None:
        tz_name = get_current_user_timezone(user=user)

    try:
        target_tz = ZoneInfo(tz_name)
    except Exception:
        target_tz = ZoneInfo(DEFAULT_TIMEZONE)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(target_tz)

def format_user_datetime(dt, fmt='%d/%m/%Y %H:%M', user=None, tz_name=None):
    if not dt:
        return '-'
    try:
        converted = to_user_tz(dt, user=user, tz_name=tz_name)
        return converted.strftime(fmt)
    except Exception:
        return str(dt)
