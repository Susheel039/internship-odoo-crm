from odoo import fields, models


class InternshipSector(models.Model):
    _name = "internship.sector"
    _description = "Sector"
    _inherit = ["internship.lookup.mixin"]

    color = fields.Integer()
