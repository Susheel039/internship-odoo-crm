from odoo import api, fields, models
from odoo.exceptions import UserError


class InternshipDocumentRequestLine(models.Model):
    _name = "internship.document.request.line"
    _description = "Requested Document"
    _order = "request_id, mandatory desc, id"

    request_id = fields.Many2one("internship.document.request", required=True, index=True, ondelete="cascade")
    placement_id = fields.Many2one(related="request_id.placement_id", store=True, index=True)
    document_type_id = fields.Many2one("internship.document.type", required=True, string="Document Type")
    description = fields.Char()
    mandatory = fields.Boolean(default=True)
    attachment_id = fields.Many2one("ir.attachment", string="File")
    uploaded_date = fields.Datetime(readonly=True, copy=False)
    uploaded_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    accepted = fields.Boolean(readonly=True, copy=False)
    rejection_note = fields.Char(copy=False)
    document_id = fields.Many2one("internship.document", readonly=True, copy=False, string="Registered Document")

    def write(self, vals):
        if vals.get("attachment_id"):
            vals.setdefault("uploaded_date", fields.Datetime.now())
            vals.setdefault("uploaded_by_id", self.env.user.id)
            vals.setdefault("accepted", False)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("attachment_id"):
                vals.setdefault("uploaded_date", fields.Datetime.now())
                vals.setdefault("uploaded_by_id", self.env.user.id)
        return super().create(vals_list)

    def action_accept(self):
        for line in self:
            if not line.attachment_id:
                raise UserError(self.env._("Upload the file before accepting it."))
            document = self.env["internship.document"].create(
                {
                    "name": line.description or line.document_type_id.name,
                    "document_type_id": line.document_type_id.id,
                    "attachment_id": line.attachment_id.id,
                    "placement_id": line.placement_id.id,
                    "student_id": line.placement_id.student_id.id,
                    "internship_company_id": line.placement_id.internship_company_id.id,
                    "res_model": line._name,
                    "res_id": line.id,
                    "state": "approved",
                }
            )
            line.write({"accepted": True, "rejection_note": False, "document_id": document.id})
        self.request_id._check_completion()
        return True

    def action_reject(self, reason=None, note=None):
        label = note or (reason.name if hasattr(reason, "name") else "") or self.env._("Please upload again.")
        self.write({"accepted": False, "attachment_id": False, "rejection_note": label})
        for line in self:
            line.request_id.message_post(
                body=self.env._("%(doc)s rejected: %(note)s", doc=line.document_type_id.name, note=label)
            )
        return True
