"""19.0.2.1.0: spec names for Vapi data.

- internship.vapi.event.payload_hash -> hash (old column kept, field deprecated)
- the four calling-window parameters -> one `internship_vapi.calling_window` value
Idempotent: only empty values are filled; old parameters are left in place.
"""

import logging

_logger = logging.getLogger(__name__)

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _column_exists(cr, table, column):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s", (table, column))
    return bool(cr.fetchone())


def _param(cr, key):
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (key,))
    row = cr.fetchone()
    return row[0] if row else None


def _hhmm(value):
    hours = float(value)
    return f"{int(hours):02d}:{round((hours % 1) * 60):02d}"


def migrate(cr, version):
    if not version:
        return
    if _column_exists(cr, "internship_vapi_event", "payload_hash") and _column_exists(
        cr, "internship_vapi_event", "hash"
    ):
        cr.execute(
            "UPDATE internship_vapi_event SET hash = payload_hash WHERE hash IS NULL AND payload_hash IS NOT NULL"
        )
        _logger.info("internship_vapi 19.0.2.1.0: hash filled on %s webhook events", cr.rowcount)

    if _param(cr, "internship_vapi.calling_window"):
        return
    start, end = _param(cr, "internship_vapi.window_start"), _param(cr, "internship_vapi.window_end")
    days, timezone = _param(cr, "internship_vapi.window_days"), _param(cr, "internship_vapi.timezone")
    if not any((start, end, days, timezone)):
        return
    try:
        day_numbers = sorted({int(d) for d in (days or "0,1,2,3,4").split(",") if d.strip().isdigit()})
        if day_numbers == list(range(day_numbers[0], day_numbers[-1] + 1)):
            day_text = f"{DAY_NAMES[day_numbers[0]]}-{DAY_NAMES[day_numbers[-1]]}"
        else:
            day_text = ",".join(DAY_NAMES[d] for d in day_numbers)
        window = f"{day_text} {_hhmm(start or 9)}-{_hhmm(end or 20)} {timezone or 'Europe/London'}"
    except (ValueError, IndexError):
        window = "Mon-Fri 09:00-20:00 Europe/London"
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES ('internship_vapi.calling_window', %s, 1, 1, now(), now())
        """,
        (window,),
    )
    _logger.info("internship_vapi 19.0.2.1.0: calling window set to %r", window)
