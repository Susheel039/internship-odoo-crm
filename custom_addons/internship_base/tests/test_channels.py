from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCommunicationChannels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls.env["ir.mail_server"].create({"name": "Brevo", "smtp_host": "smtp.example", "smtp_port": 587})
        cls.env.company.write({"channel_email_from": "hello@company.example", "channel_sms_sender": "INTERNTION"})
        cls.agent = cls.env["res.users"].create(
            {"name": "Agent One", "login": "agent_one_channels", "email": "agent.one@company.example"}
        )

    def test_personal_values_and_house_identity(self):
        self.agent.write({"channel_email_from": "agent@company.example", "channel_mail_server_id": self.server.id})
        email = self.agent._internship_channel("email")
        self.assertTrue(email["enabled"])
        self.assertTrue(email["personal"])
        self.assertEqual(email["channel_email_from"], "agent@company.example")
        sms = self.agent._internship_channel("sms")
        self.assertEqual(sms["channel_sms_sender"], "INTERNTION", "blank falls back to the house identity")
        self.agent.channels_house_identity = False
        self.assertFalse(self.agent._internship_channel("sms")["channel_sms_sender"])
        self.assertIn("Email", self.agent.channels_personalised)
        self.assertNotIn("SMS", self.agent.channels_personalised)

    def test_switched_off_does_not_fall_back(self):
        self.agent.channel_sms_enabled = False
        self.assertEqual(self.agent._internship_channel("sms"), {"enabled": False, "personal": False})
        self.agent.channels_active = False
        channel = self.agent._internship_channel("sms")
        self.assertTrue(channel["enabled"], "inactive channels: the user just uses the company identity")
        self.assertEqual(channel["channel_sms_sender"], "INTERNTION")

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.agent.channel_whatsapp_number = "not a number"
        with self.assertRaises(ValidationError):
            self.agent.channel_sms_sender = "WAY-TOO-LONG-SENDER"
        self.agent.write({"channel_whatsapp_number": "+44 7700 900123", "channel_sms_sender": "NETON"})

    def test_outgoing_mail_uses_user_identity_or_is_blocked(self):
        self.agent.write({"channel_email_from": "agent@company.example", "channel_mail_server_id": self.server.id})
        mail = self.env["mail.mail"].create(
            {
                "author_id": self.agent.partner_id.id,
                "email_to": "x@y.example",
                "subject": "Hi",
                "body_html": "<p>Hi</p>",
            }
        )
        self.assertIn("agent@company.example", mail.email_from)
        self.assertEqual(mail.mail_server_id, self.server)
        self.agent.channel_email_enabled = False
        blocked = self.env["mail.mail"].create(
            {
                "author_id": self.agent.partner_id.id,
                "email_to": "x@y.example",
                "subject": "Hi",
                "body_html": "<p>Hi</p>",
            }
        )
        self.assertEqual(blocked.state, "cancel")
        self.assertIn("switched off", blocked.failure_reason)
