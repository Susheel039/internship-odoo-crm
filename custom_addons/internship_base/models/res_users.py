import re

import phonenumbers

from odoo import api, fields, models
from odoo.exceptions import ValidationError

CHANNEL_ADMIN_GROUPS = "base.group_system,internship_base.group_platform_administrator"
CHANNELS = ("email", "sms", "whatsapp", "voice")
CHANNEL_LABELS = {"email": "Email", "whatsapp": "WhatsApp", "sms": "SMS", "voice": "Voice"}
# Per channel: user field -> company fallback field (None: no company value, e.g. Vapi keys)
CHANNEL_FIELDS = {
    "email": {"channel_email_from": "channel_email_from", "channel_mail_server_id": "channel_mail_server_id"},
    "sms": {"channel_sms_sender": "channel_sms_sender"},
    "whatsapp": {
        "channel_whatsapp_number": "channel_whatsapp_number",
        "channel_whatsapp_phone_number_id": "channel_whatsapp_phone_number_id",
    },
    "voice": {
        "channel_voice_phone_number_id": None,
        "channel_voice_assistant_id": None,
        "channel_voice_api_key": None,
    },
}
SMS_SENDER = re.compile(r"^(?=.*[A-Za-z])[A-Za-z0-9 ]{3,11}$|^\+?\d{3,15}$")


class ResUsers(models.Model):
    """Per-user communication channels: the numbers and addresses this user's customers see."""

    _inherit = "res.users"

    # Email
    channel_email_enabled = fields.Boolean(string="Email Enabled", default=True, groups=CHANNEL_ADMIN_GROUPS)
    channel_email_from = fields.Char(
        string="From Address",
        groups=CHANNEL_ADMIN_GROUPS,
        help="Address this user's e-mails are sent from. Blank: the company's shared address.",
    )
    channel_mail_server_id = fields.Many2one(
        "ir.mail_server",
        string="Channel Outgoing Mail Server",
        groups=CHANNEL_ADMIN_GROUPS,
        help="Server used for this user's e-mails. Blank: the company's shared server (or Odoo's default).",
    )
    # SMS
    channel_sms_enabled = fields.Boolean(string="SMS Enabled", default=True, groups=CHANNEL_ADMIN_GROUPS)
    channel_sms_sender = fields.Char(
        string="SMS Sender",
        groups=CHANNEL_ADMIN_GROUPS,
        help="Sender name (3-11 letters/digits) or number shown on this user's text messages.",
    )
    # WhatsApp
    channel_whatsapp_enabled = fields.Boolean(string="WhatsApp Enabled", default=True, groups=CHANNEL_ADMIN_GROUPS)
    channel_whatsapp_number = fields.Char(
        string="WhatsApp Number", groups=CHANNEL_ADMIN_GROUPS, help="Business number in international format."
    )
    channel_whatsapp_phone_number_id = fields.Char(
        string="Meta Phone Number ID",
        groups=CHANNEL_ADMIN_GROUPS,
        help="Phone number ID from Meta WhatsApp Business (Cloud API).",
    )
    # Voice (Vapi)
    channel_voice_enabled = fields.Boolean(string="Voice Enabled", default=True, groups=CHANNEL_ADMIN_GROUPS)
    channel_voice_phone_number_id = fields.Char(
        string="Phone Number ID",
        groups=CHANNEL_ADMIN_GROUPS,
        help="Vapi phone number this user's AI calls are made from. Blank: the company number.",
    )
    channel_voice_assistant_id = fields.Char(
        string="Assistant ID", groups=CHANNEL_ADMIN_GROUPS, help="Vapi assistant for this user's calls."
    )
    channel_voice_api_key = fields.Char(
        string="API Key",
        groups=CHANNEL_ADMIN_GROUPS,
        copy=False,
        help="Vapi private key for this user's own Vapi account. Never logged.",
    )
    # Administrator
    channels_active = fields.Boolean(
        string="Channels Active",
        default=True,
        groups=CHANNEL_ADMIN_GROUPS,
        help="Apply this user's channel settings. Off: the user sends with the company's shared details.",
    )
    channels_house_identity = fields.Boolean(
        string="House Identity",
        default=True,
        groups=CHANNEL_ADMIN_GROUPS,
        help="Blank channel fields fall back to the company's shared identity. "
        "Off: a channel without its own details cannot send.",
    )
    channels_personalised = fields.Char(
        string="Personalised", compute="_compute_channels_personalised", groups=CHANNEL_ADMIN_GROUPS
    )

    @api.depends(*(f for fields_map in CHANNEL_FIELDS.values() for f in fields_map))
    def _compute_channels_personalised(self):
        for user in self:
            personalised = [
                CHANNEL_LABELS[channel]
                for channel in ("email", "whatsapp", "sms", "voice")
                if any(user[field_name] for field_name in CHANNEL_FIELDS[channel])
            ]
            user.channels_personalised = ", ".join(personalised) or self.env._("None")

    @api.constrains("channel_whatsapp_number", "channel_sms_sender", "channel_email_from")
    def _check_channel_values(self):
        for user in self:
            if user.channel_whatsapp_number:
                try:
                    number = phonenumbers.parse(user.channel_whatsapp_number, "GB")
                except phonenumbers.NumberParseException:
                    number = None
                if not number or not phonenumbers.is_possible_number(number):
                    raise ValidationError(self.env._("WhatsApp Number must be a phone number, e.g. +44 7700 900123."))
            if user.channel_sms_sender and not SMS_SENDER.match(user.channel_sms_sender):
                raise ValidationError(
                    self.env._("SMS Sender must be 3-11 letters/digits (with at least one letter) or a phone number.")
                )
            if user.channel_email_from and "@" not in user.channel_email_from:
                raise ValidationError(self.env._("From Address must be an e-mail address."))

    def _internship_channel(self, channel):
        """Resolve a channel for this user.

        Returns {"enabled": bool, "personal": bool, <field>: value, ...}. A channel switched off
        is disabled outright (no fallback to the company). Blank fields use the company's shared
        identity when House Identity is on; otherwise they stay empty.
        """
        self.ensure_one()
        if channel not in CHANNELS:
            raise ValueError(channel)
        user = self.sudo()
        company = user.company_id
        result = {"enabled": True, "personal": False}
        if not user.channels_active:
            for field_name, company_field in CHANNEL_FIELDS[channel].items():
                result[field_name] = company[company_field] if company_field else False
            return result
        if not user[f"channel_{channel}_enabled"]:
            return {"enabled": False, "personal": False}
        for field_name, company_field in CHANNEL_FIELDS[channel].items():
            value = user[field_name]
            if value:
                result["personal"] = True
            elif user.channels_house_identity and company_field:
                value = company[company_field]
            result[field_name] = value
        return result
