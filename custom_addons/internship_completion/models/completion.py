from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class InternshipCompletion(models.Model):
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
    final_report = fields.Text(string="Final Report")
    evaluation_score = fields.Float(string="Evaluation Score", digits=(3, 1))
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
    )
    approved_by = fields.Many2one("res.users", string="Approved By", tracking=True)
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True, tracking=True)

    @api.constrains("start_date", "end_date", "evaluation_score")
    def _check_completion_values(self):
        for completion in self:
            if completion.start_date and completion.end_date and completion.start_date > completion.end_date:
                raise ValidationError("The internship start date cannot be after its end date.")
            if not 0 <= completion.evaluation_score <= 100:
                raise ValidationError("The evaluation score must be between 0 and 100.")

    def action_start(self):
        self._check_status("draft")
        return self.write({"status": "in_progress"})

    def action_complete(self):
        self._check_status("in_progress")
        if any(not completion.final_report for completion in self):
            raise UserError("Add the final report before completing the internship.")
        if any(completion.end_date and completion.end_date > fields.Date.context_today(self) for completion in self):
            raise UserError("An internship cannot be completed before its end date.")
        return self.write({"status": "completed", "completion_date": fields.Date.context_today(self)})

    def action_approve(self):
        self._check_status("completed")
        if any(not completion.final_report for completion in self):
            raise UserError("A final report is required before approval.")
        return self.write({
            "status": "approved",
            "certificate_issued": True,
            "approved_by": self.env.user.id,
        })

    def action_close(self):
        self._check_status("approved")
        return self.write({"status": "closed"})

    def action_print_certificate(self):
        self.ensure_one()
        if not self.certificate_issued or self.status not in ("approved", "closed"):
            raise UserError("The certificate is available after completion approval.")
        return self.env.ref("internship_completion.action_report_completion_certificate").report_action(self)

    def _check_status(self, expected_status):
        if any(completion.status != expected_status for completion in self):
            raise UserError("This action is only available when the record is %s." % expected_status.replace("_", " "))
