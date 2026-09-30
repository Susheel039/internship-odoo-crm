from odoo import api, models


class CrmStage(models.Model):
    _inherit = "crm.stage"

    @api.model
    def _internship_remove_unused_default_stages(self):
        """The internship pipeline is New, Contacted, Qualified, Interview, Won, Lost.

        Remove Odoo's default "Proposition" stage when no lead uses it (it is never recreated:
        the CRM data record is forcecreate=False).
        """
        proposition = self.env.ref("crm.stage_lead3", raise_if_not_found=False)
        if proposition and not self.env["crm.lead"].with_context(active_test=False).search_count(
            [("stage_id", "=", proposition.id)], limit=1
        ):
            proposition.unlink()
        return True
