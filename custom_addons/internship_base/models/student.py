from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.activity import default_coordinator, schedule_activity_once

RESTRICTED_GROUPS = "internship_base.group_university_administrator,internship_base.group_platform_administrator"

LIFECYCLE_STATUSES = [
    ("searching", "Searching"),
    ("applied", "Applied"),
    ("offered", "Offered"),
    ("approved", "Approved"),
    ("in_internship", "In internship"),
    ("completed", "Completed"),
    ("failed", "Failed"),
    ("withdrawn", "Withdrawn"),
]


class InternshipStudent(models.Model):
    _name = "internship.student"
    _description = "Student"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Name", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    student_id = fields.Char(string="Student ID", tracking=True, index=True)
    university_id = fields.Many2one(
        "internship.university",
        string="University",
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    course = fields.Char(string="Course")
    department = fields.Char(string="Department")
    graduation_year = fields.Integer(string="Graduation Year")
    application_ids = fields.One2many("internship.application", "student_id", string="Application")
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text(string="Notes")

    # Personal
    date_of_birth = fields.Date()
    image = fields.Binary(related="partner_id.image_1920", readonly=False)

    # Academic
    program_id = fields.Many2one("internship.program", string="Program", index=True, tracking=True)
    academic_year_id = fields.Many2one("internship.academic.year", string="Academic Year", index=True, tracking=True)
    year_of_study = fields.Selection(
        [("1", "Year 1"), ("2", "Year 2"), ("3", "Year 3"), ("4", "Year 4"), ("5", "Year 5"), ("pg", "Postgraduate")],
        string="Year Of Study",
    )
    academic_tutor_id = fields.Many2one("res.users", string="Academic Tutor", index=True, tracking=True)
    expected_graduation = fields.Date()

    # Compliance
    rtw_status = fields.Selection(
        [("not_checked", "Not checked"), ("pending", "Pending"), ("verified", "Verified"), ("failed", "Failed")],
        string="RTW Status",
        default="not_checked",
        tracking=True,
        index=True,
    )
    rtw_document_type = fields.Selection(
        [("uk_passport", "UK passport"), ("share_code", "Share code"), ("evisa", "eVisa"), ("other", "Other")],
        string="RTW Document Type",
    )
    rtw_expiry = fields.Date(string="RTW Expiry", tracking=True)
    rtw_checked_by_id = fields.Many2one("res.users", string="RTW Checked By", tracking=True)
    rtw_checked_date = fields.Date(string="RTW Checked Date", tracking=True)
    dbs_required = fields.Boolean(string="DBS Required")
    dbs_status = fields.Selection(
        [("not_required", "Not required"), ("pending", "Pending"), ("clear", "Clear"), ("issue", "Issue raised")],
        string="DBS Status",
        default="not_required",
        tracking=True,
    )
    gdpr_consent = fields.Boolean(string="GDPR Consent", tracking=True)
    gdpr_consent_date = fields.Date(string="GDPR Consent Date", tracking=True)
    consent_withdrawn_date = fields.Date(tracking=True)
    retention_until = fields.Date(
        compute="_compute_retention_until",
        store=True,
        index=True,
        help="Personal data is reviewed for deletion after this date. Never deleted automatically.",
    )
    retention_flagged = fields.Boolean(string="Retention Review Due", copy=False, tracking=True, index=True)
    retention_flag_date = fields.Date(copy=False)

    # Visa (restricted)
    visa_required = fields.Boolean(groups=RESTRICTED_GROUPS, tracking=True)
    visa_type = fields.Char(groups=RESTRICTED_GROUPS)
    visa_expiry = fields.Date(groups=RESTRICTED_GROUPS, tracking=True)
    term_time_hour_limit = fields.Float(string="Term Time Hour Limit", groups=RESTRICTED_GROUPS)
    placement_permitted = fields.Boolean(groups=RESTRICTED_GROUPS, tracking=True)
    visa_checked_by_id = fields.Many2one("res.users", string="Visa Checked By", groups=RESTRICTED_GROUPS)
    visa_check_date = fields.Date(groups=RESTRICTED_GROUPS)

    # Reasonable adjustments (restricted to coordinators)
    adjustments_needed = fields.Boolean(string="Adjustments Needed", groups=RESTRICTED_GROUPS)
    adjustments_notes = fields.Text(string="Adjustments Notes", groups=RESTRICTED_GROUPS)
    adjustments_shared_with_company = fields.Boolean(
        string="Adjustments Shared With Company",
        groups=RESTRICTED_GROUPS,
        help="Only with the student's recorded consent.",
    )

    # Profile
    cv_attachment_id = fields.Many2one("ir.attachment", string="CV Attachment")
    skill_ids = fields.Many2many("internship.skill", string="Skill")
    sector_ids = fields.Many2many("internship.sector", string="Sector")
    preferred_locations = fields.Char()
    portfolio_url = fields.Char(string="Portfolio URL")

    # Emergency contact
    emergency_name = fields.Char(string="Emergency Name")
    emergency_relationship = fields.Char(string="Emergency Relationship")
    emergency_phone = fields.Char(string="Emergency Phone")

    lifecycle_status = fields.Selection(
        LIFECYCLE_STATUSES,
        compute="_compute_lifecycle_status",
        store=True,
        index=True,
        tracking=True,
    )
    properties = fields.Properties("Properties", definition="program_id.student_properties_definition", copy=True)

    @api.depends("application_ids.status")
    def _compute_lifecycle_status(self):
        for student in self:
            student.lifecycle_status = student._lifecycle_from_applications()

    def _lifecycle_from_applications(self):
        """Lifecycle derived from applications only; internship_placement refines it with placements."""
        self.ensure_one()
        statuses = set(self.application_ids.mapped("status"))
        if statuses & {"accepted", "offered"}:
            return "offered"
        if statuses & {"submitted", "under_review", "interview"}:
            return "applied"
        if statuses and statuses <= {"cancelled"}:
            return "withdrawn"
        return "searching"

    @api.depends("program_id", "expected_graduation", "graduation_year")
    def _compute_retention_until(self):
        for student in self:
            anchor = student._retention_anchor_date()
            years = student.program_id._get_rule("retention_years")
            student.retention_until = anchor + relativedelta(years=years) if anchor else False

    def _retention_anchor_date(self):
        """Date the retention period starts from; internship_placement uses the last placement end."""
        self.ensure_one()
        if self.expected_graduation:
            return self.expected_graduation
        if self.graduation_year:
            return fields.Date.to_date(f"{self.graduation_year}-12-31")
        return False

    # ------------------------------------------------------------------
    # Crons
    # ------------------------------------------------------------------
    def _coordinator_user(self):
        self.ensure_one()
        contact = self.university_id.contact_ids.filtered(lambda c: c.role == "coordinator" and c.user_id)[:1]
        return self.academic_tutor_id or contact.user_id or default_coordinator(self.env)

    @api.model
    def _cron_expiry_alerts(self):
        today = fields.Date.context_today(self)
        students = self.sudo().search(
            ["|", ("rtw_expiry", "!=", False), ("visa_expiry", "!=", False), ("active", "=", True)]
        )
        for student in students:
            horizon = today + relativedelta(days=student.program_id._get_rule("expiry_alert_days"))
            checks = [
                (student.rtw_expiry, self.env._("Right to work")),
                (student.visa_expiry, self.env._("Visa")),
            ]
            for expiry, label in checks:
                if expiry and expiry <= horizon:
                    state = self.env._("expired") if expiry < today else self.env._("expiring")
                    schedule_activity_once(
                        student,
                        student._coordinator_user(),
                        self.env._("%(label)s %(state)s on %(date)s", label=label, state=state, date=expiry),
                        deadline=min(expiry, horizon),
                    )
        return True

    @api.model
    def _cron_gdpr_retention(self):
        """Flag students past their retention date for review. Nothing is deleted automatically."""
        today = fields.Date.context_today(self)
        students = self.sudo().search([("retention_until", "<", today), ("retention_flagged", "=", False)])
        admin = default_coordinator(self.env)
        for student in students:
            student.write({"retention_flagged": True, "retention_flag_date": today})
            schedule_activity_once(
                student,
                admin,
                self.env._("GDPR retention review"),
                note=self.env._(
                    "Retention period ended on %(date)s. Review and archive if no longer needed.",
                    date=student.retention_until,
                ),
            )
        return len(students)

    def action_retention_archive(self):
        """Archive after an administrator has reviewed the retention flag."""
        if not self.env.user.has_group("internship_base.group_platform_administrator"):
            raise UserError(self.env._("Only a platform administrator can archive records for data retention."))
        for student in self:
            student.message_post(body=self.env._("Archived after GDPR retention review."))
        return self.write({"active": False})
