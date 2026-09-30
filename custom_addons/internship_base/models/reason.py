from odoo import fields, models

REASON_TYPES = [
    ("rejection", "Application rejection"),
    ("decline", "Offer declined by student"),
    ("withdrawal", "Withdrawal"),
    ("university_rejection", "University rejection"),
    ("termination", "Termination"),
    ("document_rejection", "Document rejection"),
    ("company_rejection", "Company vetting rejection"),
    ("hold", "Placement on hold"),
]


class InternshipReason(models.Model):
    _name = "internship.reason"
    _description = "Internship Reason"
    _inherit = ["internship.lookup.mixin"]

    reason_type = fields.Selection(REASON_TYPES, required=True, index=True)

    _code_unique = models.Constraint(
        "unique(reason_type, code)",
        "The code must be unique per reason type.",
    )
