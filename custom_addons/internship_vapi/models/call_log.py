from odoo import fields, models


class InternshipCallLog(models.Model):
    _name = "internship.call.log"
    _description = "Internship Call Log"
    _order = "call_datetime desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Call Reference", required=True, default="New")
    external_call_id = fields.Char(string="External Call ID", index=True, copy=False, readonly=True)
    student_id = fields.Many2one(
        "internship.student",
        string="Student",
        ondelete="restrict",
        tracking=True,
    )
    opportunity_id = fields.Many2one(
        "internship.opportunity",
        string="Opportunity",
        ondelete="restrict",
        tracking=True,
    )
    company_id = fields.Many2one(
        "internship.company",
        string="Company",
        related="opportunity_id.company_id",
        store=True,
        readonly=True,
    )
    call_datetime = fields.Datetime(string="Call Date and Time", default=fields.Datetime.now)
    call_type = fields.Selection(
        [
            ("inbound", "Inbound"),
            ("outbound", "Outbound"),
            ("follow_up", "Follow-up"),
            ("screening", "Screening"),
        ],
        string="Call Type",
        default="outbound",
        tracking=True,
    )
    status = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("connected", "Connected"),
            ("missed", "Missed"),
            ("completed", "Completed"),
        ],
        string="Status",
        default="scheduled",
        tracking=True,
    )
    duration_seconds = fields.Integer(string="Duration (seconds)", default=0)
    summary = fields.Text(string="Summary")
    recording_url = fields.Char(string="Recording URL")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True, tracking=True)

    _external_call_id_unique = models.Constraint(
        "unique(external_call_id)",
        "Each external call can only be imported once.",
    )

    def action_connect(self):
        return self.write({"status": "connected"})

    def action_miss(self):
        return self.write({"status": "missed"})

    def action_complete(self):
        return self.write({"status": "completed"})
