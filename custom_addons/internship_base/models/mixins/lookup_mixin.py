from odoo import fields, models


class InternshipLookupMixin(models.AbstractModel):
    """Common shape of the configurable lookup tables (reasons, document types, ...)."""

    _name = "internship.lookup.mixin"
    _description = "Internship Lookup Value"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Stable technical key used by automations and integrations.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(translate=True)

    _code_unique = models.Constraint("unique(code)", "The code must be unique.")
