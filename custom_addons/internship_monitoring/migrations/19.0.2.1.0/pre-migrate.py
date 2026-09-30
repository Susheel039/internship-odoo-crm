"""19.0.2.1.0: monthly `working_as_required` changes from a yes/no selection to a Boolean.

Keep the old text values in `working_as_required_legacy` (renamed column, never dropped);
post-migrate fills the new Boolean from them. Idempotent: only runs while the column is text.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT data_type FROM information_schema.columns
         WHERE table_name = 'internship_attendance_monthly' AND column_name = 'working_as_required'
        """
    )
    row = cr.fetchone()
    if not row or row[0] == "boolean":
        return
    cr.execute(
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_name = 'internship_attendance_monthly' AND column_name = 'working_as_required_legacy'"
    )
    if cr.fetchone():
        return
    cr.execute(
        "ALTER TABLE internship_attendance_monthly RENAME COLUMN working_as_required TO working_as_required_legacy"
    )
    _logger.info("internship_monitoring 19.0.2.1.0: kept yes/no answers in working_as_required_legacy")
