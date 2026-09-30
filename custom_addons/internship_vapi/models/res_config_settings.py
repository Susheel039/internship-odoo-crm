from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    internship_vapi_enabled = fields.Boolean(
        string="Voice AI Calling Enabled", config_parameter="internship_vapi.enabled"
    )
    internship_vapi_api_key = fields.Char(string="Vapi API Key", config_parameter="internship_vapi.api_key")
    internship_vapi_webhook_token = fields.Char(
        string="Webhook Token", config_parameter="internship_vapi.webhook_token"
    )
    internship_vapi_default_assistant_id = fields.Char(
        string="Lead Generation Assistant ID", config_parameter="internship_vapi.default_assistant_id"
    )
    internship_vapi_chaser_assistant_id = fields.Char(
        string="Workflow Chaser Assistant ID", config_parameter="internship_vapi.chaser_assistant_id"
    )
    internship_vapi_phone_number_id = fields.Char(
        string="Phone Number ID", config_parameter="internship_vapi.phone_number_id"
    )
    internship_vapi_window_start = fields.Float(
        string="Calling From (hour)", config_parameter="internship_vapi.window_start", default=9.0
    )
    internship_vapi_window_end = fields.Float(
        string="Calling Until (hour)", config_parameter="internship_vapi.window_end", default=20.0
    )
    internship_vapi_window_days = fields.Char(
        string="Calling Days",
        config_parameter="internship_vapi.window_days",
        default="0,1,2,3,4",
        help="Weekday numbers, Monday = 0.",
    )
    internship_vapi_timezone = fields.Char(
        string="Calling Time Zone", config_parameter="internship_vapi.timezone", default="Europe/London"
    )
    internship_vapi_max_attempts = fields.Integer(
        string="Max Attempts", config_parameter="internship_vapi.max_attempts", default=3
    )
