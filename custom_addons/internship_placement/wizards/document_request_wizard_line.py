from odoo import api, fields, models


class InternshipDocumentRequestWizardLine(models.TransientModel):
    _name = "internship.document.request.wizard.line"
    _description = "Request Documents: Line"

    wizard_id = fields.Many2one("internship.document.request.wizard", required=True, ondelete="cascade")
    document_type_id = fields.Many2one("internship.document.type", required=True)
    description = fields.Char()
    mandatory = fields.Boolean(default=True)

    @api.onchange("document_type_id")
    def _onchange_document_type_id(self):
        if self.document_type_id and not self.description:
            self.description = self.document_type_id.name
