from odoo import fields, models


class InternshipStudent(models.Model):
    _inherit = "internship.student"

    call_log_ids = fields.One2many("internship.call.log", "student_id", string="Calls")

    def action_call_with_ai(self):
        self.env["internship.call.log"].action_queue_call("lead_generation", self)
        return self.env["crm.lead"]._notify_queued()
