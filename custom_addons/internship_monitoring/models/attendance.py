from odoo import api, fields, models


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

    # v2: optional daily log feeding the monthly record
    placement_id = fields.Many2one("internship.placement", index=True, ondelete="set null")
    monthly_id = fields.Many2one("internship.attendance.monthly", index=True, ondelete="set null")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._link_monthly()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"placement_id", "attendance_date"} & set(vals):
            self._link_monthly()
        elif "status" in vals:
            self.monthly_id._sync_from_daily()
        return result

    def _link_monthly(self):
        Monthly = self.env["internship.attendance.monthly"]
        for day in self.filtered(lambda d: d.placement_id and d.attendance_date):
            monthly = Monthly.search(
                [
                    ("placement_id", "=", day.placement_id.id),
                    ("year", "=", day.attendance_date.year),
                    ("month", "=", str(day.attendance_date.month)),
                ],
                limit=1,
            ) or Monthly._ensure_for(day.placement_id, day.attendance_date)
            if day.monthly_id != monthly:
                super(InternshipAttendance, day).write({"monthly_id": monthly.id})
        self.monthly_id._sync_from_daily()
        return True

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
