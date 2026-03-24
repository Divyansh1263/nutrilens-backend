# utils/date_utils.py
from datetime import date, timedelta, datetime

def get_today_str():
    """Return YYYY-MM-DD string for today."""
    return str(date.today())

def get_date_str_with_offset(days_offset):
    """Return YYYY-MM-DD string with an offset (e.g., -1 for yesterday)."""
    return str(date.today() + timedelta(days=days_offset))

def get_days_difference(date_str1, date_str2):
    """Return absolute days difference between two YYYY-MM-DD strings."""
    try:
        d1 = datetime.strptime(date_str1, "%Y-%m-%d").date()
        d2 = datetime.strptime(date_str2, "%Y-%m-%d").date()
        return abs((d1 - d2).days)
    except ValueError:
        return 999
