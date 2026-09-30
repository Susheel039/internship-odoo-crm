from odoo import api, fields, models
from odoo.exceptions import UserError

SOURCE_CHANNELS = [
    ("portal", "Portal"),
    ("referral", "Referral"),
    ("university", "University"),
    ("campus_event", "Campus event"),
    ("vapi_inbound", "Voice AI (inbound)"),
    ("vapi_outbound", "Voice AI (outbound)"),
    ("n8n", "n8n automation"),
    ("other", "Other"),
]

# Internship pipeline stage codes -> crm.stage xml ids (with name fallback)
STAGES = {
    "new": ("crm.stage_lead1", "New"),
    "contacted": ("internship_crm.stage_contacted", "Contacted"),
    "qualified": ("crm.stage_lead2", "Qualified"),
    "interview": ("internship_crm.stage_interview", "Interview"),
    "won": ("crm.stage_lead4", "Won"),
}


class CrmLead(models.Model):
    _inherit = "crm.lead"

    lead_category = fields.Selection(
        [("student", "Student"), ("company", "Company"), ("university", "University"), ("other", "Other")],
        string="Internship Category",
        index=True,
        tracking=True,
    )
    student_id = fields.Many2one("internship.student", index=True, tracking=True, ondelete="set null")
    internship_company_id = fields.Many2one(
        "internship.company", string="Internship Company", index=True, tracking=True, ondelete="set null"
    )
    university_id = fields.Many2one("internship.university", index=True, tracking=True, ondelete="set null")
    internship_opportunity_id = fields.Many2one(
        "internship.opportunity", string="Internship Opportunity", index=True, ondelete="set null"
    )
    placement_id = fields.Many2one("internship.placement", index=True, ondelete="set null")
    source_channel = fields.Selection(SOURCE_CHANNELS, index=True, tracking=True)

    # Voice AI outcome
    interest_level = fields.Selection([("cold", "Cold"), ("warm", "Warm"), ("hot", "Hot")], tracking=True)
    callback_datetime = fields.Datetime(string="Callback At", tracking=True)

    # UK contact compliance (PECR / TPS / UK GDPR)
    do_not_call = fields.Boolean(string="Do Not Call", tracking=True)
    tps_checked = fields.Boolean(string="TPS/CTPS Checked", tracking=True)
    tps_checked_date = fields.Date(string="TPS Check Date")
    consent_to_contact = fields.Boolean(tracking=True)
    consent_date = fields.Datetime()
    recording_consent = fields.Boolean(string="Call Recording Consent")

    legacy_internship_lead_id = fields.Many2one(
        "internship.crm.lead", string="Legacy Lead", readonly=True, copy=False, index=True
    )

    @api.model
    def _internship_stage(self, code):
        xmlid, name = STAGES[code]
        stage = self.env.ref(xmlid, raise_if_not_found=False)
        if not stage:
            stage = self.env["crm.stage"].search([("name", "=ilike", name)], limit=1)
        if not stage:
            stage = self.env["crm.stage"].create({"name": name, "is_won": code == "won"})
        return stage

    @api.onchange("consent_to_contact")
    def _onchange_consent_to_contact(self):
        if self.consent_to_contact and not self.consent_date:
            self.consent_date = fields.Datetime.now()

    def _contact_partner(self, is_company=False):
        """Existing partner of the lead, or a new one built from its contact details."""
        self.ensure_one()
        if self.partner_id and bool(self.partner_id.is_company) == is_company:
            return self.partner_id
        name = (
            (self.partner_name if is_company else self.contact_name)
            or self.partner_name
            or self.contact_name
            or self.name
        )
        partner = self.env["res.partner"].create(
            {
                "name": name,
                "is_company": is_company,
                "email": self.email_from,
                "phone": self.phone,
                "country_id": self.country_id.id or self.env.ref("base.uk").id,
            }
        )
        if not self.partner_id:
            self.partner_id = partner
        return partner

    def action_convert_to_student(self):
        self.ensure_one()
        if self.student_id:
            raise UserError(self.env._("This lead is already linked to a student."))
        partner = self._contact_partner(is_company=False)
        student = self.env["internship.student"].create(
            {
                "name": partner.name,
                "partner_id": partner.id,
                "email": partner.email,
                "phone": partner.phone,
                "university_id": self.university_id.id,
                "gdpr_consent": self.consent_to_contact,
                "gdpr_consent_date": self.consent_date and self.consent_date.date(),
            }
        )
        self.write({"student_id": student.id, "lead_category": "student"})
        self.message_post(body=self.env._("Converted to student %(name)s.", name=student.name))
        return {
            "type": "ir.actions.act_window",
            "res_model": "internship.student",
            "res_id": student.id,
            "view_mode": "form",
        }

    def action_convert_to_company(self):
        self.ensure_one()
        if self.internship_company_id:
            raise UserError(self.env._("This lead is already linked to a company."))
        partner = self._contact_partner(is_company=True)
        company = self.env["internship.company"].create(
            {
                "name": partner.name,
                "partner_id": partner.id,
                "contact_person": self.contact_name,
                "contact_email": self.email_from or partner.email,
                "phone": self.phone or partner.phone,
                "registration_source": "invited_by_university",
                "invited_by_id": self.env.user.id,
            }
        )
        self.write({"internship_company_id": company.id, "lead_category": "company"})
        if company.contact_email:
            company.action_send_invite()
        self.message_post(body=self.env._("Converted to company %(name)s and invited.", name=company.name))
        return {
            "type": "ir.actions.act_window",
            "res_model": "internship.company",
            "res_id": company.id,
            "view_mode": "form",
        }
