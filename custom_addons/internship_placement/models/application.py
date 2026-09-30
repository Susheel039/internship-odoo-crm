from odoo import fields, models


class InternshipApplication(models.Model):
    _inherit = "internship.application"

    placement_id = fields.Many2one("internship.placement", index=True, copy=False, readonly=True, ondelete="set null")

    def _create_placement(self):
        placements = self.env["internship.placement"]
        for application in self:
            placements |= self.env["internship.placement"]._create_from_application(application)
        return placements

    def action_view_placement(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "internship.placement",
            "res_id": self.placement_id.id,
            "view_mode": "form",
        }
