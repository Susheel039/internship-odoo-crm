from odoo import fields, models


class InternshipDocumentRequest(models.Model):
    _inherit = "internship.document.request"

    meeting_id = fields.Many2one("internship.meeting", index=True, ondelete="set null", string="Meeting")
