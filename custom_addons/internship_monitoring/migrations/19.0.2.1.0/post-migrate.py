"""19.0.2.1.0: fill the new Boolean `working_as_required` from the kept yes/no answers."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_name = 'internship_attendance_monthly' AND column_name = 'working_as_required_legacy'"
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE internship_attendance_monthly
           SET working_as_required = (working_as_required_legacy = 'yes')
         WHERE working_as_required_legacy IS NOT NULL
        """
    )
    _logger.info("internship_monitoring 19.0.2.1.0: working_as_required set on %s monthly records", cr.rowcount)
