import hmac
import secrets

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from ..services.activity import default_coordinator, schedule_activity_once


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
    company_registration_number = fields.Char(string="Companies House No.", tracking=True)
    industry = fields.Char(string="Industry")
    contact_person = fields.Char(string="HR Contact")
    contact_email = fields.Char(string="Contact Email")
    phone = fields.Char(string="Phone")
    user_ids = fields.Many2many("res.users", string="Company Users")
    opportunity_ids = fields.One2many("internship.opportunity", "company_id", string="Opportunities")
    active = fields.Boolean(default=True, tracking=True)
    notes = fields.Text(string="Notes")

    company_size = fields.Selection(
        [("1_10", "1-10"), ("11_50", "11-50"), ("51_200", "51-200"), ("201_500", "201-500"), ("500_plus", "500+")],
        string="Company Size",
    )
    website = fields.Char(related="partner_id.website", readonly=False)
    sector_ids = fields.Many2many("internship.sector", string="Sectors")
    site_ids = fields.One2many("internship.company.site", "company_id", string="Sites")
    line_manager_ids = fields.One2many("internship.line.manager", "company_id", string="Line Managers")

    # Compliance
    insurance_policy_no = fields.Char(string="Insurance Policy No.")
    insurance_expiry = fields.Date(tracking=True)
    insurance_attachment_id = fields.Many2one("ir.attachment", string="Insurance Certificate")
    risk_assessment_attachment_id = fields.Many2one("ir.attachment", string="Risk Assessment")
    risk_assessment_date = fields.Date(tracking=True)

    # Vetting / pre-approval
    vetting_state = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("expired", "Expired")],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    vetting_approved_by_id = fields.Many2one("res.users", string="Vetted By", tracking=True, copy=False)
    vetting_approved_date = fields.Date(string="Vetting Date", tracking=True, copy=False)
    approved_until = fields.Date(tracking=True, copy=False)
    vetting_rejection_reason_id = fields.Many2one(
        "internship.reason",
        string="Vetting Rejection Reason",
        domain=[("reason_type", "=", "company_rejection")],
        tracking=True,
    )
    framework_agreement_attachment_id = fields.Many2one("ir.attachment", string="Framework Agreement")

    # Registration
    registration_source = fields.Selection(
        [
            ("self_registered", "Self-registered"),
            ("invited_by_student", "Invited by student"),
            ("invited_by_university", "Invited by university"),
        ],
        default="invited_by_university",
    )
    invited_by_id = fields.Many2one("res.users", string="Invited By", copy=False)
    invite_date = fields.Datetime(copy=False)
    invite_accepted = fields.Boolean(copy=False, tracking=True)
    invite_token = fields.Char(copy=False, groups="base.group_system")

    # Signatory
    signatory_name = fields.Char()
    signatory_title = fields.Char()
    signatory_email = fields.Char()

    def action_vetting_approve(self):
        today = fields.Date.context_today(self)
        for company in self:
            company.write(
                {
                    "vetting_state": "approved",
                    "vetting_approved_by_id": self.env.user.id,
                    "vetting_approved_date": today,
                    "approved_until": company.approved_until
                    if company.approved_until and company.approved_until > today
                    else today + relativedelta(years=1),
                    "vetting_rejection_reason_id": False,
                }
            )
        return True

    def action_vetting_reject(self, reason=None, note=None):
        values = {"vetting_state": "rejected"}
        if reason:
            values["vetting_rejection_reason_id"] = reason.id if hasattr(reason, "id") else reason
        self.write(values)
        if note:
            for company in self:
                company.message_post(body=note)
        return True

    def action_vetting_reset(self):
        return self.write({"vetting_state": "pending"})

    def _is_vetted(self, on_date=None):
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        return self.vetting_state == "approved" and bool(self.approved_until) and self.approved_until >= on_date

    def _generate_invite_token(self):
        for company in self.sudo():
            company.invite_token = secrets.token_urlsafe(32)
        return True

    def _check_invite_token(self, token):
        """Constant-time comparison of a supplied invite token."""
        self.ensure_one()
        stored = self.sudo().invite_token
        return bool(stored and token) and hmac.compare_digest(stored, token)

    def action_send_invite(self):
        template = self.env.ref("internship_base.mail_template_company_invite")
        for company in self:
            company._generate_invite_token()
            company.write({"invited_by_id": self.env.user.id, "invite_date": fields.Datetime.now()})
            template.send_mail(company.id, force_send=False)
        return True

    def _invite_url(self):
        self.ensure_one()
        base_url = self.get_base_url()
        return f"{base_url}/internship/company/invite/{self.id}/{self.sudo().invite_token or ''}"

    @api.model
    def _cron_expiry_alerts(self):
        """Insurance and pre-approval expiry: alert coordinators; expire lapsed approvals."""
        today = fields.Date.context_today(self)
        horizon = today + relativedelta(days=self.env["internship.program"]._get_rule("expiry_alert_days"))
        companies = self.sudo().search(
            [
                ("active", "=", True),
                "|",
                ("insurance_expiry", "<=", horizon),
                ("approved_until", "<=", horizon),
            ]
        )
        for company in companies:
            owner = company.vetting_approved_by_id or default_coordinator(self.env)
            if company.vetting_state == "approved" and company.approved_until and company.approved_until < today:
                company.vetting_state = "expired"
            for expiry, label in (
                (company.insurance_expiry, self.env._("Insurance")),
                (company.approved_until, self.env._("Company pre-approval")),
            ):
                if expiry and expiry <= horizon:
                    state = self.env._("expired") if expiry < today else self.env._("expiring")
                    schedule_activity_once(
                        company,
                        owner,
                        self.env._("%(label)s %(state)s on %(date)s", label=label, state=state, date=expiry),
                        deadline=min(expiry, horizon),
                    )
        self.env["internship.student"]._cron_expiry_alerts()
        return True
