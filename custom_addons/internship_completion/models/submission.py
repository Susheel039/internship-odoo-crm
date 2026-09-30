from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.internship_base.services.activity import default_coordinator, schedule_activity_once


class InternshipSubmission(models.Model):
    """Final report attempt (v2). Pre-v2 submissions keep their data and keys."""

    _name = "internship.submission"
    _description = "Final Report Attempt"
    _order = "submitted_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Submission Reference", required=True, default="New")
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
    title = fields.Char(string="Title")
    due_date = fields.Date(string="Deadline", tracking=True, index=True)
    submitted_date = fields.Date(string="Submitted Date", tracking=True)
    document = fields.Binary(string="Submitted Document", attachment=True)
    document_filename = fields.Char(string="Document Filename")
    document_url = fields.Char(string="Document URL")
    # Keys kept from v1 and relabelled; "failed" added in 19.0.2.
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("approved", "Marked - Pass"),
            ("rejected", "Marked - Fail"),
            ("returned", "Resubmission due"),
            ("completed", "Completed"),
            ("failed", "Failed (final)"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )
    evaluation_score = fields.Float(string="Grade (numeric)", digits=(3, 1))
    supervisor_feedback = fields.Text(string="Supervisor Feedback")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True, tracking=True)

    # v2
    placement_id = fields.Many2one("internship.placement", index=True, ondelete="restrict", tracking=True)
    internship_company_id = fields.Many2one(
        related="placement_id.internship_company_id", store=True, index=True, string="Placement Company"
    )
    university_id = fields.Many2one(related="placement_id.university_id", store=True, index=True)
    attempt_no = fields.Integer(string="Attempt", default=1, required=True)
    is_late = fields.Boolean(compute="_compute_is_late", store=True, index=True)
    report_title = fields.Char()
    marker_id = fields.Many2one("res.users", string="Marker", tracking=True)
    grade = fields.Char(help="e.g. '72 (First)'", tracking=True)
    rubric_score_ids = fields.One2many("internship.rubric.score", "submission_id", string="Rubric")
    rubric_total = fields.Float(compute="_compute_rubric_total", store=True)
    feedback = fields.Html()
    marked_date = fields.Date(tracking=True, copy=False)
    result = fields.Selection([("pass", "Pass"), ("fail", "Fail")], tracking=True, copy=False)
    resubmission_allowed = fields.Boolean(readonly=True, copy=False)
    resubmission_deadline = fields.Date(readonly=True, copy=False)
    next_attempt_id = fields.Many2one("internship.submission", readonly=True, copy=False)
    released_to_student = fields.Boolean(tracking=True, copy=False)
    release_date = fields.Date(copy=False)

    _attempt_positive = models.Constraint("CHECK(attempt_no > 0)", "The attempt number must be positive.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            placement = self.env["internship.placement"].browse(vals.get("placement_id"))
            if placement:
                vals.setdefault("student_id", placement.student_id.id)
                vals.setdefault("opportunity_id", placement.opportunity_id.id)
            if vals.get("name", "New") == "New" and placement:
                vals["name"] = self.env._(
                    "%(placement)s report attempt %(n)s", placement=placement.name, n=vals.get("attempt_no", 1)
                )
        return super().create(vals_list)

    @api.depends("due_date", "submitted_date")
    def _compute_is_late(self):
        today = fields.Date.context_today(self)
        for attempt in self:
            if not attempt.due_date:
                attempt.is_late = False
            elif attempt.submitted_date:
                attempt.is_late = attempt.submitted_date > attempt.due_date
            else:
                attempt.is_late = today > attempt.due_date

    @api.depends("rubric_score_ids.score")
    def _compute_rubric_total(self):
        for attempt in self:
            attempt.rubric_total = sum(attempt.rubric_score_ids.mapped("score"))

    def action_load_rubric(self):
        """Fill the rubric from the programme's criteria (plus shared ones)."""
        for attempt in self:
            program = attempt.placement_id.program_id
            criteria = (
                self.env["internship.rubric.criterion"].search(
                    ["|", ("program_id", "=", program.id), ("program_id", "=", False)]
                )
                if program
                else self.env["internship.rubric.criterion"].search([("program_id", "=", False)])
            )
            if program.rubric_criterion_ids:
                criteria = program.rubric_criterion_ids
            existing = attempt.rubric_score_ids.criterion_id
            attempt.write({"rubric_score_ids": [(0, 0, {"criterion_id": c.id}) for c in criteria if c not in existing]})
        return True

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        for attempt in self:
            if attempt.status not in ("draft", "returned"):
                raise UserError(self.env._("This report has already been submitted."))
        self.write({"status": "submitted", "submitted_date": fields.Date.context_today(self)})
        for attempt in self.filtered("placement_id"):
            schedule_activity_once(
                attempt,
                attempt.marker_id or attempt.placement_id.tutor_id or default_coordinator(self.env),
                self.env._("Mark final report %(name)s", name=attempt.name),
            )
        return True

    def action_review(self):
        return self.write({"status": "under_review"})

    def _check_markable(self):
        for attempt in self:
            if attempt.status not in ("submitted", "under_review"):
                raise UserError(self.env._("Only submitted reports can be marked."))
        return True

    def action_mark_pass(self):
        self._check_markable()
        self.write(
            {
                "status": "approved",
                "result": "pass",
                "marked_date": fields.Date.context_today(self),
                "marker_id": self.env.user.id,
            }
        )
        return True

    def action_mark_fail(self):
        self._check_markable()
        today = fields.Date.context_today(self)
        for attempt in self:
            attempt.write({"result": "fail", "marked_date": today, "marker_id": self.env.user.id})
            program = attempt.placement_id.program_id
            max_attempts = program._get_rule("max_report_attempts")
            if attempt.placement_id and attempt.attempt_no < max_attempts:
                deadline = today + relativedelta(days=program._get_rule("resubmission_days"))
                next_attempt = attempt.copy(
                    {
                        "attempt_no": attempt.attempt_no + 1,
                        "due_date": deadline,
                        "status": "returned",
                        "name": "New",
                        "submitted_date": False,
                        "document": False,
                        "document_filename": False,
                        "grade": False,
                        "feedback": False,
                    }
                )
                attempt.write(
                    {
                        "status": "rejected",
                        "resubmission_allowed": True,
                        "resubmission_deadline": deadline,
                        "next_attempt_id": next_attempt.id,
                    }
                )
            else:
                attempt.status = "failed"
                if attempt.placement_id.stage_code == "completion":
                    attempt.placement_id._mark_failed()
                    attempt.placement_id.completion_id._set_final_result("failed")
        return True

    # Kept for pre-v2 buttons
    def action_approve(self):
        return self.action_mark_pass() if self.filtered("placement_id") else self.write({"status": "approved"})

    def action_reject(self):
        return self.action_mark_fail() if self.filtered("placement_id") else self.write({"status": "rejected"})

    def action_complete(self):
        return self.write({"status": "completed"})

    def action_release(self):
        if self.filtered(lambda a: not a.result):
            raise UserError(self.env._("Mark the report before releasing the result."))
        return self.write({"released_to_student": True, "release_date": fields.Date.context_today(self)})

    @api.model
    def _cron_deadlines(self):
        """Refresh lateness; flag the tutor when a deadline passed without a submission."""
        today = fields.Date.context_today(self)
        overdue = self.search(
            [("due_date", "<", today), ("submitted_date", "=", False), ("status", "in", ("draft", "returned"))]
        )
        if overdue:
            self.env.add_to_compute(self._fields["is_late"], overdue)
            overdue.flush_recordset(["is_late"])
        for attempt in overdue.filtered("placement_id"):
            schedule_activity_once(
                attempt.placement_id,
                attempt.placement_id.tutor_id or attempt.placement_id.user_id or default_coordinator(self.env),
                self.env._("Final report overdue (attempt %(n)s)", n=attempt.attempt_no),
            )
        return overdue
