from odoo import api, fields, models


class InternshipUniversityContact(models.Model):
    _name = "internship.university.contact"
    _description = "University Contact"
    _order = "university_id, role, name"

    university_id = fields.Many2one(
        "internship.university", required=True, index=True, ondelete="cascade", string="University"
    )
    partner_id = fields.Many2one("res.partner", required=True, index=True, ondelete="restrict", string="Contact")
    name = fields.Char(related="partner_id.name", store=True)
    user_id = fields.Many2one("res.users", index=True, string="User")
    role = fields.Selection(
        [("coordinator", "Placement coordinator"), ("tutor", "Academic tutor"), ("admin", "Administrator")],
        required=True,
        default="coordinator",
        index=True,
    )
    email = fields.Char(related="partner_id.email", readonly=False)
    phone = fields.Char(related="partner_id.phone", readonly=False)
    active = fields.Boolean(default=True)
    assigned_student_count = fields.Integer(compute="_compute_assigned_student_count")

    @api.depends("user_id")
    def _compute_assigned_student_count(self):
        counts = dict(
            self.env["internship.student"]._read_group(
                [("academic_tutor_id", "in", self.user_id.ids)], ["academic_tutor_id"], ["__count"]
            )
        )
        for contact in self:
            contact.assigned_student_count = counts.get(contact.user_id, 0) if contact.user_id else 0
