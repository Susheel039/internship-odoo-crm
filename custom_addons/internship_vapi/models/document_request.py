from odoo import models


class InternshipDocumentRequest(models.Model):
    _inherit = "internship.document.request"

    def action_chase_by_phone(self):
        self.env["internship.call.log"].action_queue_call("document_chase", self)
        return self.env["crm.lead"]._notify_queued()
