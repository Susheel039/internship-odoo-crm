from odoo import fields, models
from odoo.exceptions import UserError


class InternshipPlacement(models.Model):
    _inherit = "internship.placement"

    call_log_ids = fields.One2many("internship.call.log", "placement_id", string="Call Log")
    call_count = fields.Integer(compute="_compute_call_count")

    def _compute_call_count(self):
        for placement in self:
            placement.call_count = len(placement.call_log_ids)

    def action_chase_form_by_phone(self):
        if self.filtered(lambda p: p.stage_code != "form_requested"):
            raise UserError(self.env._("Only placements waiting for the internship form can be chased."))
        self.env["internship.call.log"].action_queue_call("document_chase", self)
        return self.env["crm.lead"]._notify_queued()

    def action_view_calls(self):
        return self._action_related("internship.call.log", self.env._("Calls"))
