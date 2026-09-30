from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.exceptions import UserError


class InternshipDocumentRequestWizard(models.TransientModel):
    _name = "internship.document.request.wizard"
    _description = "Request Documents"

    placement_id = fields.Many2one("internship.placement", required=True)
    requested_from = fields.Selection(
        [("student", "Student"), ("company", "Company"), ("both", "Student and company")],
        default="both",
        required=True,
    )
    due_date = fields.Date(required=True, default=lambda self: fields.Date.context_today(self) + relativedelta(days=7))
    notes = fields.Text()
    line_ids = fields.One2many("internship.document.request.wizard.line", "wizard_id", string="Documents")

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(self.env._("Add at least one document to request."))
        placement = self.placement_id
        request = self.env["internship.document.request"].create(
            {
                "placement_id": placement.id,
                "round_no": placement.review_round,
                "requested_from": self.requested_from,
                "due_date": self.due_date,
                "notes": self.notes,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "document_type_id": line.document_type_id.id,
                            "description": line.description,
                            "mandatory": line.mandatory,
                        },
                    )
                    for line in self.line_ids
                ],
            }
        )
        if placement.stage_code in ("under_review", "meeting"):
            placement._move_to("more_docs", ("under_review", "meeting"))
        request.action_send()
        return {
            "type": "ir.actions.act_window",
            "res_model": "internship.document.request",
            "res_id": request.id,
            "view_mode": "form",
        }
