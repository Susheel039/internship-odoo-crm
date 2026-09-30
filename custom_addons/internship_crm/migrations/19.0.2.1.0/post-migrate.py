"""19.0.2.1.0: crm.lead.internship_opportunity_id -> opportunity_id (spec name); closed legacy leads -> Lost.

The old column is kept (field deprecated). Idempotent: only empty opportunity_id values are filled.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s", (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return
    if _column_exists(cr, "crm_lead", "internship_opportunity_id") and _column_exists(cr, "crm_lead", "opportunity_id"):
        cr.execute(
            "UPDATE crm_lead SET opportunity_id = internship_opportunity_id"
            " WHERE opportunity_id IS NULL AND internship_opportunity_id IS NOT NULL"
        )
        _logger.info("internship_crm 19.0.2.1.0: opportunity_id filled on %s leads", cr.rowcount)
    env = api.Environment(cr, SUPERUSER_ID, {})
    lost_stage = env.ref("internship_crm.stage_lost", raise_if_not_found=False)
    reason = env.ref("internship_crm.lost_reason_legacy_closed", raise_if_not_found=False)
    if lost_stage and reason:
        leads = (
            env["crm.lead"]
            .with_context(active_test=False)
            .search([("legacy_internship_lead_id", "!=", False), ("lost_reason_id", "=", reason.id)])
        )
        leads.write({"stage_id": lost_stage.id})
        _logger.info("internship_crm 19.0.2.1.0: %s closed legacy leads moved to Lost", len(leads))
