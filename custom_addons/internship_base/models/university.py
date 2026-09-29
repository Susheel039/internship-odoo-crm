from odoo import fields, models


class InternshipUniversity(models.Model):
    _name = "internship.university"
    _description = "University"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="University Name", required=True, tracking=True)
    code = fields.Char(string="Code", tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    contact_email = fields.Char(string="Contact Email")
    phone = fields.Char(string="Phone")
    address = fields.Text(string="Address")
    active = fields.Boolean(default=True, tracking=True)
    user_ids = fields.Many2many("res.users", string="Users")
    student_ids = fields.One2many("internship.student", "university_id", string="Students")
    notes = fields.Text(string="Notes")
