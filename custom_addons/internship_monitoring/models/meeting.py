from odoo import fields, models


class InternshipMeeting(models.Model):
    _name = "internship.meeting"
    _description = "Internship Meeting"
    _order = "meeting_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Meeting Reference", required=True, default="New")
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
    company_id = fields.Many2one(
        "internship.company",
        string="Company",
        related="opportunity_id.company_id",
        store=True,
        readonly=True,
    )
    meeting_date = fields.Datetime(
        string="Meeting Date",
        default=fields.Datetime.now,
        tracking=True,
    )
    meeting_type = fields.Selection(
        [
            ("checkin", "Check-in"),
            ("review", "Review"),
            ("feedback", "Feedback"),
            ("support", "Support"),
        ],
        string="Type",
        default="review",
        tracking=True,
    )
    summary = fields.Text(string="Summary")
    next_action = fields.Text(string="Next Action")
    active = fields.Boolean(default=True, tracking=True)
