from odoo import fields, models


class InternshipAttendance(models.Model):
    _name = "internship.attendance"
    _description = "Internship Attendance"
    _order = "attendance_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Attendance Reference", required=True, default="New")
    student_id = fields.Many2one(
        "internship.student",
        string="Student",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    opportunity_id = fields.Many2one(
        "internship.opportunity",
        string="Opportunity",
        ondelete="restrict",
        tracking=True,
    )
    attendance_date = fields.Date(
        string="Attendance Date",
        default=fields.Date.context_today,
        tracking=True,
    )
    check_in = fields.Datetime(string="Check In")
    check_out = fields.Datetime(string="Check Out")
    status = fields.Selection(
        [
            ("present", "Present"),
            ("late", "Late"),
            ("absent", "Absent"),
            ("excused", "Excused"),
            ("half_day", "Half Day"),
        ],
        string="Status",
        default="present",
        tracking=True,
    )
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True, tracking=True)

    def action_mark_present(self):
        return self.write({"status": "present", "check_in": fields.Datetime.now()})

    def action_mark_late(self):
        return self.write({"status": "late", "check_in": fields.Datetime.now()})

    def action_mark_absent(self):
        return self.write({"status": "absent"})

    def action_mark_excused(self):
        return self.write({"status": "excused"})

    def action_checkout(self):
        return self.write({"check_out": fields.Datetime.now()})
