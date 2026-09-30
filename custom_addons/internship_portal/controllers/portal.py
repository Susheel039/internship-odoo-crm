"""Portal for students and line managers.

Every route first checks that the logged-in user is the placement's student or line manager
(`_placement_for_user`); only then does it act on the records with sudo. Business rules stay
in the model methods (action_student_submit, action_company_approve, ...).
"""

import base64
import logging

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

MAX_UPLOAD = 10 * 1024 * 1024  # 10 MB


class InternshipPortal(CustomerPortal):
    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    def _portal_identity(self):
        env = request.env(su=True)
        user = request.env.user
        students = env["internship.student"].search([("partner_id", "=", user.partner_id.id)])
        managers = env["internship.line.manager"].search([("user_id", "=", user.id)])
        return students, managers

    def _my_placements_domain(self):
        students, managers = self._portal_identity()
        return ["|", ("student_id", "in", students.ids), ("line_manager_id", "in", managers.ids)]

    def _placement_for_user(self, placement_id):
        """Return (placement sudo, role) or raise 404. Role is 'student' or 'manager'."""
        students, managers = self._portal_identity()
        placement = request.env["internship.placement"].sudo().browse(placement_id).exists()
        if placement and placement.student_id in students:
            return placement, "student"
        if placement and placement.line_manager_id in managers:
            return placement, "manager"
        raise request.not_found()

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "internship_placement_count" in counters:
            values["internship_placement_count"] = (
                request.env["internship.placement"].sudo().search_count(self._my_placements_domain())
            )
        return values

    def _redirect(self, placement, message=None, error=None):
        url = f"/my/placements/{placement.id}"
        if message:
            url += f"?message={message}"
        elif error:
            url += f"?error={error}"
        return request.redirect(url)

    @staticmethod
    def _attachment_from_upload(upload, res_model, res_id):
        if not upload or not getattr(upload, "filename", None):
            return request.env["ir.attachment"]
        content = upload.read()
        if len(content) > MAX_UPLOAD:
            raise UserError(request.env._("Files must be smaller than 10 MB."))
        return (
            request.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": upload.filename,
                    "datas": base64.b64encode(content),
                    "res_model": res_model,
                    "res_id": res_id,
                    "mimetype": upload.mimetype or "application/octet-stream",
                }
            )
        )

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    @http.route(["/my/placements"], type="http", auth="user", website=True)
    def portal_my_placements(self, **kwargs):
        placements = request.env["internship.placement"].sudo().search(self._my_placements_domain())
        values = self._prepare_portal_layout_values()
        values.update({"placements": placements, "page_name": "internship_placements"})
        return request.render("internship_portal.portal_my_placements", values)

    @http.route(["/my/placements/<int:placement_id>"], type="http", auth="user", website=True)
    def portal_my_placement(self, placement_id, message=None, error=None, **kwargs):
        placement, role = self._placement_for_user(placement_id)
        signer = placement.agreement_id.current_signer_id
        my_partner = request.env.user.partner_id
        sign_url = signer.sudo()._sign_url() if signer and signer.partner_id == my_partner else False
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "placement": placement,
                "role": role,
                "page_name": "internship_placement",
                "message": message,
                "error": error and (request.session.pop("internship_portal_error", None) or error),
                "sign_url": sign_url,
                "open_requests": placement.document_request_ids.filtered(
                    lambda r: (
                        r.state != "complete"
                        and (
                            r.requested_from == "both"
                            or r.requested_from == ("student" if role == "student" else "company")
                        )
                    )
                ),
                "monthly": placement.monthly_ids.sorted(lambda m: (m.year, int(m.month)), reverse=True),
                "report": placement.report_attempt_ids.filtered(lambda a: a.status in ("draft", "returned"))[:1],
                "today": fields.Date.context_today(placement),
            }
        )
        return request.render("internship_portal.portal_my_placement", values)

    # ------------------------------------------------------------------
    # Actions (POST, CSRF-protected)
    # ------------------------------------------------------------------
    def _run(self, placement, func, ok_message):
        try:
            func()
        except (UserError, ValidationError) as error:
            _logger.info("Portal action refused on %s: %s", placement.name, error)
            request.session["internship_portal_error"] = str(error)
            return self._redirect(placement, error="refused")
        return self._redirect(placement, message=ok_message)

    @http.route(
        ["/my/placements/<int:placement_id>/request-form"], type="http", auth="user", methods=["POST"], website=True
    )
    def portal_request_form(self, placement_id, **kwargs):
        placement, role = self._placement_for_user(placement_id)
        if role != "student" or placement.stage_code != "form_requested":
            raise request.not_found()
        return self._run(placement, placement._request_company_form, "form_requested")

    @http.route(["/my/placements/<int:placement_id>/form"], type="http", auth="user", methods=["POST"], website=True)
    def portal_submit_form(self, placement_id, learning_objectives=None, hs_confirmed=None, form_file=None, **kwargs):
        placement, role = self._placement_for_user(placement_id)
        if role != "manager" or placement.stage_code != "form_requested":
            raise request.not_found()

        def submit():
            attachment = self._attachment_from_upload(form_file, placement._name, placement.id)
            values = {"learning_objectives": learning_objectives or False, "hs_confirmed": bool(hs_confirmed)}
            if attachment:
                values["form_attachment_id"] = attachment.id
            placement.write(values)
            placement.action_submit_form()

        return self._run(placement, submit, "form_submitted")

    @http.route(
        ["/my/placements/<int:placement_id>/documents/<int:line_id>"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_upload_document(self, placement_id, line_id, document=None, **kwargs):
        placement, _role = self._placement_for_user(placement_id)
        line = request.env["internship.document.request.line"].sudo().browse(line_id).exists()
        if not line or line.placement_id != placement or line.accepted:
            raise request.not_found()

        def upload():
            attachment = self._attachment_from_upload(document, line._name, line.id)
            if not attachment:
                raise UserError(request.env._("Choose a file to upload."))
            line.write({"attachment_id": attachment.id, "rejection_note": False})
            line.request_id.message_post(
                body=request.env._("%(doc)s uploaded via the portal.", doc=line.document_type_id.name)
            )

        return self._run(placement, upload, "uploaded")

    @http.route(
        ["/my/placements/<int:placement_id>/monthly/<int:monthly_id>/submit"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_monthly_submit(
        self,
        placement_id,
        monthly_id,
        days_attended=None,
        total_hours=None,
        absence_reasons=None,
        self_reflection=None,
        **kwargs,
    ):
        placement, role = self._placement_for_user(placement_id)
        monthly = request.env["internship.attendance.monthly"].sudo().browse(monthly_id).exists()
        if role != "student" or not monthly or monthly.placement_id != placement:
            raise request.not_found()

        def submit():
            try:
                attended, hours = float(days_attended or 0), float(total_hours or 0)
            except ValueError as error:
                raise UserError(request.env._("Days and hours must be numbers.")) from error
            monthly.write(
                {
                    "days_attended": attended,
                    "total_hours": hours,
                    "absence_reasons": absence_reasons,
                    "self_reflection": self_reflection,
                }
            )
            monthly.action_student_submit()

        return self._run(placement, submit, "monthly_submitted")

    @http.route(
        ["/my/placements/<int:placement_id>/monthly/<int:monthly_id>/approve"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_monthly_approve(
        self,
        placement_id,
        monthly_id,
        working_as_required=None,
        rating=None,
        strengths=None,
        improvement_areas=None,
        concerns=None,
        **kwargs,
    ):
        placement, role = self._placement_for_user(placement_id)
        monthly = request.env["internship.attendance.monthly"].sudo().browse(monthly_id).exists()
        if role != "manager" or not monthly or monthly.placement_id != placement:
            raise request.not_found()
        if not placement.line_manager_id.can_approve_attendance:
            raise request.not_found()

        def approve():
            if working_as_required not in ("yes", "no") or rating not in ("1", "2", "3", "4", "5"):
                raise UserError(request.env._("Answer 'working as required' and give a rating."))
            monthly.write(
                {
                    "working_as_required": working_as_required,
                    "rating": rating,
                    "strengths": strengths,
                    "improvement_areas": improvement_areas,
                    "concerns": concerns,
                }
            )
            monthly.with_user(request.env.user).sudo().action_company_approve()

        return self._run(placement, approve, "monthly_approved")

    @http.route(["/my/placements/<int:placement_id>/leave"], type="http", auth="user", methods=["POST"], website=True)
    def portal_leave(
        self, placement_id, leave_type=None, date_from=None, date_to=None, notes=None, evidence=None, **kwargs
    ):
        placement, role = self._placement_for_user(placement_id)
        if role != "student" or placement.stage_code not in ("approved", "active", "on_hold"):
            raise request.not_found()

        def request_leave():
            if leave_type not in ("annual", "sick", "university", "other") or not date_from or not date_to:
                raise UserError(request.env._("Choose the leave type and both dates."))
            leave = (
                request.env["internship.leave"]
                .sudo()
                .create(
                    {
                        "placement_id": placement.id,
                        "leave_type": leave_type,
                        "date_from": date_from,
                        "date_to": date_to,
                        "notes": notes,
                    }
                )
            )
            attachment = self._attachment_from_upload(evidence, leave._name, leave.id)
            if attachment:
                leave.evidence_attachment_id = attachment

        return self._run(placement, request_leave, "leave_requested")

    @http.route(
        ["/my/placements/<int:placement_id>/report/<int:attempt_id>"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_submit_report(self, placement_id, attempt_id, report_title=None, report_file=None, **kwargs):
        placement, role = self._placement_for_user(placement_id)
        attempt = request.env["internship.submission"].sudo().browse(attempt_id).exists()
        if role != "student" or not attempt or attempt.placement_id != placement:
            raise request.not_found()

        def submit():
            if not report_file or not getattr(report_file, "filename", None):
                raise UserError(request.env._("Attach your report."))
            content = report_file.read()
            if len(content) > MAX_UPLOAD:
                raise UserError(request.env._("Files must be smaller than 10 MB."))
            attempt.write(
                {
                    "report_title": report_title,
                    "document": base64.b64encode(content),
                    "document_filename": report_file.filename,
                }
            )
            attempt.action_submit()

        return self._run(placement, submit, "report_submitted")

    @http.route(
        ["/my/placements/<int:placement_id>/feedback"], type="http", auth="user", methods=["POST"], website=True
    )
    def portal_feedback(
        self,
        placement_id,
        overall_rating=None,
        learning_quality=None,
        supervision_quality=None,
        would_recommend=None,
        comments=None,
        **kwargs,
    ):
        placement, role = self._placement_for_user(placement_id)
        if role != "student" or placement.feedback_ids or placement.stage_code not in ("completion", "completed"):
            raise request.not_found()

        def give_feedback():
            if overall_rating not in ("1", "2", "3", "4", "5"):
                raise UserError(request.env._("Give an overall rating."))
            request.env["internship.student.feedback"].sudo().create(
                {
                    "placement_id": placement.id,
                    "overall_rating": overall_rating,
                    "learning_quality": learning_quality if learning_quality in ("1", "2", "3", "4", "5") else False,
                    "supervision_quality": supervision_quality
                    if supervision_quality in ("1", "2", "3", "4", "5")
                    else False,
                    "would_recommend": bool(would_recommend),
                    "comments": comments,
                }
            )

        return self._run(placement, give_feedback, "feedback_saved")

    @http.route(
        ["/my/placements/<int:placement_id>/evaluation"], type="http", auth="user", methods=["POST"], website=True
    )
    def portal_evaluation(
        self, placement_id, overall_rating=None, final_feedback=None, skills_gained=None, would_rehire=None, **kwargs
    ):
        placement, role = self._placement_for_user(placement_id)
        if role != "manager" or placement.stage_code != "completion":
            raise request.not_found()

        def evaluate():
            if overall_rating not in ("1", "2", "3", "4", "5"):
                raise UserError(request.env._("Give an overall rating."))
            evaluation = (
                request.env["internship.company.evaluation"]
                .sudo()
                .create(
                    {
                        "placement_id": placement.id,
                        "overall_rating": overall_rating,
                        "final_feedback": final_feedback,
                        "skills_gained": skills_gained,
                        "would_rehire": bool(would_rehire),
                        "submitted_by_id": placement.line_manager_id.id,
                    }
                )
            )
            evaluation.action_submit()

        return self._run(placement, evaluate, "evaluation_submitted")

    @http.route(
        ["/my/placements/<int:placement_id>/certificate"], type="http", auth="user", methods=["POST"], website=True
    )
    def portal_certificate(self, placement_id, **kwargs):
        placement, role = self._placement_for_user(placement_id)
        if role != "manager" or placement.stage_code != "completion":
            raise request.not_found()

        def issue():
            certificate = (
                request.env["internship.certificate"]
                .sudo()
                .create({"placement_id": placement.id, "issued_by_id": placement.line_manager_id.id})
            )
            certificate.action_issue()

        return self._run(placement, issue, "certificate_issued")

    @http.route(["/my/placements/<int:placement_id>/certificate/download"], type="http", auth="user", website=True)
    def portal_certificate_download(self, placement_id, **kwargs):
        placement, _role = self._placement_for_user(placement_id)
        certificate = placement.certificate_ids.filtered("attachment_id")[:1]
        if not certificate:
            raise request.not_found()
        attachment = certificate.attachment_id.sudo()
        return request.make_response(
            attachment.raw,
            headers=[
                ("Content-Type", attachment.mimetype),
                ("Content-Disposition", f'attachment; filename="{attachment.name}"'),
            ],
        )
