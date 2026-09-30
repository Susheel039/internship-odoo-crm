from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.internship_base.models.company_site import WORK_MODES
from odoo.addons.internship_base.services.activity import default_coordinator, schedule_activity_once

PHASE_1_OPEN = ("form_requested", "under_review", "more_docs", "meeting", "agreement")
FILLED_STAGES = ("approved", "active", "on_hold", "completion", "completed")


class InternshipPlacement(models.Model):
    """The hub of v2: one record per student internship, from accepted offer to closure.

    Stage changes go through `_move_to()`, guarded by `_check_transition()`. Other modules
    hook in through the `_on_*` methods instead of changing this model.
    """

    _name = "internship.placement"
    _description = "Internship Placement"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "priority desc, id desc"

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(string="Reference", required=True, default="New", copy=False, readonly=True, index=True)
    stage_id = fields.Many2one(
        "internship.placement.stage",
        string="Stage",
        required=True,
        tracking=True,
        index=True,
        copy=False,
        ondelete="restrict",
        group_expand="_read_group_stage_ids",
        default=lambda self: self.env["internship.placement.stage"]._get_by_code("form_requested"),
    )
    stage_code = fields.Char(related="stage_id.code", store=True, index=True)
    phase = fields.Selection(related="stage_id.phase", store=True, index=True)
    is_closed = fields.Boolean(related="stage_id.is_closed", store=True, index=True)
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Important"), ("2", "High"), ("3", "Urgent")], default="0", index=True
    )
    color = fields.Integer()
    user_id = fields.Many2one(
        "res.users", string="Coordinator", tracking=True, index=True, default=lambda self: self.env.user
    )
    active = fields.Boolean(default=True, tracking=True)

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------
    application_id = fields.Many2one("internship.application", index=True, ondelete="set null", copy=False)
    student_id = fields.Many2one(
        "internship.student", required=True, index=True, ondelete="restrict", tracking=True, string="Student"
    )
    university_id = fields.Many2one(
        related="student_id.university_id", store=True, index=True, string="University", readonly=True
    )
    program_id = fields.Many2one("internship.program", string="Programme", index=True, tracking=True)
    academic_year_id = fields.Many2one("internship.academic.year", string="Academic Year", index=True)
    opportunity_id = fields.Many2one("internship.opportunity", index=True, ondelete="set null", tracking=True)
    internship_company_id = fields.Many2one(
        "internship.company", string="Company", required=True, index=True, ondelete="restrict", tracking=True
    )
    line_manager_id = fields.Many2one(
        "internship.line.manager",
        string="Line Manager",
        index=True,
        tracking=True,
        domain="[('company_id', '=', internship_company_id)]",
    )
    tutor_id = fields.Many2one("res.users", string="Academic Tutor", index=True, tracking=True)
    site_id = fields.Many2one(
        "internship.company.site", string="Site", domain="[('company_id', '=', internship_company_id)]"
    )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    placement_source = fields.Selection(
        [("platform", "Found on the platform"), ("self_sourced", "Self-sourced by student")],
        default="platform",
        required=True,
    )
    is_paid = fields.Boolean(string="Paid", default=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.ref("base.GBP", raise_if_not_found=False)
    )
    salary_amount = fields.Monetary(currency_field="currency_id")
    work_mode = fields.Selection(WORK_MODES, default="on_site")
    hours_per_week = fields.Float(default=37.5, tracking=True)
    role_title = fields.Char(tracking=True)

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------
    planned_start = fields.Date(tracking=True)
    planned_end = fields.Date(tracking=True)
    actual_start = fields.Date(tracking=True, copy=False)
    actual_end = fields.Date(tracking=True, copy=False)
    duration_weeks = fields.Integer(compute="_compute_duration_weeks", store=True)

    # Offer
    offer_letter_attachment_id = fields.Many2one("ir.attachment", string="Offer Letter")
    offer_issue_date = fields.Date(tracking=True)
    offer_expiry_date = fields.Date(tracking=True)
    offer_accepted_date = fields.Date(tracking=True)

    # Form request (student -> company)
    form_requested_by_id = fields.Many2one("res.users", string="Form Requested By", copy=False)
    form_requested_date = fields.Date(tracking=True, copy=False)
    form_contact_email = fields.Char(string="Form Contact E-mail")
    form_due_date = fields.Date(compute="_compute_form_due_date", store=True, tracking=True)
    form_reminder_count = fields.Integer(copy=False)
    form_last_reminder_date = fields.Date(copy=False)

    # Internship form (company fills)
    learning_objectives = fields.Html()
    hs_confirmed = fields.Boolean(string="Health & Safety Confirmed", tracking=True)
    form_submitted_date = fields.Date(tracking=True, copy=False)
    form_attachment_id = fields.Many2one("ir.attachment", string="Signed Internship Form")
    supporting_attachment_ids = fields.Many2many(
        "ir.attachment",
        "internship_placement_supporting_attachment_rel",
        "placement_id",
        "attachment_id",
        string="Supporting Documents",
    )

    # University review
    review_ids = fields.One2many("internship.university.review", "placement_id", string="Reviews")
    review_round = fields.Integer(compute="_compute_review_round", store=True)

    # Health
    risk_flag = fields.Selection(
        [("green", "On track"), ("amber", "Needs attention"), ("red", "At risk")],
        compute="_compute_risk_flag",
        store=True,
        index=True,
        tracking=True,
    )
    risk_reason = fields.Char(compute="_compute_risk_flag", store=True)

    # Termination
    termination_date = fields.Date(tracking=True, copy=False)
    termination_initiated_by = fields.Selection(
        [("student", "Student"), ("company", "Company"), ("university", "University")], tracking=True, copy=False
    )
    termination_reason_id = fields.Many2one(
        "internship.reason", domain=[("reason_type", "=", "termination")], tracking=True, copy=False
    )
    termination_notes = fields.Text(copy=False)
    hold_reason_id = fields.Many2one("internship.reason", domain=[("reason_type", "=", "hold")], tracking=True)

    # Related workflow records defined in this module
    document_request_ids = fields.One2many("internship.document.request", "placement_id")
    document_ids = fields.One2many("internship.document", "placement_id")
    leave_ids = fields.One2many("internship.leave", "placement_id")
    change_request_ids = fields.One2many("internship.change.request", "placement_id")

    document_request_count = fields.Integer(compute="_compute_counts")
    document_count = fields.Integer(compute="_compute_counts")
    leave_count = fields.Integer(compute="_compute_counts")
    change_request_count = fields.Integer(compute="_compute_counts")
    review_count = fields.Integer(compute="_compute_counts")

    properties = fields.Properties("Properties", definition="program_id.placement_properties_definition", copy=True)

    # Only one placement per student in a non-closed stage (archived duplicates are allowed
    # so legacy data can be migrated without loss).
    _one_open_placement_per_student = models.UniqueIndex(
        "(student_id) WHERE is_closed IS NOT TRUE AND active IS TRUE",
        "This student already has an open placement.",
    )

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("internship.placement") or "New"
        placements = super().create(vals_list)
        for placement in placements:
            if not placement.program_id and placement.student_id.program_id:
                placement.program_id = placement.student_id.program_id
            if not placement.tutor_id and placement.student_id.academic_tutor_id:
                placement.tutor_id = placement.student_id.academic_tutor_id
        return placements

    def _compute_access_url(self):
        result = super()._compute_access_url()
        for placement in self:
            placement.access_url = f"/my/placements/{placement.id}"
        return result

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([], order=stages._order)

    @api.constrains("student_id", "stage_id", "active")
    def _check_one_open_placement(self):
        for placement in self.filtered(lambda p: p.active and not p.is_closed):
            clash = self.search_count(
                [
                    ("id", "!=", placement.id),
                    ("student_id", "=", placement.student_id.id),
                    ("is_closed", "=", False),
                    ("active", "=", True),
                ],
                limit=1,
            )
            if clash:
                raise ValidationError(
                    self.env._("%(student)s already has an open placement.", student=placement.student_id.name)
                )

    @api.constrains("planned_start", "planned_end")
    def _check_dates(self):
        for placement in self:
            if placement.planned_start and placement.planned_end and placement.planned_start > placement.planned_end:
                raise ValidationError(self.env._("The planned start must be before the planned end."))

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("planned_start", "planned_end", "actual_start", "actual_end")
    def _compute_duration_weeks(self):
        for placement in self:
            start = placement.actual_start or placement.planned_start
            end = placement.actual_end or placement.planned_end
            placement.duration_weeks = ((end - start).days + 1 + 6) // 7 if start and end and end >= start else 0

    @api.depends("form_requested_date", "program_id")
    def _compute_form_due_date(self):
        for placement in self:
            if placement.form_requested_date:
                days = placement.program_id._get_rule("form_due_days")
                placement.form_due_date = placement.form_requested_date + relativedelta(days=days)
            else:
                placement.form_due_date = False

    @api.depends("document_request_ids.state")
    def _compute_review_round(self):
        for placement in self:
            completed = placement.document_request_ids.filtered(lambda r: r.state == "complete")
            placement.review_round = 1 + len(completed)

    @api.depends("stage_code", "document_request_ids.state", "form_due_date", "form_submitted_date")
    def _compute_risk_flag(self):
        order = {"green": 0, "amber": 1, "red": 2}
        for placement in self:
            signals = placement._get_risk_signals()
            if not signals:
                placement.risk_flag = "green"
                placement.risk_reason = False
                continue
            level = max((s[0] for s in signals), key=order.get)
            placement.risk_flag = level
            placement.risk_reason = "; ".join(reason for lvl, reason in signals if lvl == level)

    def _get_risk_signals(self):
        """Return [(level, reason)] for this placement. Other modules extend this."""
        self.ensure_one()
        signals = []
        if self.is_closed:
            return signals
        today = fields.Date.context_today(self)
        if self.document_request_ids.filtered(lambda r: r.state == "overdue"):
            signals.append(("amber", self.env._("Overdue document request")))
        if self.stage_code == "form_requested" and self.form_due_date and self.form_due_date < today:
            signals.append(("amber", self.env._("Internship form overdue")))
        if self.stage_code == "on_hold":
            signals.append(("amber", self.env._("Placement on hold")))
        return signals

    def _compute_counts(self):
        for placement in self:
            placement.document_request_count = len(placement.document_request_ids)
            placement.document_count = len(placement.document_ids)
            placement.leave_count = len(placement.leave_ids)
            placement.change_request_count = len(placement.change_request_ids)
            placement.review_count = len(placement.review_ids)

    def _review_checklist(self):
        """Facts the university checks before approving (see internship.university.review)."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        reference = self.planned_end or self.planned_start or today
        company = self.internship_company_id
        student = self.student_id.sudo()
        visa_ok = not student.visa_required or (
            student.placement_permitted
            and (not student.term_time_hour_limit or self.hours_per_week <= student.term_time_hour_limit)
        )
        return {
            "company_vetted": bool(company) and company._is_vetted(today),
            "insurance_valid": bool(company.insurance_expiry) and company.insurance_expiry >= reference,
            "rtw_ok": student.rtw_status == "verified" and (not student.rtw_expiry or student.rtw_expiry >= reference),
            "visa_ok": bool(visa_ok),
            "form_complete": bool(self.learning_objectives and self.hs_confirmed and self.form_attachment_id),
        }

    # ------------------------------------------------------------------
    # Stage machinery
    # ------------------------------------------------------------------
    def _stage(self, code):
        return self.env["internship.placement.stage"]._get_by_code(code)

    def _check_transition(self, from_codes, to_code):
        """Raise unless every placement is in one of `from_codes`. Returns the target stage."""
        target = self._stage(to_code)
        invalid = self.filtered(lambda p: p.stage_code not in from_codes)
        if invalid:
            allowed = ", ".join(self._stage(code).name for code in from_codes)
            raise UserError(
                self.env._(
                    "%(placement)s cannot move to '%(target)s' from '%(current)s'. Allowed from: %(allowed)s.",
                    placement=invalid[0].name,
                    target=target.name,
                    current=invalid[0].stage_id.name,
                    allowed=allowed,
                )
            )
        return target

    def _move_to(self, to_code, from_codes, **values):
        target = self._check_transition(from_codes, to_code)
        values["stage_id"] = target.id
        self.write(values)
        return True

    # ------------------------------------------------------------------
    # Creation from an accepted application
    # ------------------------------------------------------------------
    @api.model
    def _prepare_from_application(self, application):
        opportunity = application.opportunity_id
        company = application.company_id or opportunity.company_id
        return {
            "application_id": application.id,
            "student_id": application.student_id.id,
            "opportunity_id": opportunity.id,
            "internship_company_id": company.id,
            "program_id": (opportunity.program_id or application.student_id.program_id).id,
            "academic_year_id": application.student_id.academic_year_id.id,
            "line_manager_id": application.interviewer_id.id,
            "site_id": opportunity.site_id.id,
            "role_title": opportunity.job_title or opportunity.name,
            "work_mode": opportunity.work_mode or "on_site",
            "hours_per_week": opportunity.hours_per_week or 37.5,
            "is_paid": opportunity.is_paid,
            "salary_amount": opportunity.salary_amount,
            "currency_id": opportunity.currency_id.id,
            "planned_start": opportunity.start_date,
            "planned_end": opportunity.end_date,
            "offer_accepted_date": application.response_date or fields.Date.context_today(self),
            "form_requested_by_id": self.env.user.id,
            "form_requested_date": fields.Date.context_today(self),
            "form_contact_email": company.contact_email or company.partner_id.email,
            "stage_id": self._stage("form_requested").id,
        }

    @api.model
    def _create_from_application(self, application):
        application.ensure_one()
        if application.placement_id:
            return application.placement_id
        placement = self.create(self._prepare_from_application(application))
        application.placement_id = placement
        placement._request_company_form()
        return placement

    def _company_owner(self):
        """User who should act for the company: line manager, company user, else the coordinator."""
        self.ensure_one()
        return (
            self.line_manager_id.user_id
            or self.internship_company_id.user_ids[:1]
            or self.user_id
            or default_coordinator(self.env)
        )

    def _request_company_form(self):
        template = self.env.ref("internship_placement.mail_template_form_request", raise_if_not_found=False)
        for placement in self:
            schedule_activity_once(
                placement,
                placement._company_owner(),
                self.env._("Complete the internship form"),
                deadline=placement.form_due_date,
            )
            if template and placement.form_contact_email:
                template.send_mail(placement.id)
        return True

    # ------------------------------------------------------------------
    # Transitions (see docs/WORKFLOW.md)
    # ------------------------------------------------------------------
    def action_submit_form(self):
        """Company submits the internship form: form_requested/more_docs -> under_review."""
        for placement in self:
            missing = []
            if not placement.learning_objectives or placement.learning_objectives in ("<p><br></p>", "<p></p>"):
                missing.append(self.env._("learning objectives"))
            if not placement.hs_confirmed:
                missing.append(self.env._("health and safety confirmation"))
            if not placement.form_attachment_id:
                missing.append(self.env._("signed internship form"))
            if missing:
                raise UserError(self.env._("Before submitting the form, add: %(missing)s.", missing=", ".join(missing)))
        self._move_to("under_review", ("form_requested",), form_submitted_date=fields.Date.context_today(self))
        for placement in self:
            schedule_activity_once(
                placement,
                placement.user_id or default_coordinator(self.env),
                self.env._("Review the internship form"),
            )
        return True

    def action_open_review(self):
        """University decision: open a review for the current round."""
        self.ensure_one()
        if self.stage_code not in ("under_review", "meeting"):
            raise UserError(self.env._("A decision can only be recorded while the placement is under review."))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("University Decision"),
            "res_model": "internship.university.review",
            "view_mode": "form",
            "target": "new",
            "context": {"default_placement_id": self.id, "default_round_no": self.review_round},
        }

    def action_schedule_meeting(self):
        self._move_to("meeting", ("under_review",))
        return self._create_review_meeting()

    def _create_review_meeting(self):
        """Hook: internship_monitoring creates the university-company meeting."""
        return True

    def action_meeting_no_more_docs(self):
        return self._move_to("under_review", ("meeting",))

    def action_meeting_more_docs(self):
        self._move_to("more_docs", ("meeting",))
        return self.action_request_documents()

    def action_request_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Request Documents"),
            "res_model": "internship.document.request.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_placement_id": self.id},
        }

    def _on_document_request_complete(self, request):
        """All mandatory documents accepted: back to review for the next round."""
        for placement in self.filtered(lambda p: p.stage_code == "more_docs"):
            if placement.document_request_ids.filtered(
                lambda r: r != request and r.state in ("open", "partial", "overdue")
            ):
                continue
            placement._move_to("under_review", ("more_docs",))
            placement.message_post(
                body=self.env._(
                    "All requested documents accepted. Review round %(round)s.", round=placement.review_round
                )
            )
        return True

    def _university_approve(self, review):
        self._move_to("agreement", ("under_review", "meeting"))
        self._on_university_approved(review)
        return True

    def _on_university_approved(self, review):
        """Hook: internship_agreement generates the three-party agreement."""
        return True

    def _university_reject(self, review):
        self._move_to("rejected", ("under_review", "meeting", "more_docs"))
        template = self.env.ref("internship_placement.mail_template_university_decision", raise_if_not_found=False)
        for placement in self:
            placement.message_post(
                body=self.env._(
                    "Rejected by the university: %(reason)s",
                    reason=review.rejection_reason_id.name or review.comments or "-",
                ),
                subtype_xmlid="mail.mt_comment",
            )
            if template and placement.student_id.email:
                template.send_mail(review.id)
        return True

    def _mark_agreement_complete(self):
        """Fully signed agreement: agreement -> approved, withdraw the student's other applications."""
        self._move_to("approved", ("agreement",))
        reason = self.env.ref("internship_base.reason_withdrawal_other_approved", raise_if_not_found=False)
        label = reason.name if reason else self.env._("Another internship approved")
        for placement in self:
            others = placement.student_id.application_ids - placement.application_id
            withdrawn = others._auto_withdraw(label)
            placement.message_post(
                body=self.env._(
                    "Agreement fully signed. Placement approved; %(count)s other application(s) withdrawn.",
                    count=len(withdrawn),
                )
            )
        return True

    def action_mark_agreement_signed(self):
        """Manual fallback when the agreement was signed outside Odoo."""
        if not self.env.user.has_group("internship_base.group_platform_administrator") and not self.env.user.has_group(
            "internship_base.group_university_administrator"
        ):
            raise UserError(self.env._("Only university or platform administrators can confirm an offline agreement."))
        return self._mark_agreement_complete()

    def action_start(self):
        self._move_to("active", ("approved",), actual_start=fields.Date.context_today(self))
        self._on_started()
        return True

    def _on_started(self):
        """Hook: internship_monitoring creates the first monthly record."""
        return True

    def action_hold(self, reason=None, note=None):
        if not reason:
            raise UserError(self.env._("A reason is required to put a placement on hold."))
        self._move_to("on_hold", ("active",), hold_reason_id=reason.id if hasattr(reason, "id") else reason)
        if note:
            for placement in self:
                placement.message_post(body=note)
        return True

    def action_resume(self):
        return self._move_to("active", ("on_hold",))

    def _terminate(self, initiated_by, reason, notes=None, date=None):
        if not initiated_by or not reason:
            raise UserError(self.env._("Termination needs who initiated it and a reason."))
        self._move_to(
            "terminated",
            ("active", "on_hold"),
            termination_date=date or fields.Date.context_today(self),
            termination_initiated_by=initiated_by,
            termination_reason_id=reason.id if hasattr(reason, "id") else reason,
            termination_notes=notes,
            actual_end=date or fields.Date.context_today(self),
        )
        self._create_exit_meeting()
        return True

    def _create_exit_meeting(self):
        """Hook: internship_monitoring schedules the exit meeting."""
        return True

    def action_terminate(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Terminate Placement"),
            "res_model": "internship.terminate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_placement_id": self.id},
        }

    def action_to_completion(self):
        self._move_to("completion", ("active",))
        self._on_completion_started()
        return True

    def _on_completion_started(self):
        """Hook: internship_completion creates report attempt 1 and the completion checklist."""
        return True

    def _mark_completed(self):
        values = {}
        if not all(self.mapped("actual_end")):
            values["actual_end"] = fields.Date.context_today(self)
        return self._move_to("completed", ("completion",), **values)

    def _mark_failed(self):
        return self._move_to("failed", ("completion",), actual_end=fields.Date.context_today(self))

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def _action_related(self, model, name, extra_context=None):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": [("placement_id", "=", self.id)],
            "context": {"default_placement_id": self.id, **(extra_context or {})},
        }

    def action_view_document_requests(self):
        return self._action_related("internship.document.request", self.env._("Document Requests"))

    def action_view_documents(self):
        return self._action_related("internship.document", self.env._("Documents"))

    def action_view_leave(self):
        return self._action_related("internship.leave", self.env._("Leave"))

    def action_view_change_requests(self):
        return self._action_related("internship.change.request", self.env._("Change Requests"))

    def action_view_reviews(self):
        return self._action_related("internship.university.review", self.env._("University Reviews"))

    # ------------------------------------------------------------------
    # Crons
    # ------------------------------------------------------------------
    @api.model
    def _cron_start_end(self):
        """approved -> active on planned_start; active -> completion after planned_end."""
        today = fields.Date.context_today(self)
        to_start = self.search([("stage_code", "=", "approved"), ("planned_start", "<=", today)])
        for placement in to_start:
            placement.action_start()
        to_finish = self.search([("stage_code", "=", "active"), ("planned_end", "<", today)])
        for placement in to_finish:
            placement.action_to_completion()
        return len(to_start), len(to_finish)

    @api.model
    def _cron_form_reminders(self):
        """Chase overdue internship forms (once per 3 days, at most 3 times)."""
        today = fields.Date.context_today(self)
        template = self.env.ref("internship_placement.mail_template_form_request", raise_if_not_found=False)
        placements = self.search(
            [("stage_code", "=", "form_requested"), ("form_due_date", "<", today), ("form_reminder_count", "<", 3)]
        )
        chased = self.browse()
        for placement in placements:
            last = placement.form_last_reminder_date
            if last and last > today - relativedelta(days=3):
                continue
            if template and placement.form_contact_email:
                template.send_mail(placement.id)
            placement.write(
                {"form_reminder_count": placement.form_reminder_count + 1, "form_last_reminder_date": today}
            )
            schedule_activity_once(
                placement, placement.user_id or default_coordinator(self.env), self.env._("Internship form overdue")
            )
            chased |= placement
        self.env["internship.document.request"]._cron_reminders()
        self.search([("is_closed", "=", False)])._recompute_risk()
        return chased

    def _recompute_risk(self):
        """Refresh the stored risk flag (it depends on today's date as well as on fields)."""
        if self:
            self.env.add_to_compute(self._fields["risk_flag"], self)
            self.env.add_to_compute(self._fields["risk_reason"], self)
            self.flush_recordset(["risk_flag", "risk_reason"])
        return True
