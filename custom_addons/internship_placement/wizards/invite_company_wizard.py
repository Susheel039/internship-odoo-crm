from odoo import api, fields, models
from odoo.exceptions import UserError


class InternshipInviteCompanyWizard(models.TransientModel):
    """Self-sourced placement: the student found the company; invite it and open the placement."""

    _name = "internship.invite.company.wizard"
    _description = "Invite Company (Self-sourced Placement)"

    student_id = fields.Many2one("internship.student", required=True)
    existing_company_id = fields.Many2one(
        "internship.company", string="Existing Company", help="Leave empty to register a new company."
    )
    company_name = fields.Char()
    company_registration_number = fields.Char(string="Companies House No.")
    contact_name = fields.Char()
    contact_email = fields.Char()
    contact_phone = fields.Char()
    role_title = fields.Char(required=True)
    planned_start = fields.Date()
    planned_end = fields.Date()
    hours_per_week = fields.Float(default=37.5)
    send_invite = fields.Boolean(default=True)

    @api.onchange("existing_company_id")
    def _onchange_existing_company_id(self):
        if self.existing_company_id:
            self.company_name = self.existing_company_id.name
            self.contact_email = self.existing_company_id.contact_email

    def _get_or_create_company(self):
        if self.existing_company_id:
            return self.existing_company_id
        if not self.company_name or not self.contact_email:
            raise UserError(self.env._("A company name and contact e-mail are needed to invite a new company."))
        partner = self.env["res.partner"].create(
            {
                "name": self.company_name,
                "is_company": True,
                "email": self.contact_email,
                "phone": self.contact_phone,
                "country_id": self.env.ref("base.uk").id,
            }
        )
        return self.env["internship.company"].create(
            {
                "name": self.company_name,
                "partner_id": partner.id,
                "company_registration_number": self.company_registration_number,
                "contact_person": self.contact_name,
                "contact_email": self.contact_email,
                "phone": self.contact_phone,
                "registration_source": "invited_by_student",
                "invited_by_id": self.env.user.id,
            }
        )

    def action_confirm(self):
        self.ensure_one()
        company = self._get_or_create_company()
        placement = self.env["internship.placement"].create(
            {
                "student_id": self.student_id.id,
                "internship_company_id": company.id,
                "placement_source": "self_sourced",
                "role_title": self.role_title,
                "planned_start": self.planned_start,
                "planned_end": self.planned_end,
                "hours_per_week": self.hours_per_week,
                "form_requested_by_id": self.env.user.id,
                "form_requested_date": fields.Date.context_today(self),
                "form_contact_email": self.contact_email or company.contact_email,
            }
        )
        if self.send_invite and not company.invite_accepted:
            company.action_send_invite()
        placement._request_company_form()
        return {
            "type": "ir.actions.act_window",
            "res_model": "internship.placement",
            "res_id": placement.id,
            "view_mode": "form",
        }
