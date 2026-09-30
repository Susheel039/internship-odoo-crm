from odoo import fields, models


class InternshipSkill(models.Model):
    _name = "internship.skill"
    _description = "Skill"
    _inherit = ["internship.lookup.mixin"]

    color = fields.Integer()
