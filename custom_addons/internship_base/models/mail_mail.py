from email.utils import formataddr

from odoo import api, models


class MailMail(models.Model):
    """Send each user's e-mails with their own channel identity (see res.users channels)."""

    _inherit = "mail.mail"

    @api.model_create_multi
    def create(self, vals_list):
        authors = {vals.get("author_id") for vals in vals_list if vals.get("author_id")}
        users_by_partner = {}
        if authors:
            users = self.env["res.users"].sudo().search([("partner_id", "in", list(authors)), ("share", "=", False)])
            users_by_partner = {user.partner_id.id: user for user in users}
        for vals in vals_list:
            user = users_by_partner.get(vals.get("author_id"))
            if not user or not user.channels_active:
                continue
            channel = user._internship_channel("email")
            if not channel["enabled"]:
                vals["state"] = "cancel"
                vals["failure_reason"] = self.env._(
                    "E-mail is switched off for %(user)s (Communication Channels).", user=user.name
                )
                continue
            if channel.get("channel_email_from"):
                vals["email_from"] = formataddr((user.name, channel["channel_email_from"]))
            if channel.get("channel_mail_server_id"):
                vals["mail_server_id"] = channel["channel_mail_server_id"].id
        return super().create(vals_list)
