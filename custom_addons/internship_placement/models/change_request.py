from odoo import api, fields, models
from odoo.exceptions import UserError

AMENDMENT_TYPES = ("dates", "hours", "role")


class InternshipChangeRequest(models.Model):
    _name = "internship.change.request"
    _description = "Placement Change Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "internship.placement.link.mixin"]
    _order = "create_date desc"

    change_type = fields.Selection(
        [
            ("dates", "Dates"),
            ("line_manager", "Line manager"),
            ("hours", "Hours"),
            ("site", "Site"),
            ("role", "Role"),
        ],
        required=True,
        tracking=True,
    )
    current_value = fields.Char(compute="_compute_current_value", store=True, readonly=False)
    new_value = fields.Char(compute="_compute_new_value", store=True)
    new_date_start = fields.Date()
    new_date_end = fields.Date()
    new_line_manager_id = fields.Many2one("internship.line.manager")
    new_hours = fields.Float()
    new_site_id = fields.Many2one("internship.company.site")
    new_role_title = fields.Char()
    reason = fields.Text(required=True)
    requested_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    company_approved_by_id = fields.Many2one("res.users", readonly=True, tracking=True)
    company_approved_date = fields.Datetime(readonly=True)
    university_approved_by_id = fields.Many2one("res.users", readonly=True, tracking=True)
    university_approved_date = fields.Datetime(readonly=True)
    agreement_amendment_needed = fields.Boolean(compute="_compute_amendment_needed", store=True)
    state = fields.Selection(
        [("requested", "Requested"), ("approved", "Approved"), ("rejected", "Rejected"), ("applied", "Applied")],
        default="requested",
        required=True,
        tracking=True,
        index=True,
    )

    @api.depends("change_type", "placement_id")
    def _compute_current_value(self):
        for request in self:
            placement = request.placement_id
            request.current_value = {
                "dates": f"{placement.planned_start or ''} - {placement.planned_end or ''}",
                "line_manager": placement.line_manager_id.name or "",
                "hours": str(placement.hours_per_week or ""),
                "site": placement.site_id.name or "",
                "role": placement.role_title or "",
            }.get(request.change_type, "")

    @api.depends(
        "change_type",
        "new_date_start",
        "new_date_end",
        "new_line_manager_id",
        "new_hours",
        "new_site_id",
        "new_role_title",
    )
    def _compute_new_value(self):
        for request in self:
            request.new_value = {
                "dates": f"{request.new_date_start or ''} - {request.new_date_end or ''}",
                "line_manager": request.new_line_manager_id.name or "",
                "hours": str(request.new_hours or ""),
                "site": request.new_site_id.name or "",
                "role": request.new_role_title or "",
            }.get(request.change_type, "")

    @api.depends("change_type")
    def _compute_amendment_needed(self):
        for request in self:
            request.agreement_amendment_needed = request.change_type in AMENDMENT_TYPES

    def _check_requested(self):
        if self.filtered(lambda r: r.state != "requested"):
            raise UserError(self.env._("Only pending change requests can be approved or rejected."))

    def action_company_approve(self):
        self._check_requested()
        self.write({"company_approved_by_id": self.env.user.id, "company_approved_date": fields.Datetime.now()})
        self._approve_if_complete()
        return True

    def action_university_approve(self):
        self._check_requested()
        self.write({"university_approved_by_id": self.env.user.id, "university_approved_date": fields.Datetime.now()})
        self._approve_if_complete()
        return True

    def _approve_if_complete(self):
        done = self.filtered(lambda r: r.company_approved_by_id and r.university_approved_by_id)
        done.write({"state": "approved"})
        return done

    def action_reject(self, reason=None, note=None):
        self._check_requested()
        self.write({"state": "rejected"})
        for request in self:
            request.message_post(body=note or self.env._("Change request rejected."))
        return True

    def _placement_values(self):
        self.ensure_one()
        if self.change_type == "dates":
            values = {}
            if self.new_date_start:
                values["planned_start"] = self.new_date_start
            if self.new_date_end:
                values["planned_end"] = self.new_date_end
            return values
        return {
            "line_manager": {"line_manager_id": self.new_line_manager_id.id},
            "hours": {"hours_per_week": self.new_hours},
            "site": {"site_id": self.new_site_id.id},
            "role": {"role_title": self.new_role_title},
        }[self.change_type]

    def action_apply(self):
        for request in self:
            if request.state != "approved":
                raise UserError(self.env._("Only approved change requests can be applied."))
            values = request._placement_values()
            if not values or not any(values.values()):
                raise UserError(self.env._("Enter the new value before applying the change."))
            request.placement_id.write(values)
            request.placement_id.message_post(
                body=self.env._(
                    "Change applied (%(type)s): %(old)s → %(new)s",
                    type=dict(self._fields["change_type"].selection)[request.change_type],
                    old=request.current_value or "-",
                    new=request.new_value or "-",
                )
            )
            request.state = "applied"
            if request.agreement_amendment_needed:
                request._create_agreement_amendment()
        return True

    def _create_agreement_amendment(self):
        """Hook: internship_agreement creates an amended agreement for the placement."""
        return False
