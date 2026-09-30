"""Parse the calling window setting, e.g. "Mon-Fri 09:00-20:00 Europe/London"."""

import re

import pytz

DEFAULT_WINDOW = "Mon-Fri 09:00-20:00 Europe/London"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PATTERN = re.compile(
    r"^\s*(?P<days>[A-Za-z]{3}(?:\s*-\s*[A-Za-z]{3})?(?:\s*,\s*[A-Za-z]{3}(?:\s*-\s*[A-Za-z]{3})?)*)\s+"
    r"(?P<start>\d{1,2}:\d{2})\s*-\s*(?P<end>\d{1,2}:\d{2})\s+(?P<tz>\S+)\s*$"
)


def _hours(value):
    hours, minutes = value.split(":")
    return int(hours) + int(minutes) / 60.0


def parse_calling_window(value):
    """Return {"days": {0..6}, "start": float, "end": float, "timezone": str}. Raises ValueError."""
    match = PATTERN.match(value or "")
    if not match:
        raise ValueError(f"Calling window must look like '{DEFAULT_WINDOW}'")
    days = set()
    for part in match["days"].lower().replace(" ", "").split(","):
        first, _, last = part.partition("-")
        if first not in DAYS or (last and last not in DAYS):
            raise ValueError(f"Unknown day in calling window: {part}")
        lo, hi = DAYS.index(first), DAYS.index(last or first)
        days.update(range(lo, hi + 1) if lo <= hi else [*range(lo, 7), *range(0, hi + 1)])
    start, end = _hours(match["start"]), _hours(match["end"])
    if not 0 <= start < end <= 24:
        raise ValueError("The calling window must start before it ends.")
    if match["tz"] not in pytz.all_timezones_set:
        raise ValueError(f"Unknown time zone: {match['tz']}")
    return {"days": days, "start": start, "end": end, "timezone": match["tz"]}
