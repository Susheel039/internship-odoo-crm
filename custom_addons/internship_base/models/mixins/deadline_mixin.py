from odoo import api, fields, models


class InternshipDeadlineMixin(models.AbstractModel):
    """Due date, submission date, lateness and reminder bookkeeping."""

    _name = "internship.deadline.mixin"
    _description = "Internship Deadline Mixin"

    due_date = fields.Date(tracking=True, index=True)
    submitted_date = fields.Date(tracking=True, copy=False)
    is_late = fields.Boolean(compute="_compute_is_late", store=True, index=True)
    reminder_count = fields.Integer(default=0, copy=False)
    last_reminder_date = fields.Date(copy=False)

    @api.depends("due_date", "submitted_date")
    def _compute_is_late(self):
        today = fields.Date.context_today(self)
        for record in self:
            if not record.due_date:
                record.is_late = False
            elif record.submitted_date:
                record.is_late = record.submitted_date > record.due_date
            else:
                record.is_late = today > record.due_date

    def _refresh_lateness(self):
        """Recompute `is_late` for unsubmitted records whose deadline passed (called by crons)."""
        today = fields.Date.context_today(self)
        overdue = self.search([("due_date", "<", today), ("submitted_date", "=", False), ("is_late", "=", False)])
        if overdue:
            self.env.add_to_compute(self._fields["is_late"], overdue)
            overdue.flush_recordset(["is_late"])
        return overdue

    def _register_reminder(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.write({"reminder_count": record.reminder_count + 1, "last_reminder_date": today})
