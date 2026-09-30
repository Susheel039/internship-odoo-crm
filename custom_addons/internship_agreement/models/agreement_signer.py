import hmac
import secrets

from odoo import api, fields, models

TOKEN_GROUPS = "base.group_system,internship_base.group_platform_administrator"


class InternshipAgreementSigner(models.Model):
    _name = "internship.agreement.signer"
    _description = "Agreement Signer"
    _order = "agreement_id, sequence"

    agreement_id = fields.Many2one("internship.agreement", required=True, index=True, ondelete="cascade")
    placement_id = fields.Many2one(related="agreement_id.placement_id", store=True, index=True)
    sequence = fields.Integer(required=True)
    role = fields.Selection(
        [("company", "Company"), ("student", "Student"), ("university", "University")], required=True
    )
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict", string="Partner")
    user_id = fields.Many2one("res.users", string="User")
    access_token = fields.Char(copy=False, groups=TOKEN_GROUPS, default=lambda self: secrets.token_urlsafe(32))
    state = fields.Selection(
        [("pending", "Pending"), ("sent", "Sent"), ("signed", "Signed"), ("declined", "Declined")],
        default="pending",
        required=True,
    )
    sent_date = fields.Datetime(readonly=True, copy=False)
    signed_at = fields.Datetime(readonly=True, copy=False)
    signed_ip = fields.Char(string="Signed IP", readonly=True, copy=False)
    user_agent = fields.Char(readonly=True, copy=False)
    signature = fields.Binary(attachment=True, readonly=True, copy=False)
    signed_name = fields.Char(readonly=True, copy=False)

    @api.model
    def _find_by_token(self, agreement_id, token):
        """Constant-time token lookup for the public signing routes (sudo)."""
        if not token:
            return self.browse()
        agreement = self.env["internship.agreement"].sudo().browse(agreement_id).exists()
        for signer in agreement.signer_ids.sudo():
            if signer.access_token and hmac.compare_digest(signer.access_token, str(token)):
                return signer
        return self.browse()

    def _sign_url(self):
        self.ensure_one()
        base_url = self.agreement_id.get_base_url()
        return f"{base_url}/internship/agreement/{self.agreement_id.id}/sign/{self.sudo().access_token}"
