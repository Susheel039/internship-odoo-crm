from odoo import fields, models


class InternshipDocumentType(models.Model):
    _name = "internship.document.type"
    _description = "Internship Document Type"
    _inherit = ["internship.lookup.mixin"]

    applies_to = fields.Selection(
        [("student", "Student"), ("company", "Company"), ("placement", "Placement")],
        required=True,
        default="placement",
        index=True,
    )
    requires_expiry = fields.Boolean(help="Documents of this type must carry an expiry date.")
