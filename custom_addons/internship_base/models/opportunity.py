from odoo import api, fields, models
from odoo.exceptions import ValidationError


class InternshipOpportunity(models.Model):
    _name = "internship.opportunity"
    _description = "Internship Opportunity"
    _order = "application_deadline, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Opportunity Title", required=True, tracking=True)
    company_id = fields.Many2one(
        "internship.company",
        string="Company",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    program_id = fields.Many2one(
        "internship.program",
        string="Program",
        ondelete="restrict",
        tracking=True,
    )
    job_title = fields.Char(string="Job Title")
    description = fields.Text(string="Description")
    location = fields.Char(string="Location")
    internship_type = fields.Selection(
        [
            ("internship", "Internship"),
            ("placement", "Placement"),
            ("research", "Research"),
            ("project", "Project"),
        ],
        string="Type",
        default="internship",
    )
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    application_deadline = fields.Date(string="Application Deadline")
    number_of_positions = fields.Integer(string="Available Positions", default=1)
    skills_required = fields.Text(string="Skills Required")
    active = fields.Boolean(default=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Open"),
            ("filled", "Filled"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    @api.constrains("application_deadline", "start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.application_deadline and rec.start_date and rec.application_deadline > rec.start_date:
                raise ValidationError(self.env._("The application deadline must be before the start date."))
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(self.env._("The opportunity start date cannot be after the end date."))

    def action_open(self):
        self.write({"state": "open"})

    def action_fill(self):
        self.write({"state": "filled"})

    def action_close(self):
        self.write({"state": "closed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_draft(self):
        self.write({"state": "draft"})
