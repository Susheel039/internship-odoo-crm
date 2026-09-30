from odoo import api, fields, models
from odoo.exceptions import UserError


class InternshipUniversityReview(models.Model):
    """One university review round of a placement: checklist plus decision."""

    _name = "internship.university.review"
    _description = "University Review"
    _inherit = ["mail.thread", "internship.placement.link.mixin"]
    _order = "placement_id, round_no desc"

    round_no = fields.Integer(string="Round", default=1, required=True)
    reviewer_id = fields.Many2one("res.users", string="Reviewer", default=lambda self: self.env.user, tracking=True)
    review_date = fields.Datetime(default=fields.Datetime.now, tracking=True)

    # Checklist: computed from the placement when the review is opened, editable by the reviewer.
    chk_company_vetted = fields.Boolean(string="Company vetted", compute="_compute_checks", store=True, readonly=False)
    chk_insurance_valid = fields.Boolean(
        string="Insurance valid", compute="_compute_checks", store=True, readonly=False
    )
    chk_rtw_ok = fields.Boolean(string="Right to work verified", compute="_compute_checks", store=True, readonly=False)
    chk_visa_ok = fields.Boolean(string="Visa conditions met", compute="_compute_checks", store=True, readonly=False)
    chk_form_complete = fields.Boolean(
        string="Internship form complete", compute="_compute_checks", store=True, readonly=False
    )

    comments = fields.Text()
    decision = fields.Selection(
        [("approve", "Approve"), ("more_docs", "More documents needed"), ("reject", "Reject")], tracking=True
    )
    rejection_reason_id = fields.Many2one(
        "internship.reason", domain=[("reason_type", "=", "university_rejection")], tracking=True
    )
    decided = fields.Boolean(readonly=True, copy=False)
    student_notified_date = fields.Datetime(readonly=True, copy=False)

    @api.depends("placement_id", "round_no")
    def _compute_display_name(self):
        for review in self:
            review.display_name = self.env._(
                "%(placement)s - round %(round)s", placement=review.placement_id.name or "", round=review.round_no
            )

    @api.depends("placement_id")
    def _compute_checks(self):
        for review in self:
            checks = review.placement_id._review_checklist() if review.placement_id else {}
            review.chk_company_vetted = checks.get("company_vetted", False)
            review.chk_insurance_valid = checks.get("insurance_valid", False)
            review.chk_rtw_ok = checks.get("rtw_ok", False)
            review.chk_visa_ok = checks.get("visa_ok", False)
            review.chk_form_complete = checks.get("form_complete", False)

    def action_refresh_checks(self):
        self.env.add_to_compute(self._fields["chk_company_vetted"], self)
        for name in ("chk_insurance_valid", "chk_rtw_ok", "chk_visa_ok", "chk_form_complete"):
            self.env.add_to_compute(self._fields[name], self)
        self.flush_recordset()
        return True

    def action_decide(self):
        for review in self:
            if review.decided:
                raise UserError(self.env._("This review already has a decision."))
            if not review.decision:
                raise UserError(self.env._("Choose a decision first."))
            placement = review.placement_id
            if review.decision == "approve":
                missing = [
                    review._fields[name].string
                    for name in (
                        "chk_company_vetted",
                        "chk_insurance_valid",
                        "chk_rtw_ok",
                        "chk_visa_ok",
                        "chk_form_complete",
                    )
                    if not review[name]
                ]
                if missing:
                    raise UserError(
                        self.env._(
                            "Tick every checklist item before approving. Missing: %(missing)s.",
                            missing=", ".join(missing),
                        )
                    )
                review.decided = True
                placement._university_approve(review)
            elif review.decision == "more_docs":
                review.decided = True
                placement._move_to("more_docs", ("under_review", "meeting"))
                return placement.action_request_documents()
            else:
                if not review.rejection_reason_id:
                    raise UserError(self.env._("A rejection reason is required."))
                review.decided = True
                placement._university_reject(review)
                review.student_notified_date = fields.Datetime.now()
        return {"type": "ir.actions.act_window_close"}
