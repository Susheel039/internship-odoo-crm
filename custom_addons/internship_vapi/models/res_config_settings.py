import secrets

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.calling_window import DEFAULT_WINDOW, parse_calling_window
from ..services.vapi_client import VapiClient, VapiError


class ResConfigSettings(models.TransientModel):
    """Voice assistant (Vapi) configuration, shown in the CRM settings.

    Every value is an ir.config_parameter under `internship_vapi.*`, never stored in Git.
    """

    _inherit = "res.config.settings"

    vapi_enabled = fields.Boolean(string="Enabled", config_parameter="internship_vapi.enabled")
    vapi_api_key = fields.Char(string="API Key", config_parameter="internship_vapi.api_key")
    vapi_webhook_token = fields.Char(string="Webhook Token", config_parameter="internship_vapi.webhook_token")
    vapi_default_assistant_id = fields.Char(
        string="Default Assistant ID", config_parameter="internship_vapi.default_assistant_id"
    )
    vapi_chaser_assistant_id = fields.Char(
        string="Workflow Chaser Assistant ID",
        config_parameter="internship_vapi.chaser_assistant_id",
        help="Optional. Used for document, attendance, report and feedback reminders; "
        "otherwise the default assistant makes those calls too.",
    )
    vapi_phone_number_id = fields.Char(string="Phone Number ID", config_parameter="internship_vapi.phone_number_id")
    vapi_calling_window = fields.Char(
        string="Calling Window",
        config_parameter="internship_vapi.calling_window",
        default=DEFAULT_WINDOW,
        help="Days, hours and time zone, e.g. 'Mon-Fri 09:00-20:00 Europe/London'.",
    )
    vapi_max_attempts = fields.Integer(
        string="Max Attempts", config_parameter="internship_vapi.max_attempts", default=3
    )
    vapi_webhook_url = fields.Char(string="Webhook URL", compute="_compute_vapi_urls")
    vapi_tool_url = fields.Char(string="Tool URL", compute="_compute_vapi_urls")

    @api.depends("company_id")
    def _compute_vapi_urls(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        for settings in self:
            settings.vapi_webhook_url = f"{base_url}/internship/call-tracking/webhook"
            settings.vapi_tool_url = f"{base_url}/internship/vapi/tool"

    @api.constrains("vapi_calling_window", "vapi_max_attempts")
    def _check_vapi_settings(self):
        for settings in self:
            if settings.vapi_calling_window:
                try:
                    parse_calling_window(settings.vapi_calling_window)
                except ValueError as error:
                    raise UserError(str(error)) from error
            if settings.vapi_max_attempts < 1:
                raise UserError(self.env._("Max attempts must be at least 1."))

    def action_vapi_generate_token(self):
        """Create a new random webhook token (paste it into the Vapi dashboard afterwards)."""
        self.env["ir.config_parameter"].sudo().set_param("internship_vapi.webhook_token", secrets.token_urlsafe(48))
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_vapi_test_connection(self):
        self.execute()
        try:
            client = VapiClient(self.env)
            assistant_id = self.vapi_default_assistant_id
            if assistant_id:
                assistant = client.get_assistant(assistant_id)
                message = self.env._("Connected. Assistant: %(name)s", name=assistant.get("name") or assistant_id)
            else:
                client.list_assistants()
                message = self.env._("Connected. Set the default assistant ID to finish the setup.")
            kind = "success"
        except VapiError as error:
            message, kind = str(error), "danger"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Voice Assistant"),
                "message": message,
                "type": kind,
                "sticky": kind != "success",
            },
        }

    def action_vapi_open_call_logs(self):
        return self.env["ir.actions.act_window"]._for_xml_id("internship_vapi.action_internship_call_log")

    def action_vapi_open_events(self):
        return self.env["ir.actions.act_window"]._for_xml_id("internship_vapi.action_internship_vapi_event")
