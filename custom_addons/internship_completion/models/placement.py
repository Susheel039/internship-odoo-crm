from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class InternshipPlacement(models.Model):
    _inherit = "internship.placement"

    report_attempt_ids = fields.One2many("internship.submission", "placement_id", string="Report Attempt")
    evaluation_ids = fields.One2many("internship.company.evaluation", "placement_id", string="Evaluation")
    certificate_ids = fields.One2many("internship.certificate", "placement_id", string="Certificates")
    feedback_ids = fields.One2many("internship.student.feedback", "placement_id", string="Feedback")
    completion_ids = fields.One2many("internship.completion", "placement_id", string="Completion Records")
    completion_id = fields.Many2one("internship.completion", compute="_compute_completion_id", string="Completion")
    report_attempt_count = fields.Integer(compute="_compute_completion_id")
    evaluation_count = fields.Integer(compute="_compute_completion_id")
    feedback_count = fields.Integer(compute="_compute_completion_id")

    @api.depends("completion_ids", "report_attempt_ids", "evaluation_ids", "feedback_ids")
    def _compute_completion_id(self):
        for placement in self:
            placement.completion_id = placement.completion_ids[:1]
            placement.report_attempt_count = len(placement.report_attempt_ids)
            placement.evaluation_count = len(placement.evaluation_ids)
            placement.feedback_count = len(placement.feedback_ids)

    @api.depends("report_attempt_ids.is_late", "report_attempt_ids.status")
    def _compute_risk_flag(self):
        return super()._compute_risk_flag()

    def _get_risk_signals(self):
        signals = super()._get_risk_signals()
        if not self.is_closed and self.report_attempt_ids.filtered(
            lambda a: a.is_late and a.status in ("draft", "returned")
        ):
            signals.append(("amber", self.env._("Final report overdue")))
        return signals

    def _on_completion_started(self):
        result = super()._on_completion_started()
        today = fields.Date.context_today(self)
        for placement in self:
            if not placement.report_attempt_ids:
                end = placement.actual_end or placement.planned_end or today
                deadline = max(end, today) + relativedelta(days=placement.program_id._get_rule("report_deadline_days"))
                self.env["internship.submission"].create(
                    {"placement_id": placement.id, "attempt_no": 1, "due_date": deadline, "status": "draft"}
                )
            if not placement.completion_ids:
                start = placement.actual_start or placement.planned_start
                end = placement.actual_end or placement.planned_end
                self.env["internship.completion"].create(
                    {
                        "name": self.env._("%(name)s completion", name=placement.name),
                        "placement_id": placement.id,
                        "student_id": placement.student_id.id,
                        "opportunity_id": placement.opportunity_id.id,
                        "start_date": start,
                        "end_date": max(start, end) if start and end else end,
                        "status": "in_progress",
                    }
                )
        return result

    def action_view_report_attempts(self):
        return self._action_related("internship.submission", self.env._("Report Attempts"))

    def action_view_evaluations(self):
        return self._action_related("internship.company.evaluation", self.env._("Evaluations"))

    def action_view_feedback(self):
        return self._action_related("internship.student.feedback", self.env._("Feedback"))

    def action_open_completion(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "internship.completion",
            "res_id": self.completion_id.id,
            "view_mode": "form",
        }
