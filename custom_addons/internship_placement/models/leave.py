from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class InternshipLeave(models.Model):
    _name = "internship.leave"
    _description = "Internship Leave"
    _inherit = ["mail.thread", "internship.placement.link.mixin", "internship.approval.mixin"]
    _order = "date_from desc"

    leave_type = fields.Selection(
        [("annual", "Annual leave"), ("sick", "Sickness"), ("university", "University commitment"), ("other", "Other")],
        required=True,
        default="annual",
        tracking=True,
    )
    date_from = fields.Date(required=True, tracking=True)
    date_to = fields.Date(required=True, tracking=True)
    days = fields.Float(compute="_compute_days", store=True, help="Working days (Monday to Friday).")
    requested_date = fields.Date(default=fields.Date.context_today)
    evidence_attachment_id = fields.Many2one("ir.attachment", string="Evidence Attachment")
    notes = fields.Text()
    state = fields.Selection(
        [("requested", "Requested"), ("approved", "Approved"), ("rejected", "Rejected")],
        default="requested",
        required=True,
        tracking=True,
        index=True,
    )

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for leave in self:
            if leave.date_from > leave.date_to:
                raise ValidationError(self.env._("Leave must start before it ends."))

    @api.depends("date_from", "date_to")
    def _compute_days(self):
        for leave in self:
            leave.days = leave._working_days_between(leave.date_from, leave.date_to)

    @staticmethod
    def _working_days_between(start, end):
        if not start or not end or end < start:
            return 0
        return sum(1 for offset in range((end - start).days + 1) if (start + timedelta(days=offset)).weekday() < 5)

    def _overlap_days(self, start, end):
        """Working days of these leaves inside [start, end]."""
        total = 0.0
        for leave in self:
            lo, hi = max(leave.date_from, start), min(leave.date_to, end)
            total += self._working_days_between(lo, hi)
        return total

    def action_approve(self):
        if self.filtered(lambda leave: leave.state != "requested"):
            raise UserError(self.env._("Only requested leave can be approved."))
        self._mark_approved()
        return self.write({"state": "approved"})

    def action_reject(self, reason=None, note=None):
        self.write({"state": "rejected"})
        if note:
            for leave in self:
                leave.message_post(body=note)
        return True
