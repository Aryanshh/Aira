from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "Asia/Kolkata"


def utc_now() -> datetime:
    """Return the current time in UTC with timezone awareness."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_elder_local_dt(dt: datetime, tz_name: str = DEFAULT_TIMEZONE) -> datetime:
    """Convert a UTC datetime to elder local datetime."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return dt.astimezone(tz)


def elder_today(tz_name: str = DEFAULT_TIMEZONE) -> date:
    """Get today's calendar date in the elder's timezone."""
    return to_elder_local_dt(utc_now(), tz_name).date()


def parse_time_slot(t: time) -> str:
    """Map a time to one of the 4 agreed slots:
    Morning (05:00-11:59)
    Afternoon (12:00-16:59)
    Evening (17:00-20:59)
    Night (21:00-04:59)
    """
    hour = t.hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"
