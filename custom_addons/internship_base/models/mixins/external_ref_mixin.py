from odoo import fields, models


class InternshipExternalRefMixin(models.AbstractModel):
    """Reference of the record in an external system (Vapi, n8n, ...)."""

    _name = "internship.external.ref.mixin"
    _description = "Internship External Reference Mixin"

    external_source = fields.Char(index=True, copy=False, help="System the record came from, e.g. 'vapi' or 'n8n'.")
    external_ref = fields.Char(string="External Reference", index=True, copy=False)

    _external_ref_unique = models.Constraint(
        "unique(external_source, external_ref)",
        "This external reference is already linked to another record.",
    )

    def _find_by_external_ref(self, source, ref):
        if not source or not ref:
            return self.browse()
        return self.search([("external_source", "=", source), ("external_ref", "=", str(ref))], limit=1)
