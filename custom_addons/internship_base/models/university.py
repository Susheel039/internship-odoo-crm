from odoo import fields, models


class InternshipUniversity(models.Model):
    _name = "internship.university"
    _description = "University"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="University Name", required=True, tracking=True)
    code = fields.Char(string="Code", tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    contact_email = fields.Char(string="Contact Email")
    phone = fields.Char(string="Phone")
    address = fields.Text(string="Address")
    active = fields.Boolean(default=True, tracking=True)
    user_ids = fields.Many2many("res.users", string="Users")
    student_ids = fields.One2many("internship.student", "university_id", string="Students")
    notes = fields.Text(string="Notes")

    ukprn = fields.Char(string="UKPRN", tracking=True, help="UK Provider Reference Number (8 digits).")
    website = fields.Char(related="partner_id.website", readonly=False)
    logo = fields.Binary(related="partner_id.image_1920", readonly=False)
    contact_ids = fields.One2many("internship.university.contact", "university_id", string="Contacts")
    program_ids = fields.One2many("internship.program", "university_id", string="Programmes")
    framework_template_ids = fields.Many2many(
        "ir.attachment",
        "internship_university_template_rel",
        "university_id",
        "attachment_id",
        string="Default Templates",
        help="Default form, agreement and rubric templates offered to new programmes.",
    )

    # University-wide workflow defaults; programmes fall back to these (see internship.program._get_rule).
    default_rules_form_due_days = fields.Integer(string="Form due (days)", default=7)
    default_rules_monthly_due_day = fields.Integer(string="Monthly record due (day of month)", default=5)
    default_rules_monthly_late_grace_days = fields.Integer(string="Monthly late grace (days)", default=3)
    default_rules_report_deadline_days = fields.Integer(string="Report deadline (days after end)", default=14)
    default_rules_resubmission_days = fields.Integer(string="Resubmission window (days)", default=14)
    default_rules_max_report_attempts = fields.Integer(string="Max report attempts", default=2)
    default_rules_tripartite_attendance_pct = fields.Float(string="Tripartite if attendance below (%)", default=80.0)
    default_rules_tripartite_rating_threshold = fields.Integer(string="Tripartite if rating at or below", default=2)
    default_rules_expiry_alert_days = fields.Integer(string="Expiry alert (days before)", default=30)
    default_rules_retention_years = fields.Integer(string="Data retention (years)", default=6)

    _ukprn_unique = models.Constraint("unique(ukprn)", "Another university already uses this UKPRN.")
