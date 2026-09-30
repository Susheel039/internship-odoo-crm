"""v2 step 4: copy internship.crm.lead rows into crm.lead (idempotent). The legacy table is kept."""

from odoo import SUPERUSER_ID, api

from odoo.addons.internship_crm.upgrade_helpers import migrate_legacy_leads


def migrate(cr, version):
    if not version:
        return
    migrate_legacy_leads(api.Environment(cr, SUPERUSER_ID, {}))
