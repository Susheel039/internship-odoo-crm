from odoo import api, fields, models
from odoo.exceptions import ValidationError

# The keys documentation / agreement / approved / placed were removed in 19.0.2.0.0:
# that lifecycle now lives on internship.placement. migrations/19.0.2.0.0/pre-migrate.py
# moves existing rows to "accepted" and records them for the placement migration.
APPLICATION_STATUSES = [
    ("draft", "Draft"),
    ("submitted", "Applied"),
    ("under_review", "Shortlisted"),
    ("interview", "Interviewed"),
    ("offered", "Offered"),
    ("rejected", "Rejected"),
    ("accepted", "Accepted"),
    ("declined", "Declined by student"),
    ("cancelled", "Withdrawn"),
]
OPEN_STATUSES = ("draft", "submitted", "under_review", "interview", "offered")


class InternshipApplication(models.Model):
    _name = "internship.application"
    _description = "Internship Application"
    _order = "application_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Name", required=True, default="New", copy=False, index=True)
    student_id = fields.Many2one(
        "internship.student",
        string="Student",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    opportunity_id = fields.Many2one(
        "internship.opportunity",
        string="Opportunity",
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "internship.company",
        string="Company",
        related="opportunity_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    university_id = fields.Many2one(
        "internship.university",
        string="University",
        related="student_id.university_id",
        store=True,
        readonly=True,
        index=True,
    )
    application_date = fields.Date(string="Application Date", default=fields.Date.context_today, tracking=True)
    interview_date = fields.Datetime(string="Interview Date", tracking=True)
    status = fields.Selection(APPLICATION_STATUSES, string="Status", default="draft", tracking=True, index=True)
    rejection_reason = fields.Text(string="Rejection Notes")
    notes = fields.Text(string="Notes")

    # Submission
    cv_attachment_id = fields.Many2one("ir.attachment", string="CV Attachment")
    cover_letter_attachment_id = fields.Many2one("ir.attachment", string="Cover Letter Attachment")
    screening_answers = fields.Text()

    # Interview
    interview_mode = fields.Selection(
        [("in_app_video", "Video call"), ("in_person", "In person"), ("phone", "Phone")], default="in_app_video"
    )
    interviewer_id = fields.Many2one(
        "internship.line.manager", string="Interviewer", domain="[('company_id', '=', company_id)]"
    )
    interview_notes = fields.Text()
    interview_score = fields.Integer(help="0 to 10")
    calendar_event_id = fields.Many2one("calendar.event", string="Calendar Event", copy=False)

    # Outcome
    offer_made = fields.Boolean(copy=False, tracking=True)
    decision_date = fields.Date(copy=False, tracking=True)
    rejection_reason_id = fields.Many2one(
        "internship.reason", string="Rejection Reason", domain=[("reason_type", "=", "rejection")], tracking=True
    )

    # Student response
    student_response = fields.Selection(
        [("pending", "Pending"), ("accepted", "Accepted"), ("declined", "Declined")],
        default="pending",
        tracking=True,
        copy=False,
    )
    decline_reason_id = fields.Many2one(
        "internship.reason", string="Decline Reason", domain=[("reason_type", "=", "decline")], tracking=True
    )
    response_date = fields.Date(copy=False, tracking=True)

    # Auto-withdraw
    auto_withdrawn = fields.Boolean(copy=False, readonly=True)
    withdrawn_reason = fields.Char(copy=False)
    withdrawn_date = fields.Date(copy=False)

    _interview_score_range = models.Constraint(
        "CHECK(interview_score IS NULL OR (interview_score >= 0 AND interview_score <= 10))",
        "The interview score must be between 0 and 10.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") in (False, "New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("internship.application") or "New"
        return super().create(vals_list)

    @api.constrains("student_id", "opportunity_id")
    def _check_required_records(self):
        for rec in self:
            if not rec.student_id:
                raise ValidationError(self.env._("A student is required for every application."))
            if not rec.opportunity_id:
                raise ValidationError(self.env._("An opportunity is required for every application."))

    def _check_status(self, *expected_statuses):
        invalid = self.filtered(lambda application: application.status not in expected_statuses)
        if invalid:
            labels = dict(self._fields["status"]._description_selection(self.env))
            raise ValidationError(
                self.env._(
                    "This action is only available when the application is %(status)s.",
                    status=" / ".join(labels[s] for s in expected_statuses),
                )
            )

    @staticmethod
    def _reason_id(reason):
        return reason.id if hasattr(reason, "id") else (reason or False)

    # ------------------------------------------------------------------
    # Company / university side
    # ------------------------------------------------------------------
    def action_submit(self):
        self._check_status("draft")
        return self.write({"status": "submitted", "application_date": fields.Date.context_today(self)})

    def action_shortlist(self):
        self._check_status("submitted")
        return self.write({"status": "under_review"})

    def action_review(self):
        """Kept for backwards compatibility (pre-v2 button name)."""
        return self.action_shortlist()

    def action_interview(self):
        self._check_status("under_review")
        return self.write({"status": "interview"})

    def action_offer(self):
        self._check_status("interview", "under_review")
        return self.write(
            {
                "status": "offered",
                "offer_made": True,
                "decision_date": fields.Date.context_today(self),
                "student_response": "pending",
            }
        )

    def action_reject(self, reason=None, note=None):
        self._check_status(*OPEN_STATUSES)
        values = {"status": "rejected", "decision_date": fields.Date.context_today(self)}
        reason_id = self._reason_id(reason)
        if reason_id:
            values["rejection_reason_id"] = reason_id
        if note:
            values["rejection_reason"] = note
        return self.write(values)

    def action_withdraw(self, reason=None, note=None):
        self._check_status(*OPEN_STATUSES)
        return self.write(
            {
                "status": "cancelled",
                "withdrawn_reason": note or (reason.name if hasattr(reason, "name") else False),
                "withdrawn_date": fields.Date.context_today(self),
            }
        )

    def action_cancel(self):
        """Kept for backwards compatibility: cancelling is withdrawing."""
        return self.action_withdraw()

    # ------------------------------------------------------------------
    # Student side
    # ------------------------------------------------------------------
    def action_student_accept(self):
        self._check_status("offered")
        self.write(
            {
                "status": "accepted",
                "student_response": "accepted",
                "response_date": fields.Date.context_today(self),
            }
        )
        self._create_placement()
        return True

    def action_accept(self):
        """Kept for backwards compatibility (pre-v2 button name)."""
        return self.action_student_accept()

    def action_student_decline(self, reason=None, note=None):
        self._check_status("offered")
        values = {
            "status": "declined",
            "student_response": "declined",
            "response_date": fields.Date.context_today(self),
        }
        reason_id = self._reason_id(reason)
        if reason_id:
            values["decline_reason_id"] = reason_id
        self.write(values)
        if note:
            for application in self:
                application.message_post(body=note)
        return True

    def _create_placement(self):
        """Hook: internship_placement creates the placement for accepted applications."""
        return False

    def _auto_withdraw(self, reason_label):
        """Withdraw open applications because another internship was approved."""
        open_applications = self.filtered(lambda a: a.status in OPEN_STATUSES)
        open_applications.write(
            {
                "status": "cancelled",
                "auto_withdrawn": True,
                "withdrawn_reason": reason_label,
                "withdrawn_date": fields.Date.context_today(self),
            }
        )
        for application in open_applications:
            application.message_post(body=reason_label)
        return open_applications
