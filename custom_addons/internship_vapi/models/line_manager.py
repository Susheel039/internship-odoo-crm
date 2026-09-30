from odoo import models


class InternshipLineManager(models.Model):
    _inherit = "internship.line.manager"

    def action_call_with_ai(self):
        self.env["internship.call.log"].action_queue_call("feedback_request", self)
        return self.env["crm.lead"]._notify_queued()
