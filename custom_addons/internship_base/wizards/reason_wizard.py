from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.reason import REASON_TYPES


class InternshipReasonWizard(models.TransientModel):
    """Ask for a reason, then call `<method>(reason, note)` on the active records.

    Open it from a button with context
    ``{'default_reason_type': 'rejection', 'default_method': 'action_reject'}``.
    """

    _name = "internship.reason.wizard"
    _description = "Give a Reason"

    reason_type = fields.Selection(REASON_TYPES, required=True)
    method = fields.Char(required=True)
    reason_id = fields.Many2one("internship.reason", string="Reason", domain="[('reason_type', '=', reason_type)]")
    reason_required = fields.Boolean(default=True)
    note = fields.Text()
    res_model = fields.Char(default=lambda self: self.env.context.get("active_model"))
    res_ids = fields.Json(default=lambda self: self.env.context.get("active_ids") or [])

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if not values.get("res_ids") and self.env.context.get("active_id"):
            values["res_ids"] = [self.env.context["active_id"]]
        return values

    def action_confirm(self):
        self.ensure_one()
        # Only public workflow methods can be triggered from here.
        if not self.method.startswith("action_") or not self.res_model or self.res_model not in self.env:
            raise UserError(self.env._("This action cannot be run from the reason dialog."))
        if self.reason_required and not self.reason_id:
            raise UserError(self.env._("Please select a reason."))
        records = self.env[self.res_model].browse(self.res_ids or []).exists()
        method = getattr(records, self.method, None)
        if not callable(method):
            raise UserError(self.env._("This action cannot be run from the reason dialog."))
        result = method(self.reason_id, self.note)
        return result if isinstance(result, dict) else {"type": "ir.actions.act_window_close"}
