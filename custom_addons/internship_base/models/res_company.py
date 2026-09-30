from odoo import fields, models


class ResCompany(models.Model):
    """The company's shared ("house") communication identity.

    Users' channels fall back to these when their own fields are blank and House Identity is on.
    """

    _inherit = "res.company"

    channel_email_from = fields.Char(string="Shared From Address")
    channel_mail_server_id = fields.Many2one("ir.mail_server", string="Shared Outgoing Mail Server")
    channel_sms_sender = fields.Char(string="Shared SMS Sender")
    channel_whatsapp_number = fields.Char(string="Shared WhatsApp Number")
    channel_whatsapp_phone_number_id = fields.Char(string="Shared Meta Phone Number ID")
