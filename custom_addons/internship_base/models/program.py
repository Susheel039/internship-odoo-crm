import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# System-wide fallbacks for the workflow rules. Override per database with the
# system parameter `internship_base.rule_<name>` (Settings > Internship CRM).
RULE_DEFAULTS = {
    "form_due_days": 7,
    "monthly_due_day": 5,
    "monthly_late_grace_days": 3,
    "report_deadline_days": 14,
    "resubmission_days": 14,
    "max_report_attempts": 2,
    "tripartite_attendance_pct": 80.0,
    "tripartite_rating_threshold": 2,
    "expiry_alert_days": 30,
    "retention_years": 6,
}

RULE_HELP = "Leave at 0 to use the university default (or the system default)."


class InternshipProgram(models.Model):
    _name = "internship.program"
    _description = "Internship Programme"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Programme Name", required=True, tracking=True)
    university_id = fields.Many2one(
        "internship.university",
        string="University",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    description = fields.Text(string="Description")
    start_date = fields.Date(string="Start Date", tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    application_deadline = fields.Date(string="Application Deadline", tracking=True)
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
        index=True,
    )

    department = fields.Char()
    academic_year_id = fields.Many2one("internship.academic.year", string="Academic Year", index=True, tracking=True)
    credit_value = fields.Integer(string="Credits")

    # Internship rules
    min_duration_weeks = fields.Integer(string="Minimum duration (weeks)")
    max_duration_weeks = fields.Integer(string="Maximum duration (weeks)")
    required_hours_per_week = fields.Float(string="Required hours per week")
    allowed_start_from = fields.Date(string="Earliest start")
    allowed_start_to = fields.Date(string="Latest start")

    # Workflow rules: 0 means "inherit" (see _get_rule)
    form_due_days = fields.Integer(string="Form due (days)", help=RULE_HELP)
    monthly_due_day = fields.Integer(string="Monthly record due (day of month)", help=RULE_HELP)
    monthly_late_grace_days = fields.Integer(string="Monthly late grace (days)", help=RULE_HELP)
    report_deadline_days = fields.Integer(string="Report deadline (days after end)", help=RULE_HELP)
    resubmission_days = fields.Integer(string="Resubmission window (days)", help=RULE_HELP)
    max_report_attempts = fields.Integer(string="Max report attempts", help=RULE_HELP)
    tripartite_attendance_pct = fields.Float(string="Tripartite if attendance below (%)", help=RULE_HELP)
    tripartite_rating_threshold = fields.Integer(string="Tripartite if rating at or below", help=RULE_HELP)
    expiry_alert_days = fields.Integer(string="Expiry alert (days before)", help=RULE_HELP)
    retention_years = fields.Integer(string="Data retention (years)", help=RULE_HELP)

    # Templates
    form_template_id = fields.Many2one("ir.attachment", string="Internship form template")
    agreement_template_id = fields.Many2one("ir.attachment", string="Agreement template")
    rubric_template_id = fields.Many2one("ir.attachment", string="Rubric template")
    certificate_template_id = fields.Many2one("ir.attachment", string="Certificate template")
    feedback_template_id = fields.Many2one("ir.attachment", string="Feedback template")

    rubric_criterion_ids = fields.One2many("internship.rubric.criterion", "program_id", string="Rubric Criteria")
    placement_properties_definition = fields.PropertiesDefinition("Placement Properties")
    student_properties_definition = fields.PropertiesDefinition("Student Properties")

    @api.constrains("start_date", "end_date", "application_deadline")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.start_date > rec.end_date:
                raise ValidationError(self.env._("The program start date cannot be after the end date."))
            if rec.application_deadline and rec.start_date and rec.application_deadline > rec.start_date:
                raise ValidationError(self.env._("The application deadline must be before the program starts."))

    @api.constrains("min_duration_weeks", "max_duration_weeks", "allowed_start_from", "allowed_start_to")
    def _check_rules(self):
        for rec in self:
            if rec.min_duration_weeks and rec.max_duration_weeks and rec.min_duration_weeks > rec.max_duration_weeks:
                raise ValidationError(self.env._("The minimum duration cannot exceed the maximum duration."))
            if rec.allowed_start_from and rec.allowed_start_to and rec.allowed_start_from > rec.allowed_start_to:
                raise ValidationError(self.env._("The earliest start date must be before the latest start date."))

    def _get_rule(self, name):
        """Return a workflow rule: programme value, else university default, else system default.

        Works on an empty recordset too (records without a programme get the system default).
        """
        if name not in RULE_DEFAULTS:
            raise KeyError(name)
        default = RULE_DEFAULTS[name]
        if self:
            self.ensure_one()
            if self[name]:
                return self[name]
            university_value = self.university_id[f"default_rules_{name}"] if self.university_id else 0
            if university_value:
                return university_value
        raw = self.env["ir.config_parameter"].sudo().get_param(f"internship_base.rule_{name}")
        if raw:
            try:
                return type(default)(raw)
            except ValueError:
                _logger.warning("Ignoring invalid system parameter internship_base.rule_%s=%r", name, raw)
        return default

    def action_open(self):
        return self.write({"state": "open"})

    def action_close(self):
        return self.write({"state": "closed"})

    def action_archive(self):
        return self.write({"state": "archived"})

    def action_reset_draft(self):
        return self.write({"state": "draft"})
