from odoo import api, fields, models
from odoo.exceptions import ValidationError


class InternshipApplication(models.Model):
    _name = "internship.application"
    _description = "Internship Application"
    _order = "application_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Application Reference", required=True, default="New")
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
    university_id = fields.Many2one(
        "internship.university",
        string="University",
        related="student_id.university_id",
        store=True,
        readonly=True,
    )
    application_date = fields.Date(string="Application Date", default=fields.Date.context_today)
    interview_date = fields.Datetime(string="Interview Date")
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("interview", "Interview"),
            ("offered", "Offered"),
            ("rejected", "Rejected"),
            ("accepted", "Accepted"),
            ("documentation", "Documentation"),
            ("agreement", "Agreement"),
            ("approved", "Approved"),
            ("placed", "Placed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    rejection_reason = fields.Text(string="Rejection Reason")
    notes = fields.Text(string="Notes")

    @api.constrains("student_id", "opportunity_id")
    def _check_required_records(self):
        for rec in self:
            if not rec.student_id:
                raise ValidationError("A student is required for every application.")
            if not rec.opportunity_id:
                raise ValidationError("An opportunity is required for every application.")

    def action_submit(self):
        return self.write({"status": "submitted"})

    def action_review(self):
        self._check_status("submitted")
        return self.write({"status": "under_review"})

    def action_interview(self):
        self._check_status("under_review")
        return self.write({"status": "interview"})

    def action_offer(self):
        self._check_status("interview")
        return self.write({"status": "offered"})

    def action_accept(self):
        self._check_status("offered")
        return self.write({"status": "accepted"})

    def action_documentation(self):
        self._check_status("accepted")
        return self.write({"status": "documentation"})

    def action_agreement(self):
        self._check_status("documentation")
        return self.write({"status": "agreement"})

    def action_reject(self, reason=False):
        vals = {"status": "rejected"}
        if reason:
            vals["rejection_reason"] = reason
        return self.write(vals)

    def action_approve(self):
        self._check_status("agreement")
        return self.write({"status": "approved"})

    def action_place(self):
        self._check_status("approved")
        return self.write({"status": "placed"})

    def action_cancel(self):
        if any(application.status in ("placed", "rejected", "cancelled") for application in self):
            raise ValidationError("Placed, rejected, or cancelled applications cannot be cancelled again.")
        return self.write({"status": "cancelled"})

    def _check_status(self, expected_status):
        invalid = self.filtered(lambda application: application.status != expected_status)
        if invalid:
            raise ValidationError(
                "This action is only available when the application is %s." % expected_status.replace("_", " ")
            )
