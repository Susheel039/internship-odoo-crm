"""v2 step 3: link pre-v2 submissions and completion records to placements.

Idempotent: only rows with an empty placement_id are touched; unmatched rows stay unlinked.
A placement has at most one completion checklist, so when several v1 completion records
match the same placement only the newest is linked (the others keep their data, unlinked).
"""

import logging

from odoo.addons.internship_placement.upgrade_helpers import column_exists, link_to_placements

_logger = logging.getLogger(__name__)


def link_completions(cr):
    if not column_exists(cr, "internship_completion", "placement_id"):
        return 0
    cr.execute(
        """
        UPDATE internship_completion c
           SET placement_id = m.placement_id
          FROM (
                SELECT DISTINCT ON (p.id) p.id AS placement_id, r.id AS row_id
                  FROM internship_completion r
                  JOIN internship_placement p
                    ON p.student_id = r.student_id
                   AND (r.opportunity_id IS NULL OR p.opportunity_id IS NULL OR p.opportunity_id = r.opportunity_id)
                 WHERE r.placement_id IS NULL
                   AND NOT EXISTS (SELECT 1 FROM internship_completion x WHERE x.placement_id = p.id)
              ORDER BY p.id, r.id DESC
               ) m
         WHERE c.id = m.row_id
        """
    )
    _logger.info("v2 migration: internship_completion: linked %s rows to placements", cr.rowcount)
    return cr.rowcount


def migrate(cr, version):
    if not version:
        return
    link_to_placements(cr, "internship_submission")
    link_completions(cr)
