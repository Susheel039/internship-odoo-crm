from odoo import fields, models

WORK_MODES = [("on_site", "On-site"), ("hybrid", "Hybrid"), ("remote", "Remote")]


class InternshipCompanySite(models.Model):
    _name = "internship.company.site"
    _description = "Company Site"
    _order = "company_id, name"

    name = fields.Char(required=True)
    company_id = fields.Many2one("internship.company", required=True, index=True, ondelete="cascade")
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    zip = fields.Char(string="Postcode")
    country_id = fields.Many2one("res.country", default=lambda self: self.env.ref("base.uk", raise_if_not_found=False))
    work_mode = fields.Selection(WORK_MODES, default="on_site", required=True)
    active = fields.Boolean(default=True)
