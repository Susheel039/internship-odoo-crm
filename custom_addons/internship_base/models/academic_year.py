from odoo import api, fields, models
from odoo.exceptions import ValidationError


class InternshipAcademicYear(models.Model):
    _name = "internship.academic.year"
    _description = "Academic Year"
    _inherit = ["internship.lookup.mixin"]
    _order = "date_from desc"

    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for year in self:
            if year.date_from > year.date_to:
                raise ValidationError(self.env._("An academic year must start before it ends."))

    @api.model
    def _get_for_date(self, date=None):
        date = date or fields.Date.context_today(self)
        return self.search([("date_from", "<=", date), ("date_to", ">=", date)], limit=1)
