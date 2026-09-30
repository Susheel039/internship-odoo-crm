import base64
import hashlib
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.pdf import merge_pdf

from odoo.addons.internship_base.services.activity import default_coordinator, schedule_activity_once

_logger = logging.getLogger(__name__)

SEND_STATE = {"company": "sent_company", "student": "sent_student", "university": "awaiting_university"}
SIGNED_STATE = {"company": "signed_company", "student": "signed_student", "university": "fully_signed"}
SENT_DATE_FIELD = {
    "company": "sent_to_company_date",
    "student": "sent_to_student_date",
    "university": "sent_to_university_date",
}
OPEN_STATES = ("sent_company", "signed_company", "sent_student", "signed_student", "awaiting_university")


class InternshipAgreement(models.Model):
    """Three-party placement agreement, signed in sequence: company, student, university."""

    _name = "internship.agreement"
    _description = "Placement Agreement"
    _inherit = ["mail.thread", "mail.activity.mixin", "internship.placement.link.mixin"]
    _order = "placement_id, version desc"

    # Documents of record are never deleted with their placement.
    placement_id = fields.Many2one(
        "internship.placement", required=True, index=True, ondelete="restrict", string="Placement"
    )
    name = fields.Char(required=True, default="New", copy=False, readonly=True, index=True)
    version = fields.Integer(default=1, readonly=True)
    amendment_of_id = fields.Many2one("internship.agreement", readonly=True, index=True, string="Amends")
    change_request_id = fields.Many2one("internship.change.request", readonly=True)

    pdf_attachment_id = fields.Many2one("ir.attachment", string="Agreement Document", readonly=True, copy=False)
    pdf_sha256 = fields.Char(string="SHA-256", readonly=True, copy=False)
    signed_attachment_id = fields.Many2one("ir.attachment", string="Signed Document", readonly=True, copy=False)
    generated_date = fields.Datetime(readonly=True, copy=False)
    sent_to_company_date = fields.Datetime(readonly=True, copy=False)
    sent_to_student_date = fields.Datetime(readonly=True, copy=False)
    sent_to_university_date = fields.Datetime(readonly=True, copy=False)
    reminder_count = fields.Integer(readonly=True, copy=False)
    last_reminder_date = fields.Date(readonly=True, copy=False)

    signer_ids = fields.One2many("internship.agreement.signer", "agreement_id", string="Signers", copy=False)
    current_signer_id = fields.Many2one("internship.agreement.signer", compute="_compute_current_signer_id")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent_company", "Sent to company"),
            ("signed_company", "Signed by company"),
            ("sent_student", "Sent to student"),
            ("signed_student", "Signed by student"),
            ("awaiting_university", "Awaiting university"),
            ("fully_signed", "Fully signed"),
            ("declined", "Declined"),
            ("voided", "Voided"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
    decline_reason = fields.Text(readonly=True, copy=False)
    declined_by_id = fields.Many2one("res.partner", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("internship.agreement") or "New"
        return super().create(vals_list)

    @api.depends("signer_ids.state", "state")
    def _compute_current_signer_id(self):
        for agreement in self:
            pending = agreement.signer_ids.filtered(lambda s: s.state in ("pending", "sent")).sorted("sequence")
            agreement.current_signer_id = pending[:1] if agreement.state in ("draft",) + OPEN_STATES else False

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    @api.model
    def _create_for_placement(self, placement, amendment_of=None, change_request=None, send=True):
        agreement = self.create(
            {
                "placement_id": placement.id,
                # Versions count every agreement issued for the placement, voided ones included.
                "version": max(placement.agreement_ids.mapped("version"), default=0) + 1,
                "amendment_of_id": amendment_of.id if amendment_of else False,
                "change_request_id": change_request.id if change_request else False,
            }
        )
        agreement._create_signers()
        agreement._generate_document()
        if send:
            agreement.action_send()
        return agreement

    def _signer_values(self):
        """Company (1), student (2), university (3)."""
        self.ensure_one()
        placement = self.placement_id
        company = placement.internship_company_id
        manager = (
            placement.line_manager_id
            if placement.line_manager_id.can_sign_agreement
            else company.line_manager_ids.filtered("can_sign_agreement")[:1]
        )
        if manager:
            company_partner, company_user = manager.partner_id, manager.user_id
        elif company.signatory_email:
            company_partner = self.env["res.partner"].search([("email", "=ilike", company.signatory_email)], limit=1)
            if not company_partner:
                company_partner = self.env["res.partner"].create(
                    {
                        "name": company.signatory_name or company.name,
                        "email": company.signatory_email,
                        "function": company.signatory_title,
                        "parent_id": company.partner_id.id,
                    }
                )
            company_user = company_partner.user_ids[:1]
        else:
            company_partner, company_user = company.partner_id, company.user_ids[:1]
        student_partner = placement.student_id.partner_id
        coordinator = placement.user_id or default_coordinator(self.env)
        return [
            {"sequence": 1, "role": "company", "partner_id": company_partner.id, "user_id": company_user.id},
            {
                "sequence": 2,
                "role": "student",
                "partner_id": student_partner.id,
                "user_id": student_partner.user_ids[:1].id,
            },
            {"sequence": 3, "role": "university", "partner_id": coordinator.partner_id.id, "user_id": coordinator.id},
        ]

    def _create_signers(self):
        for agreement in self:
            agreement.write({"signer_ids": [(0, 0, values) for values in agreement._signer_values()]})
        return True

    # ------------------------------------------------------------------
    # Document generation and integrity
    # ------------------------------------------------------------------
    @staticmethod
    def _is_pdf(content):
        return bool(content) and content[:5] == b"%PDF-"

    def _render(self, report_xmlid):
        content, _fmt = self.env["ir.actions.report"].sudo()._render_qweb_pdf(report_xmlid, self.ids)
        return content if isinstance(content, bytes) else content.encode()

    def _generate_document(self):
        """Render the agreement, append the programme template (if a PDF), store and hash it."""
        for agreement in self:
            content = agreement._render("internship_agreement.action_report_agreement")
            template = agreement.placement_id.program_id.agreement_template_id
            if agreement._is_pdf(content) and template and template.mimetype == "application/pdf":
                content = merge_pdf([content, base64.b64decode(template.datas)])
            extension = "pdf" if agreement._is_pdf(content) else "html"
            attachment = (
                self.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": f"{agreement.name}.{extension}",
                        "raw": content,
                        "mimetype": "application/pdf" if extension == "pdf" else "text/html",
                        "res_model": agreement._name,
                        "res_id": agreement.id,
                    }
                )
            )
            agreement.write(
                {
                    "pdf_attachment_id": attachment.id,
                    "pdf_sha256": hashlib.sha256(content).hexdigest(),
                    "generated_date": fields.Datetime.now(),
                }
            )
        return True

    def _verify_integrity(self):
        """The unsigned document must be byte-for-byte what was generated and sent."""
        for agreement in self:
            raw = agreement.pdf_attachment_id.sudo().raw
            if not raw or hashlib.sha256(raw).hexdigest() != agreement.pdf_sha256:
                _logger.warning("Agreement %s failed its integrity check", agreement.name)
                raise UserError(
                    self.env._(
                        "The agreement document has changed since it was generated. Ask the university to reissue it."
                    )
                )
        return True

    def _stamp_signatures(self):
        """Signed copy = original document + signature certificate page."""
        for agreement in self:
            original = agreement.pdf_attachment_id.sudo().raw
            certificate = agreement._render("internship_agreement.action_report_agreement_signatures")
            if agreement._is_pdf(original) and agreement._is_pdf(certificate):
                content, extension, mimetype = merge_pdf([original, certificate]), "pdf", "application/pdf"
            else:
                content, extension, mimetype = original + b"\n" + certificate, "html", "text/html"
            values = {"name": f"{agreement.name}-signed.{extension}", "raw": content, "mimetype": mimetype}
            if agreement.signed_attachment_id:
                agreement.signed_attachment_id.sudo().write(values)
            else:
                values.update(res_model=agreement._name, res_id=agreement.id)
                agreement.signed_attachment_id = self.env["ir.attachment"].sudo().create(values)
        return True

    # ------------------------------------------------------------------
    # Sending, signing, declining
    # ------------------------------------------------------------------
    def action_send(self):
        for agreement in self:
            if agreement.state not in ("draft", "signed_company", "signed_student"):
                raise UserError(self.env._("This agreement cannot be sent in its current state."))
            signer = agreement.current_signer_id
            if not signer:
                raise UserError(self.env._("There is nobody left to sign this agreement."))
            agreement._send_to(signer)
        return True

    def _send_to(self, signer):
        self.ensure_one()
        signer.write({"state": "sent", "sent_date": fields.Datetime.now()})
        self.write({"state": SEND_STATE[signer.role], SENT_DATE_FIELD[signer.role]: fields.Datetime.now()})
        template = self.env.ref("internship_agreement.mail_template_agreement_sign_request", raise_if_not_found=False)
        if template and signer.partner_id.email:
            template.sudo().send_mail(signer.id)
        if signer.user_id and not signer.user_id.share:
            schedule_activity_once(self, signer.user_id, self.env._("Sign agreement %(name)s", name=self.name))
        return True

    def _sign(self, signer, name, signature, ip_address=None, user_agent=None):
        self.ensure_one()
        if self.state not in OPEN_STATES:
            raise UserError(self.env._("This agreement is not waiting for signatures."))
        if signer != self.current_signer_id:
            raise UserError(self.env._("It is not your turn to sign this agreement."))
        if not name or not signature:
            raise UserError(self.env._("Your name and signature are required."))
        self._verify_integrity()
        signer.write(
            {
                "state": "signed",
                "signed_at": fields.Datetime.now(),
                "signed_ip": ip_address,
                "user_agent": (user_agent or "")[:500],
                "signature": signature,
                "signed_name": name,
            }
        )
        self.write({"state": SIGNED_STATE[signer.role], "reminder_count": 0, "last_reminder_date": False})
        self.message_post(
            body=self.env._(
                "Signed by %(name)s (%(role)s) from %(ip)s.",
                name=name,
                role=dict(signer._fields["role"].selection)[signer.role],
                ip=ip_address or "-",
            )
        )
        self._stamp_signatures()
        self.activity_ids.filtered(lambda a: a.user_id == signer.user_id).action_feedback(feedback=self.env._("Signed"))
        if self.state == "fully_signed":
            self._on_fully_signed()
        else:
            self._send_to(self.current_signer_id)
        return True

    def _on_fully_signed(self):
        self.ensure_one()
        template = self.env.ref("internship_agreement.mail_template_agreement_completed", raise_if_not_found=False)
        if template:
            template.sudo().send_mail(self.id)
        placement = self.placement_id
        if self.amendment_of_id:
            placement.message_post(body=self.env._("Agreement amendment %(name)s fully signed.", name=self.name))
        elif placement.stage_code == "agreement":
            placement._mark_agreement_complete()
        return True

    def _decline(self, signer, reason):
        self.ensure_one()
        if signer != self.current_signer_id:
            raise UserError(self.env._("It is not your turn on this agreement."))
        signer.state = "declined"
        self.write({"state": "declined", "decline_reason": reason, "declined_by_id": signer.partner_id.id})
        self.message_post(
            body=self.env._("Declined by %(name)s: %(reason)s", name=signer.partner_id.name, reason=reason or "-")
        )
        schedule_activity_once(
            self.placement_id,
            self.placement_id.user_id or default_coordinator(self.env),
            self.env._("Agreement %(name)s was declined", name=self.name),
            note=reason,
        )
        return True

    def action_void(self):
        # A fully signed agreement is a document of record: it is superseded, never voided.
        self.filtered(lambda a: a.state != "fully_signed").write({"state": "voided"})
        return True

    def action_regenerate(self):
        """Void this agreement and issue a fresh version (e.g. after a decline or data correction)."""
        self.ensure_one()
        self.action_void()
        new = self._create_for_placement(self.placement_id, amendment_of=self.amendment_of_id or None)
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": new.id, "view_mode": "form"}

    def action_open_signing_page(self):
        """For internal signers (e.g. the university coordinator): open the signing page."""
        self.ensure_one()
        signer = self.current_signer_id
        if not signer:
            raise UserError(self.env._("Nobody is due to sign this agreement."))
        if signer.user_id != self.env.user and not self.env.user.has_group(
            "internship_base.group_platform_administrator"
        ):
            raise UserError(self.env._("It is %(name)s's turn to sign.", name=signer.partner_id.name))
        return {"type": "ir.actions.act_url", "url": signer.sudo()._sign_url(), "target": "new"}

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_reminders(self):
        """Remind the current signer every 3 days, at most 3 times."""
        today = fields.Date.context_today(self)
        template = self.env.ref("internship_agreement.mail_template_agreement_sign_request", raise_if_not_found=False)
        reminded = self.browse()
        for agreement in self.search([("state", "in", OPEN_STATES), ("reminder_count", "<", 3)]):
            signer = agreement.current_signer_id
            if not signer or not signer.sent_date:
                continue
            last = agreement.last_reminder_date or signer.sent_date.date()
            if today < last + relativedelta(days=3):
                continue
            if template and signer.partner_id.email:
                template.sudo().send_mail(signer.id)
            agreement.write({"reminder_count": agreement.reminder_count + 1, "last_reminder_date": today})
            reminded |= agreement
        return reminded
