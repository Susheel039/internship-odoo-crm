from odoo import fields, models


class InternshipCompany(models.Model):
    _name = "internship.company"
    _description = "Company"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Company Name", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    company_registration_number = fields.Char(string="Registration Number")
    industry = fields.Char(string="Industry")
    contact_person = fields.Char(string="Contact Person")
    contact_email = fields.Char(string="Contact Email")
    phone = fields.Char(string="Phone")
    user_ids = fields.Many2many("res.users", string="Company Users")
    opportunity_ids = fields.One2many("internship.opportunity", "company_id", string="Opportunities")
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text(string="Notes")
