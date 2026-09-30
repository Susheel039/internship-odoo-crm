from odoo import fields, models


class InternshipLineManager(models.Model):
    _inherit = "internship.line.manager"

    placement_ids = fields.One2many("internship.placement", "line_manager_id", string="Placements")
    placement_count = fields.Integer(compute="_compute_placement_count")

    def _compute_placement_count(self):
        for manager in self:
            manager.placement_count = len(manager.placement_ids)

    def action_view_placements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Placements"),
            "res_model": "internship.placement",
            "view_mode": "list,form",
            "domain": [("line_manager_id", "=", self.id)],
        }
