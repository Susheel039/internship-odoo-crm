"""v2: the application lifecycle past acceptance moves to internship.placement.

Rows in status documentation / agreement / approved / placed are recorded in the temp
table _v2_app_lifecycle (read by internship_placement's migration, which creates the
placements) and set to "accepted", because those selection keys no longer exist.

Idempotent: safe to run twice; never drops anything.
"""

import logging

_logger = logging.getLogger(__name__)

LEGACY_STATUSES = ("documentation", "agreement", "approved", "placed")


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version or not _table_exists(cr, "internship_application"):
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS _v2_app_lifecycle (
            application_id integer PRIMARY KEY,
            old_status varchar NOT NULL
        )
        """
    )
    cr.execute(
        """
        INSERT INTO _v2_app_lifecycle (application_id, old_status)
             SELECT id, status FROM internship_application WHERE status IN %s
        ON CONFLICT (application_id) DO NOTHING
        """,
        (LEGACY_STATUSES,),
    )
    recorded = cr.rowcount
    cr.execute("UPDATE internship_application SET status = 'accepted' WHERE status IN %s", (LEGACY_STATUSES,))
    _logger.info(
        "internship_base 19.0.2.0.0: recorded %s legacy lifecycle applications, moved %s to 'accepted'",
        recorded,
        cr.rowcount,
    )
