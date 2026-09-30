from odoo import models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _notify_by_email_prepare_rendering_context(
        self,
        message,
        msg_vals=False,
        model_description=False,
        force_email_company=False,
        force_email_lang=False,
        force_record_name=False,
    ):
        # Pre-v2 internship models have `company_id` pointing to internship.company; the e-mail
        # layout would read it as res.company. Use the current Odoo company for those records.
        company_field = self._fields.get("company_id")
        if not force_email_company and company_field and company_field.comodel_name != "res.company":
            force_email_company = self.env.company
        return super()._notify_by_email_prepare_rendering_context(
            message,
            msg_vals=msg_vals,
            model_description=model_description,
            force_email_company=force_email_company,
            force_email_lang=force_email_lang,
            force_record_name=force_record_name,
        )
