from odoo import fields, models


class InternshipCompany(models.Model):
    _inherit = "internship.company"

    placement_ids = fields.One2many("internship.placement", "internship_company_id", string="Placements")
    placement_count = fields.Integer(compute="_compute_placement_count")

    def _compute_placement_count(self):
        counts = dict(
            self.env["internship.placement"]._read_group(
                [("internship_company_id", "in", self.ids)], ["internship_company_id"], ["__count"]
            )
        )
        for company in self:
            company.placement_count = counts.get(company, 0)

    def action_view_placements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Placements"),
            "res_model": "internship.placement",
            "view_mode": "kanban,list,form",
            "domain": [("internship_company_id", "=", self.id)],
            "context": {"default_internship_company_id": self.id},
        }
