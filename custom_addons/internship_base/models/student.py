from odoo import fields, models


class InternshipStudent(models.Model):
    _name = "internship.student"
    _description = "Student"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Student Name", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    student_id = fields.Char(string="Student ID", tracking=True)
    university_id = fields.Many2one(
        "internship.university",
        string="University",
        ondelete="restrict",
        tracking=True,
    )
    email = fields.Char(string="Email")
    phone = fields.Char(string="Phone")
    course = fields.Char(string="Course")
    department = fields.Char(string="Department")
    graduation_year = fields.Integer(string="Graduation Year")
    application_ids = fields.One2many("internship.application", "student_id", string="Applications")
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text(string="Notes")
