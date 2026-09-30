from odoo import fields, models


class InternshipTerminateWizard(models.TransientModel):
    _name = "internship.terminate.wizard"
    _description = "Terminate Placement"

    placement_id = fields.Many2one("internship.placement", required=True)
    initiated_by = fields.Selection(
        [("student", "Student"), ("company", "Company"), ("university", "University")], required=True
    )
    reason_id = fields.Many2one("internship.reason", required=True, domain=[("reason_type", "=", "termination")])
    termination_date = fields.Date(required=True, default=fields.Date.context_today)
    notes = fields.Text()

    def action_confirm(self):
        self.ensure_one()
        self.placement_id._terminate(self.initiated_by, self.reason_id, self.notes, self.termination_date)
        return {"type": "ir.actions.act_window_close"}
