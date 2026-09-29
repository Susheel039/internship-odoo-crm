from odoo import api, fields, models
from odoo.exceptions import ValidationError


class InternshipProgram(models.Model):
    _name = "internship.program"
    _description = "Internship Program"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Program Name", required=True, tracking=True)
    university_id = fields.Many2one(
        "internship.university",
        string="University",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    description = fields.Text(string="Description")
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    application_deadline = fields.Date(string="Application Deadline")
    opportunity_ids = fields.One2many("internship.opportunity", "program_id", string="Opportunities")
    active = fields.Boolean(default=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Open"),
            ("closed", "Closed"),
            ("archived", "Archived"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    @api.constrains("start_date", "end_date", "application_deadline")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError("The program start date cannot be after the end date.")
            if rec.application_deadline and rec.start_date and rec.application_deadline > rec.start_date:
                raise ValidationError("The application deadline must be before the program starts.")

    def action_open(self):
        return self.write({"state": "open"})

    def action_close(self):
        return self.write({"state": "closed"})

    def action_archive(self):
        return self.write({"state": "archived"})

    def action_reset_draft(self):
        return self.write({"state": "draft"})
