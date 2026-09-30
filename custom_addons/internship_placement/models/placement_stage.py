from odoo import api, fields, models


class InternshipPlacementStage(models.Model):
    _name = "internship.placement.stage"
    _description = "Placement Stage"
    _inherit = ["internship.lookup.mixin"]

    code = fields.Char(required=True)
    phase = fields.Selection(
        [("1", "Admission / approval"), ("2", "Monitoring"), ("3", "Completion / closure")],
        required=True,
        default="1",
        index=True,
    )
    fold = fields.Boolean(string="Folded in Kanban")
    is_closed = fields.Boolean(string="Closed Stage", help="Placements in this stage are finished.")
    is_won = fields.Boolean(string="Successful Outcome")

    @api.model
    def _get_by_code(self, code):
        stage = self.with_context(active_test=False).search([("code", "=", code)], limit=1)
        if not stage:
            raise ValueError(f"Unknown placement stage code: {code}")
        return stage
