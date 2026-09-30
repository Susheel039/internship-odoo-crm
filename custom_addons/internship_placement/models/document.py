from odoo import api, fields, models
from odoo.exceptions import UserError


class InternshipDocument(models.Model):
    """Central register of every document in the platform, with versions and expiry."""

    _name = "internship.document"
    _description = "Internship Document"
    _inherit = ["mail.thread"]
    _order = "upload_date desc, id desc"

    name = fields.Char(required=True, tracking=True)
    document_type_id = fields.Many2one("internship.document.type", required=True, index=True, tracking=True)
    attachment_id = fields.Many2one("ir.attachment", required=True, ondelete="restrict", string="Attachment")
    version = fields.Integer(default=1, readonly=True, copy=False)
    previous_version_id = fields.Many2one("internship.document", readonly=True, copy=False, index=True)

    placement_id = fields.Many2one("internship.placement", index=True, ondelete="restrict")
    student_id = fields.Many2one("internship.student", index=True, ondelete="restrict")
    internship_company_id = fields.Many2one(
        "internship.company", string="Internship Company", index=True, ondelete="restrict"
    )
    res_model = fields.Char(string="Res Model", index=True)
    res_id = fields.Integer(string="Res ID")

    uploaded_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    upload_date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    expiry_date = fields.Date(tracking=True, index=True)
    access = fields.Selection(
        [
            ("university", "University only"),
            ("company", "University and company"),
            ("student", "University and student"),
            ("all", "Everyone on the placement"),
        ],
        default="all",
        required=True,
    )
    state = fields.Selection(
        [
            ("uploaded", "Uploaded"),
            ("under_review", "Under review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("expired", "Expired"),
        ],
        default="uploaded",
        required=True,
        tracking=True,
        index=True,
    )

    @api.constrains("document_type_id", "expiry_date")
    def _check_expiry(self):
        for document in self:
            if document.document_type_id.requires_expiry and not document.expiry_date and document.state == "approved":
                raise UserError(
                    self.env._("%(type)s documents need an expiry date.", type=document.document_type_id.name)
                )

    def action_approve(self):
        return self.write({"state": "approved"})

    def action_reject(self, reason=None, note=None):
        self.write({"state": "rejected"})
        if note or reason:
            for document in self:
                document.message_post(body=note or reason.name)
        return True

    def action_new_version(self):
        """Open a copy for uploading the next version; the old one stays in the register."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_name": self.name,
                "default_document_type_id": self.document_type_id.id,
                "default_placement_id": self.placement_id.id,
                "default_student_id": self.student_id.id,
                "default_internship_company_id": self.internship_company_id.id,
                "default_previous_version_id": self.id,
                "default_access": self.access,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            previous = self.browse(vals.get("previous_version_id")) if vals.get("previous_version_id") else None
            if previous:
                vals["version"] = previous.version + 1
        return super().create(vals_list)

    @api.model
    def _cron_expire(self):
        today = fields.Date.context_today(self)
        expired = self.search([("expiry_date", "<", today), ("state", "in", ("uploaded", "under_review", "approved"))])
        expired.write({"state": "expired"})
        return expired
