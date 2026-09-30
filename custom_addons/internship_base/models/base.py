from odoo import models


class Base(models.AbstractModel):
    _inherit = "base"

    def _valid_field_parameter(self, field, name):
        # `deprecated="Replaced by X in 19.0.2"` marks fields kept only so no data is lost
        # (see CONTRIBUTING.md). Odoo 19 no longer knows the attribute; accept it as metadata.
        return name == "deprecated" or super()._valid_field_parameter(field, name)
