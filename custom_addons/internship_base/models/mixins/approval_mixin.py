from odoo import fields, models


class InternshipApprovalMixin(models.AbstractModel):
    """Who approved, when, and why; plus a permission hook."""

    _name = "internship.approval.mixin"
    _description = "Internship Approval Mixin"

    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True, tracking=True, copy=False)
    approved_date = fields.Datetime(readonly=True, tracking=True, copy=False)
    approval_comment = fields.Text(copy=False)

    def _check_can_approve(self):
        """Override to raise an AccessError/UserError when the current user may not approve."""
        return True

    def _mark_approved(self, comment=None):
        self._check_can_approve()
        values = {"approved_by_id": self.env.user.id, "approved_date": fields.Datetime.now()}
        if comment:
            values["approval_comment"] = comment
        self.write(values)
        return True
