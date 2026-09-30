from odoo import api, models


class Base(models.AbstractModel):
    _inherit = "base"

    def _valid_field_parameter(self, field, name):
        # `deprecated="Replaced by X in 19.0.2"` marks fields kept only so no data is lost
        # (see CONTRIBUTING.md). Odoo 19 no longer knows the attribute; accept it as metadata.
        return name == "deprecated" or super()._valid_field_parameter(field, name)

    @api.model
    def _mail_get_company_field(self):
        # Several pre-v2 internship models have `company_id` pointing to internship.company, not
        # res.company. mail must not read it as the Odoo company (alias domains, message company).
        field_name = super()._mail_get_company_field()
        if field_name and self._fields[field_name].comodel_name != "res.company":
            return False
        return field_name
