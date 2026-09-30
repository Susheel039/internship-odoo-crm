"""Upgrade helpers shared by the v2 migrations of the modules that sit on top of placements."""

import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# Only these pre-v2 tables are ever linked; the table name is interpolated into SQL.
LINKABLE_TABLES = (
    "internship_attendance",
    "internship_performance",
    "internship_meeting",
    "internship_submission",
    "internship_completion",
)


def column_exists(cr, table, column):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s", (table, column))
    return bool(cr.fetchone())


def link_to_placements(cr, table):
    """Set placement_id on pre-v2 rows by matching student (and opportunity when present).

    Takes the student's placement for the same opportunity first, else their most recent one.
    Rows without a match keep an empty placement_id. Idempotent: only empty rows are touched.
    """
    if table not in LINKABLE_TABLES:
        raise ValueError(f"Refusing to link unknown table {table!r}")
    if not column_exists(cr, table, "placement_id") or not column_exists(cr, "internship_placement", "student_id"):
        return 0
    table_sql = SQL.identifier(table)
    cr.execute(
        SQL(
            """
            UPDATE %(table)s t
               SET placement_id = m.placement_id
              FROM (
                    SELECT DISTINCT ON (r.id) r.id AS row_id, p.id AS placement_id
                      FROM %(table)s r
                      JOIN internship_placement p
                        ON p.student_id = r.student_id
                       AND (r.opportunity_id IS NULL OR p.opportunity_id IS NULL OR p.opportunity_id = r.opportunity_id)
                     WHERE r.placement_id IS NULL
                  ORDER BY r.id, (p.opportunity_id = r.opportunity_id) DESC NULLS LAST, p.id DESC
                   ) m
             WHERE t.id = m.row_id
            """,
            table=table_sql,
        )
    )
    linked = cr.rowcount
    cr.execute(SQL("SELECT count(*) FROM %s WHERE placement_id IS NULL", table_sql))
    unmatched = cr.fetchone()[0]
    _logger.info("v2 migration: %s: linked %s rows to placements, %s without placement", table, linked, unmatched)
    return linked
