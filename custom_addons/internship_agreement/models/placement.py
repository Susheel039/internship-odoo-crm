from odoo import api, fields, models
from odoo.exceptions import UserError


class InternshipPlacement(models.Model):
    _inherit = "internship.placement"

    agreement_ids = fields.One2many("internship.agreement", "placement_id", string="Agreements")
    agreement_count = fields.Integer(compute="_compute_agreement_count")
    agreement_id = fields.Many2one(
        "internship.agreement", compute="_compute_agreement_count", string="Current Agreement"
    )

    @api.depends("agreement_ids.state")
    def _compute_agreement_count(self):
        for placement in self:
            placement.agreement_count = len(placement.agreement_ids)
            live = placement.agreement_ids.filtered(lambda a: a.state != "voided").sorted("version")
            placement.agreement_id = live[-1:]

    def _on_university_approved(self, review):
        result = super()._on_university_approved(review)
        for placement in self:
            self.env["internship.agreement"]._create_for_placement(placement)
        return result

    def action_generate_agreement(self):
        """Issue the agreement for placements that reached the stage without one (e.g. migrated)."""
        for placement in self:
            if placement.stage_code != "agreement" or placement.agreement_id:
                raise UserError(self.env._("%(name)s already has an agreement in progress.", name=placement.name))
            self.env["internship.agreement"]._create_for_placement(placement)
        return True

    def action_view_agreements(self):
        return self._action_related("internship.agreement", self.env._("Agreements"))
