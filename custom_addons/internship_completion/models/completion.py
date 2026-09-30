from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class InternshipCompletion(models.Model):
    """Completion checklist (v2). Pre-v2 completion records keep working with their old buttons."""

    _name = "internship.completion"
    _description = "Internship Completion"
    _order = "completion_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Completion Record", required=True, default="New")
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
    )
    company_id = fields.Many2one(
        "internship.company",
        string="Company",
        related="opportunity_id.company_id",
        store=True,
        readonly=True,
    )
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    completion_date = fields.Date(string="Completion Date", default=fields.Date.context_today)
    final_report = fields.Text(
        string="Final Report", deprecated="Replaced by internship.submission report attempts in 19.0.2"
    )
    evaluation_score = fields.Float(
        string="Evaluation Score",
        digits=(3, 1),
        deprecated="Replaced by internship.submission grade / internship.company.evaluation in 19.0.2",
    )
    supervisor_feedback = fields.Text(string="Supervisor Feedback")
    certificate_issued = fields.Boolean(string="Certificate Issued", default=False)
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("approved", "Approved"),
            ("closed", "Closed"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )
    approved_by = fields.Many2one("res.users", string="Approved By", tracking=True)
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True, tracking=True)

    # v2 checklist
    placement_id = fields.Many2one("internship.placement", index=True, ondelete="restrict", tracking=True)
    internship_company_id = fields.Many2one(
        related="placement_id.internship_company_id", store=True, index=True, string="Placement Company"
    )
    university_id = fields.Many2one(related="placement_id.university_id", store=True, index=True)
    chk_report_passed = fields.Boolean(string="Chk Report Passed", compute="_compute_checks", store=True)
    chk_evaluation_received = fields.Boolean(string="Chk Evaluation Received", compute="_compute_checks", store=True)
    chk_certificate_issued = fields.Boolean(string="Chk Certificate Issued", compute="_compute_checks", store=True)
    chk_feedback_submitted = fields.Boolean(string="Chk Feedback Submitted", compute="_compute_checks", store=True)
    all_checks_done = fields.Boolean(compute="_compute_checks", store=True)
    accepted_by_id = fields.Many2one("res.users", readonly=True, tracking=True, copy=False)
    accepted_date = fields.Datetime(readonly=True, copy=False)
    acceptance_comments = fields.Text()
    final_result = fields.Selection([("completed", "Completed"), ("failed", "Failed")], tracking=True, copy=False)

    _placement_unique = models.Constraint("unique(placement_id)", "A placement has only one completion checklist.")

    @api.constrains("start_date", "end_date", "evaluation_score")
    def _check_completion_values(self):
        for completion in self:
            if completion.start_date and completion.end_date and completion.start_date > completion.end_date:
                raise ValidationError(self.env._("The internship start date cannot be after its end date."))
            if not 0 <= completion.evaluation_score <= 100:
                raise ValidationError(self.env._("The evaluation score must be between 0 and 100."))

    @api.depends(
        "placement_id.report_attempt_ids.result",
        "placement_id.evaluation_ids.state",
        "placement_id.certificate_ids.attachment_id",
        "placement_id.feedback_ids",
    )
    def _compute_checks(self):
        for completion in self:
            placement = completion.placement_id
            completion.chk_report_passed = any(a.result == "pass" for a in placement.report_attempt_ids)
            completion.chk_evaluation_received = any(e.state == "submitted" for e in placement.evaluation_ids)
            completion.chk_certificate_issued = bool(placement.certificate_ids.filtered("attachment_id"))
            completion.chk_feedback_submitted = bool(placement.feedback_ids)
            completion.all_checks_done = bool(placement) and all(
                [
                    completion.chk_report_passed,
                    completion.chk_evaluation_received,
                    completion.chk_certificate_issued,
                    completion.chk_feedback_submitted,
                ]
            )

    def action_university_accept(self):
        """All four checks done and the university accepts: close and complete the placement."""
        for completion in self:
            if not completion.placement_id:
                raise UserError(self.env._("Only v2 checklists (linked to a placement) can be accepted."))
            if not completion.all_checks_done:
                raise UserError(self.env._("Complete every checklist item before accepting."))
            completion.write(
                {
                    "accepted_by_id": self.env.user.id,
                    "accepted_date": fields.Datetime.now(),
                    "status": "closed",
                    "completion_date": fields.Date.context_today(self),
                    "certificate_issued": True,
                }
            )
            completion._set_final_result("completed")
            if completion.placement_id.stage_code == "completion":
                completion.placement_id._mark_completed()
        return True

    def _set_final_result(self, result):
        self.write({"final_result": result})
        return True

    # ------------------------------------------------------------------
    # Pre-v2 workflow (kept for existing records)
    # ------------------------------------------------------------------
    def action_start(self):
        self._check_status("draft")
        return self.write({"status": "in_progress"})

    def action_complete(self):
        self._check_status("in_progress")
        if any(not completion.final_report for completion in self):
            raise UserError(self.env._("Add the final report before completing the internship."))
        if any(completion.end_date and completion.end_date > fields.Date.context_today(self) for completion in self):
            raise UserError(self.env._("An internship cannot be completed before its end date."))
        return self.write({"status": "completed", "completion_date": fields.Date.context_today(self)})

    def action_approve(self):
        self._check_status("completed")
        if any(not completion.final_report for completion in self):
            raise UserError(self.env._("A final report is required before approval."))
        return self.write(
            {
                "status": "approved",
                "certificate_issued": True,
                "approved_by": self.env.user.id,
            }
        )

    def action_close(self):
        self._check_status("approved")
        return self.write({"status": "closed"})

    def action_print_certificate(self):
        self.ensure_one()
        if not self.certificate_issued or self.status not in ("approved", "closed"):
            raise UserError(self.env._("The certificate is available after completion approval."))
        return self.env.ref("internship_completion.action_report_completion_certificate").report_action(self)

    def _check_status(self, expected_status):
        if any(completion.status != expected_status for completion in self):
            raise UserError(
                self.env._(
                    "This action is only available when the record is %(status)s.",
                    status=expected_status.replace("_", " "),
                )
            )
