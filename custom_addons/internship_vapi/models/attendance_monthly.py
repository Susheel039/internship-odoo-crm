from odoo import models


class InternshipAttendanceMonthly(models.Model):
    _inherit = "internship.attendance.monthly"

    def action_chase_by_phone(self):
        self.env["internship.call.log"].action_queue_call("attendance_reminder", self)
        return self.env["crm.lead"]._notify_queued()
