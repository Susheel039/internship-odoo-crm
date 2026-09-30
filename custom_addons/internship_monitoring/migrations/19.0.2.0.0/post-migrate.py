"""v2 step 3: link pre-v2 attendance, performance and meeting rows to placements.

Match on student (and opportunity when the row has one), taking the student's most recent
placement. Rows without a match keep placement_id empty (it is optional on these models).
Idempotent: only rows with an empty placement_id are touched.
"""

from odoo.addons.internship_monitoring.upgrade_helpers import TABLES, column_exists, link_to_placements


def migrate(cr, version):
    if not version:
        return
    for table in TABLES:
        link_to_placements(cr, table)
    # Meetings from v1 happened already: mark past ones completed instead of "scheduled".
    if column_exists(cr, "internship_meeting", "state"):
        cr.execute(
            "UPDATE internship_meeting SET state = 'completed' WHERE meeting_date < now() AND state = 'scheduled'"
        )
