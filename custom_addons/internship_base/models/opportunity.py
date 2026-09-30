from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .company_site import WORK_MODES


class InternshipOpportunity(models.Model):
    _name = "internship.opportunity"
    _description = "Internship Opportunity"
    _order = "application_deadline, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Name", required=True, tracking=True)
    company_id = fields.Many2one(
        "internship.company",
        string="Company",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    program_id = fields.Many2one(
        "internship.program",
        string="Program",
        ondelete="restrict",
        tracking=True,
        index=True,
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
        string="Internship Type",
        default="internship",
    )
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    application_deadline = fields.Date(string="Application Deadline")
    number_of_positions = fields.Integer(string="Number Of Positions", default=1)
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
        string="State",
        default="draft",
        tracking=True,
        index=True,
    )

    department = fields.Char()
    site_id = fields.Many2one(
        "internship.company.site", string="Site", domain="[('company_id', '=', company_id)]", index=True
    )
    work_mode = fields.Selection(WORK_MODES, default="on_site")
    hours_per_week = fields.Float(default=37.5)
    is_paid = fields.Boolean(string="Is Paid", default=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self._default_currency())
    salary_amount = fields.Monetary(currency_field="currency_id")
    salary_note = fields.Char(help="e.g. 'per annum, pro rata' or 'London Living Wage'.")
    duration_weeks = fields.Integer(compute="_compute_duration_weeks", store=True)
    posting_date = fields.Date(default=fields.Date.context_today)
    positions_filled = fields.Integer(compute="_compute_positions_filled")
    skill_ids = fields.Many2many("internship.skill", string="Skill")
    open_to_visa_holders = fields.Boolean(default=True)
    max_hours_per_week = fields.Float(help="Upper limit, e.g. for students on a term-time visa limit.")

    def _default_currency(self):
        return self.env.ref("base.GBP", raise_if_not_found=False) or self.env.company.currency_id

    @api.constrains("application_deadline", "start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.application_deadline and rec.start_date and rec.application_deadline > rec.start_date:
                raise ValidationError(self.env._("The application deadline must be before the start date."))
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(self.env._("The opportunity start date cannot be after the end date."))

    @api.depends("start_date", "end_date")
    def _compute_duration_weeks(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duration_weeks = ((rec.end_date - rec.start_date).days + 1 + 6) // 7
            else:
                rec.duration_weeks = 0

    def _compute_positions_filled(self):
        """Accepted applications; internship_placement counts active placements instead."""
        counts = dict(
            self.env["internship.application"]._read_group(
                [("opportunity_id", "in", self.ids), ("status", "=", "accepted")], ["opportunity_id"], ["__count"]
            )
        )
        for rec in self:
            rec.positions_filled = counts.get(rec, 0)

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
