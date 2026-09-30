from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    internship_rule_form_due_days = fields.Integer(
        string="Form due (days)", config_parameter="internship_base.rule_form_due_days", default=7
    )
    internship_rule_monthly_due_day = fields.Integer(
        string="Monthly record due (day of month)", config_parameter="internship_base.rule_monthly_due_day", default=5
    )
    internship_rule_monthly_late_grace_days = fields.Integer(
        string="Monthly late grace (days)", config_parameter="internship_base.rule_monthly_late_grace_days", default=3
    )
    internship_rule_report_deadline_days = fields.Integer(
        string="Report deadline (days)", config_parameter="internship_base.rule_report_deadline_days", default=14
    )
    internship_rule_resubmission_days = fields.Integer(
        string="Resubmission window (days)", config_parameter="internship_base.rule_resubmission_days", default=14
    )
    internship_rule_max_report_attempts = fields.Integer(
        string="Max report attempts", config_parameter="internship_base.rule_max_report_attempts", default=2
    )
    internship_rule_tripartite_attendance_pct = fields.Float(
        string="Tripartite if attendance below (%)",
        config_parameter="internship_base.rule_tripartite_attendance_pct",
        default=80.0,
    )
    internship_rule_tripartite_rating_threshold = fields.Integer(
        string="Tripartite if rating at or below",
        config_parameter="internship_base.rule_tripartite_rating_threshold",
        default=2,
    )
    internship_rule_expiry_alert_days = fields.Integer(
        string="Expiry alert (days)", config_parameter="internship_base.rule_expiry_alert_days", default=30
    )
    internship_rule_retention_years = fields.Integer(
        string="Data retention (years)", config_parameter="internship_base.rule_retention_years", default=6
    )

    # Company shared communication identity (users' blank channels fall back to these)
    channel_email_from = fields.Char(related="company_id.channel_email_from", readonly=False)
    channel_mail_server_id = fields.Many2one(related="company_id.channel_mail_server_id", readonly=False)
    channel_sms_sender = fields.Char(related="company_id.channel_sms_sender", readonly=False)
    channel_whatsapp_number = fields.Char(related="company_id.channel_whatsapp_number", readonly=False)
    channel_whatsapp_phone_number_id = fields.Char(
        related="company_id.channel_whatsapp_phone_number_id", readonly=False
    )
