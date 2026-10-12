import os
from datetime import datetime, timedelta, timezone

SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@leftovereat.local").lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")
SEED_DEMO = os.getenv("SEED_DEMO", "1") == "1"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
SESSION_MAX_AGE = 60 * 60 * 24 * 14

# Pickup windows are entered and shown in venue-local time (default IST, UTC+5:30).
TZ_OFFSET_MINUTES = int(os.getenv("TZ_OFFSET_MINUTES", "330"))


def now_local() -> datetime:
    """Naive datetime in venue-local time. All stored datetimes use this convention."""
    utc = datetime.now(timezone.utc).replace(tzinfo=None)
    return utc + timedelta(minutes=TZ_OFFSET_MINUTES)
