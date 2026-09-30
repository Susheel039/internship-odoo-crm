"""19.0.2.1.0: programme workflow rules get their documented defaults.

Programmes created by the 19.0.2.0.0 upgrade have 0 ("inherit") in every rule column. Fill
only those zeros with the default; values that were set explicitly are left alone.
"""

import logging

_logger = logging.getLogger(__name__)

DEFAULTS = {
    "form_due_days": 7,
    "monthly_due_day": 5,
    "monthly_late_grace_days": 3,
    "report_deadline_days": 14,
    "resubmission_days": 14,
    "max_report_attempts": 2,
    "tripartite_attendance_pct": 80.0,
    "tripartite_rating_threshold": 2,
    "expiry_alert_days": 30,
    "retention_years": 6,
}


def migrate(cr, version):
    if not version:
        return
    for column, default in DEFAULTS.items():
        cr.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = 'internship_program' AND column_name = %s",
            (column,),
        )
        if not cr.fetchone():
            continue
        cr.execute(
            f"UPDATE internship_program SET {column} = %s WHERE {column} IS NULL OR {column} = 0",  # noqa: S608
            (default,),
        )
        _logger.info("internship_base 19.0.2.1.0: %s defaulted on %s programmes", column, cr.rowcount)
