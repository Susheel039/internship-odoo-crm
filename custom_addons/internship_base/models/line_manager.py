from odoo import fields, models


class InternshipLineManager(models.Model):
    _name = "internship.line.manager"
    _description = "Line Manager"
    _order = "name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True, tracking=True)
    name = fields.Char(related="partner_id.name", store=True)
    user_id = fields.Many2one("res.users", string="User", index=True, tracking=True)
    company_id = fields.Many2one(
        "internship.company", string="Company", required=True, index=True, ondelete="restrict", tracking=True
    )
    job_title = fields.Char()
    email = fields.Char(related="partner_id.email", readonly=False)
    phone = fields.Char(related="partner_id.phone", readonly=False)
    can_approve_attendance = fields.Boolean(default=True, tracking=True)
    can_sign_agreement = fields.Boolean(tracking=True)
    can_issue_certificate = fields.Boolean(tracking=True)
    active = fields.Boolean(default=True, tracking=True)
