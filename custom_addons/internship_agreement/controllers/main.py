import logging

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class InternshipAgreementPortal(http.Controller):
    """Public signing pages. Access is granted by the signer's secret token only."""

    def _signer_or_404(self, agreement_id, token):
        signer = request.env["internship.agreement.signer"].sudo()._find_by_token(agreement_id, token)
        if not signer:
            raise request.not_found()
        return signer

    @http.route(
        "/internship/agreement/<int:agreement_id>/sign/<string:token>", type="http", auth="public", website=True
    )
    def agreement_sign_page(self, agreement_id, token, **kwargs):
        signer = self._signer_or_404(agreement_id, token)
        agreement = signer.agreement_id
        values = {
            "agreement": agreement,
            "signer": signer,
            "can_sign": agreement.current_signer_id == signer and agreement.state not in ("declined", "voided"),
            "document_url": f"/internship/agreement/{agreement_id}/document/{token}",
            "call_url": f"/internship/agreement/{agreement_id}/sign/{token}/submit",
            "decline_url": f"/internship/agreement/{agreement_id}/decline/{token}",
            "message": kwargs.get("message"),
        }
        return request.render("internship_agreement.agreement_sign_page", values)

    @http.route(
        "/internship/agreement/<int:agreement_id>/document/<string:token>", type="http", auth="public", website=True
    )
    def agreement_document(self, agreement_id, token, **kwargs):
        signer = self._signer_or_404(agreement_id, token)
        agreement = signer.agreement_id
        attachment = (agreement.signed_attachment_id or agreement.pdf_attachment_id).sudo()
        if not attachment:
            raise request.not_found()
        return request.make_response(
            attachment.raw,
            headers=[
                ("Content-Type", attachment.mimetype or "application/pdf"),
                ("Content-Disposition", f'inline; filename="{attachment.name}"'),
                ("X-Content-Type-Options", "nosniff"),
            ],
        )

    @http.route(
        "/internship/agreement/<int:agreement_id>/sign/<string:token>/submit",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def agreement_sign_submit(self, agreement_id, token, name=None, signature=None, **kwargs):
        signer = request.env["internship.agreement.signer"].sudo()._find_by_token(agreement_id, token)
        if not signer:
            return {"error": request.env._("This signing link is not valid.")}
        try:
            signer.agreement_id._sign(
                signer,
                name,
                signature,
                ip_address=request.httprequest.remote_addr,
                user_agent=request.httprequest.headers.get("User-Agent"),
            )
        except UserError as error:
            return {"error": str(error)}
        return {
            "force_refresh": True,
            "redirect_url": f"/internship/agreement/{agreement_id}/sign/{token}?message=signed",
        }

    @http.route(
        "/internship/agreement/<int:agreement_id>/decline/<string:token>",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def agreement_decline(self, agreement_id, token, reason=None, **kwargs):
        signer = self._signer_or_404(agreement_id, token)
        try:
            signer.agreement_id._decline(signer, (reason or "").strip()[:2000])
        except UserError:
            _logger.info("Refused decline on agreement %s", agreement_id)
        return request.redirect(f"/internship/agreement/{agreement_id}/sign/{token}?message=declined")
