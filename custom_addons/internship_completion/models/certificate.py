from odoo import api, fields, models
from odoo.exceptions import UserError


class InternshipCertificate(models.Model):
    """Certificate of completion issued by the host company. Independent of marking."""

    _name = "internship.certificate"
    _description = "Internship Certificate"
    _inherit = ["mail.thread", "internship.placement.link.mixin"]
    _order = "issue_date desc, id desc"

    placement_id = fields.Many2one(
        "internship.placement", required=True, index=True, ondelete="restrict", string="Placement"
    )
    name = fields.Char(required=True, default="New", copy=False, readonly=True, index=True)
    issue_date = fields.Date(default=fields.Date.context_today, tracking=True)
    issued_by_id = fields.Many2one(
        "internship.line.manager",
        string="Issued By",
        tracking=True,
        domain="[('company_id', '=', internship_company_id), ('can_issue_certificate', '=', True)]",
    )
    attachment_id = fields.Many2one("ir.attachment", string="Certificate", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("internship.certificate") or "New"
        return super().create(vals_list)

    def action_issue(self):
        for certificate in self:
            issuer = certificate.issued_by_id or certificate.placement_id.line_manager_id
            if not issuer or not issuer.can_issue_certificate:
                raise UserError(self.env._("Choose a line manager who is allowed to issue certificates."))
            certificate.issued_by_id = issuer
            content, _fmt = (
                self.env["ir.actions.report"]
                .sudo()
                ._render_qweb_pdf("internship_completion.action_report_internship_certificate", certificate.ids)
            )
            is_pdf = content[:5] == b"%PDF-"
            certificate.attachment_id = (
                self.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": f"{certificate.name}.{'pdf' if is_pdf else 'html'}",
                        "raw": content,
                        "mimetype": "application/pdf" if is_pdf else "text/html",
                        "res_model": certificate._name,
                        "res_id": certificate.id,
                    }
                )
            )
            certificate.message_post(body=self.env._("Certificate issued by %(name)s.", name=issuer.name))
        return True

    def action_print(self):
        self.ensure_one()
        return self.env.ref("internship_completion.action_report_internship_certificate").report_action(self)
