from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    call_log_ids = fields.One2many("internship.call.log", "lead_id", string="Calls")
    call_count = fields.Integer(compute="_compute_call_count")
    last_call_date = fields.Datetime(compute="_compute_last_call", store=True)
    last_call_outcome = fields.Char(compute="_compute_last_call", store=True)

    def _compute_call_count(self):
        for lead in self:
            lead.call_count = len(lead.call_log_ids)

    @api.depends("call_log_ids.call_datetime", "call_log_ids.status", "call_log_ids.ended_reason")
    def _compute_last_call(self):
        for lead in self:
            last = lead.call_log_ids.sorted("call_datetime", reverse=True)[:1]
            lead.last_call_date = last.call_datetime
            lead.last_call_outcome = (
                (last.ended_reason or dict(last._fields["status"].selection).get(last.status)) if last else False
            )

    def action_call_with_ai(self):
        self.env["internship.call.log"].action_queue_call("lead_generation", self)
        return self._notify_queued()

    def _notify_queued(self):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": self.env._("Call queued. It will be dialled within the calling window."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_calls(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Calls"),
            "res_model": "internship.call.log",
            "view_mode": "list,form",
            "domain": [("lead_id", "=", self.id)],
        }
