from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class InternshipPlacement(models.Model):
    _inherit = "internship.placement"

    monthly_ids = fields.One2many("internship.attendance.monthly", "placement_id", string="Monthly Records")
    attendance_ids = fields.One2many("internship.attendance", "placement_id", string="Daily Attendance")
    performance_ids = fields.One2many("internship.performance", "placement_id", string="Performance Reviews")
    meeting_ids = fields.One2many("internship.meeting", "placement_id", string="Meetings")
    exit_meeting_id = fields.Many2one("internship.meeting", readonly=True, copy=False)
    monthly_count = fields.Integer(compute="_compute_monitoring_counts")
    meeting_count = fields.Integer(compute="_compute_monitoring_counts")

    def _compute_monitoring_counts(self):
        for placement in self:
            placement.monthly_count = len(placement.monthly_ids)
            placement.meeting_count = len(placement.meeting_ids)

    @api.depends("monthly_ids.state", "monthly_ids.tripartite_triggered", "meeting_ids.state")
    def _compute_risk_flag(self):
        return super()._compute_risk_flag()

    def _get_risk_signals(self):
        signals = super()._get_risk_signals()
        if self.is_closed:
            return signals
        escalated = self.monthly_ids.filtered(
            lambda m: m.tripartite_triggered and m.meeting_id.state not in ("completed", "cancelled")
        )
        if escalated:
            signals.append(("red", escalated[0].trigger_reason or self.env._("Tripartite meeting pending")))
        if self.monthly_ids.filtered(lambda m: m.state == "late"):
            signals.append(("amber", self.env._("Late monthly record")))
        return signals

    def _on_started(self):
        result = super()._on_started()
        Monthly = self.env["internship.attendance.monthly"]
        for placement in self:
            Monthly._ensure_for(placement, placement.actual_start or fields.Date.context_today(self))
        return result

    def _create_review_meeting(self):
        super()._create_review_meeting()
        meetings = self.env["internship.meeting"]
        for placement in self:
            meeting = meetings.create(
                {
                    "placement_id": placement.id,
                    "meeting_type": "university_company",
                    "title": self.env._("University-company meeting: %(name)s", name=placement.name),
                    "meeting_date": fields.Datetime.now() + relativedelta(days=3),
                }
            )
            meeting._add_default_attendees()
            meetings |= meeting
        if len(meetings) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "internship.meeting",
                "res_id": meetings.id,
                "view_mode": "form",
            }
        return True

    def _create_exit_meeting(self):
        super()._create_exit_meeting()
        for placement in self:
            meeting = self.env["internship.meeting"].create(
                {
                    "placement_id": placement.id,
                    "meeting_type": "exit",
                    "title": self.env._("Exit meeting: %(name)s", name=placement.name),
                    "meeting_date": fields.Datetime.now() + relativedelta(days=5),
                    "trigger_reason": placement.termination_reason_id.name,
                }
            )
            meeting._add_default_attendees()
            placement.exit_meeting_id = meeting
        return True

    def action_view_monthly(self):
        return self._action_related("internship.attendance.monthly", self.env._("Monthly Records"))

    def action_view_meetings(self):
        return self._action_related("internship.meeting", self.env._("Meetings"))
