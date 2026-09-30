from odoo import fields, models


class InternshipChangeRequest(models.Model):
    _inherit = "internship.change.request"

    agreement_id = fields.Many2one(
        "internship.agreement", string="Agreement", readonly=True, copy=False, index=True, ondelete="set null"
    )

    def _create_agreement_amendment(self):
        """Dates, hours or role changed: issue an amended agreement for all three parties to sign."""
        self.ensure_one()
        placement = self.placement_id
        signed = placement.agreement_ids.filtered(lambda a: a.state == "fully_signed").sorted("version")[-1:]
        if not signed:
            return False
        amendment = self.env["internship.agreement"]._create_for_placement(
            placement, amendment_of=signed, change_request=self
        )
        self.agreement_id = amendment
        return amendment
