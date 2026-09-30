"""v2: fill the new application response fields for rows that were accepted before v2."""

import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version or not _column_exists(cr, "internship_application", "student_response"):
        return
    cr.execute(
        """
        UPDATE internship_application
           SET student_response = 'accepted', offer_made = TRUE
         WHERE status = 'accepted' AND (student_response IS NULL OR student_response = 'pending')
        """
    )
    _logger.info("internship_base 19.0.2.0.0: marked %s accepted applications as accepted by the student", cr.rowcount)
    cr.execute(
        """
        UPDATE internship_application
           SET student_response = 'pending'
         WHERE student_response IS NULL
        """
    )
