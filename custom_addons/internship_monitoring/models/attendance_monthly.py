import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.internship_base.services.activity import default_coordinator, schedule_activity_once

MONTHS = [(str(m), calendar.month_name[m]) for m in range(1, 13)]


class InternshipAttendanceMonthly(models.Model):
    """Monthly attendance and performance record: student submits, company confirms, university reviews."""

    _name = "internship.attendance.monthly"
    _description = "Monthly Attendance Record"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "internship.placement.link.mixin",
        "internship.deadline.mixin",
    ]
    _order = "year desc, month desc, placement_id"

    name = fields.Char(compute="_compute_name", store=True)
    year = fields.Integer(required=True, index=True)
    month = fields.Selection(MONTHS, required=True, index=True)
    date_start = fields.Date(compute="_compute_period", store=True)
    date_end = fields.Date(compute="_compute_period", store=True)

    # Student submission
    days_expected = fields.Float(help="Working days in the period (Monday to Friday) within the placement dates.")
    days_attended = fields.Float(tracking=True)
    total_hours = fields.Float()
    absence_reasons = fields.Text()
    self_reflection = fields.Text()
    student_confirmed = fields.Boolean(readonly=True, copy=False)
    student_confirmed_date = fields.Datetime(readonly=True, copy=False)

    # Leave (approved internship.leave overlapping the period; excluded from absences)
    annual_leave_days = fields.Float(compute="_compute_leave_days", store=True)
    sick_days = fields.Float(compute="_compute_leave_days", store=True)

    # Company confirmation
    working_as_required = fields.Boolean(
        string="Working As Required",
        tracking=True,
        help="Company confirmation. Approving with this unticked escalates to a tripartite meeting.",
    )
    working_as_required_legacy = fields.Char(
        string="Working As Required (v2.0)",
        readonly=True,
        deprecated="Replaced by the working_as_required Boolean in 19.0.2.1",
    )
    concerns = fields.Text()

    # Performance
    rating = fields.Selection(
        [
            ("1", "1 - Poor"),
            ("2", "2 - Below expectations"),
            ("3", "3 - Meets expectations"),
            ("4", "4 - Good"),
            ("5", "5 - Excellent"),
        ],
        tracking=True,
    )
    strengths = fields.Text()
    improvement_areas = fields.Text()
    manager_comments = fields.Text()

    # Approvals
    company_approved_by_id = fields.Many2one("res.users", readonly=True, tracking=True, copy=False)
    company_approved_date = fields.Datetime(readonly=True, copy=False)
    university_reviewed_by_id = fields.Many2one("res.users", readonly=True, tracking=True, copy=False)
    university_reviewed_date = fields.Datetime(readonly=True, copy=False)
    university_comments = fields.Text()

    attendance_pct = fields.Float(
        string="Attendance Pct", compute="_compute_attendance_pct", store=True, aggregator="avg", digits=(5, 1)
    )

    # Escalation
    tripartite_triggered = fields.Boolean(readonly=True, copy=False, tracking=True, index=True)
    trigger_reason = fields.Char(readonly=True, copy=False)
    meeting_id = fields.Many2one("internship.meeting", readonly=True, copy=False, string="Meeting")
    escalation_checked = fields.Boolean(readonly=True, copy=False)

    attendance_ids = fields.One2many("internship.attendance", "monthly_id", string="Daily Log")

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("submitted", "Submitted"),
            ("company_approved", "Company approved"),
            ("university_reviewed", "University reviewed"),
            ("flagged", "Flagged"),
            ("late", "Late"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )

    _unique_period = models.Constraint(
        "unique(placement_id, year, month)", "There is already a monthly record for this placement and month."
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("placement_id.name", "year", "month")
    def _compute_name(self):
        for record in self:
            month = dict(MONTHS).get(record.month, "")
            record.name = f"{record.placement_id.name or ''} {month} {record.year or ''}".strip()

    @api.depends("year", "month")
    def _compute_period(self):
        for record in self:
            if record.year and record.month:
                month = int(record.month)
                record.date_start = date(record.year, month, 1)
                record.date_end = date(record.year, month, calendar.monthrange(record.year, month)[1])
            else:
                record.date_start = record.date_end = False

    @api.depends(
        "date_start",
        "date_end",
        "placement_id.leave_ids.state",
        "placement_id.leave_ids.date_from",
        "placement_id.leave_ids.date_to",
        "placement_id.leave_ids.leave_type",
    )
    def _compute_leave_days(self):
        for record in self:
            leaves = record.placement_id.leave_ids.filtered(lambda leave: leave.state == "approved")
            if not record.date_start:
                record.annual_leave_days = record.sick_days = 0
                continue
            sick = leaves.filtered(lambda leave: leave.leave_type == "sick")
            record.sick_days = sick._overlap_days(record.date_start, record.date_end)
            record.annual_leave_days = (leaves - sick)._overlap_days(record.date_start, record.date_end)

    @api.depends("days_attended", "days_expected", "annual_leave_days", "sick_days")
    def _compute_attendance_pct(self):
        for record in self:
            expected = record.days_expected - record.annual_leave_days - record.sick_days
            record.attendance_pct = min(100.0, 100.0 * record.days_attended / expected) if expected > 0 else 0.0

    @api.constrains("days_attended", "days_expected")
    def _check_days(self):
        for record in self:
            if record.days_attended < 0 or record.days_expected < 0:
                raise ValidationError(self.env._("Days cannot be negative."))

    # ------------------------------------------------------------------
    # Creation helpers
    # ------------------------------------------------------------------
    @api.model
    def _expected_days(self, placement, start, end):
        lo = max(start, placement.actual_start or placement.planned_start or start)
        hi = min(end, placement.actual_end or placement.planned_end or end)
        return self.env["internship.leave"]._working_days_between(lo, hi)

    @api.model
    def _due_date_for(self, placement, year, month):
        due_day = placement.program_id._get_rule("monthly_due_day")
        next_month = date(year, month, 1) + relativedelta(months=1)
        last_day = calendar.monthrange(next_month.year, next_month.month)[1]
        return next_month.replace(day=min(max(due_day, 1), last_day))

    @api.model
    def _ensure_for(self, placement, on_date=None):
        """Create the monthly record for `on_date`'s month if it does not exist yet."""
        on_date = on_date or fields.Date.context_today(self)
        year, month = on_date.year, on_date.month
        existing = self.search(
            [("placement_id", "=", placement.id), ("year", "=", year), ("month", "=", str(month))], limit=1
        )
        if existing:
            return existing
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        return self.create(
            {
                "placement_id": placement.id,
                "year": year,
                "month": str(month),
                "days_expected": self._expected_days(placement, start, end),
                "due_date": self._due_date_for(placement, year, month),
            }
        )

    def _sync_from_daily(self):
        """When a daily log exists, it is the source of days attended."""
        credit = {"present": 1.0, "late": 1.0, "half_day": 0.5}
        for record in self:
            if record.attendance_ids and record.state in ("pending", "late"):
                record.days_attended = sum(credit.get(day.status, 0.0) for day in record.attendance_ids)
        return True

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_student_submit(self):
        for record in self:
            if record.state not in ("pending", "late"):
                raise UserError(self.env._("This record has already been submitted."))
        self.write(
            {
                "state": "submitted",
                "student_confirmed": True,
                "student_confirmed_date": fields.Datetime.now(),
                "submitted_date": fields.Date.context_today(self),
            }
        )
        for record in self:
            schedule_activity_once(
                record,
                record.placement_id._company_owner(),
                self.env._("Confirm monthly attendance %(name)s", name=record.name),
                deadline=record.due_date,
            )
        return True

    def _check_can_company_approve(self):
        user = self.env.user
        for record in self:
            manager = record.placement_id.line_manager_id
            is_line_manager = manager.user_id == user
            if is_line_manager and not manager.can_approve_attendance:
                raise UserError(self.env._("You are not authorised to approve attendance."))
            if (
                user.has_group("internship_base.group_line_manager")
                and not is_line_manager
                and not user.has_group("internship_base.group_platform_administrator")
            ):
                raise UserError(self.env._("Only the placement's line manager can approve this record."))
        return True

    def action_company_approve(self):
        for record in self:
            if record.state != "submitted":
                raise UserError(self.env._("Only submitted records can be approved by the company."))
            if not record.rating:
                raise UserError(self.env._("Give a performance rating before approving."))
        self._check_can_company_approve()
        self.write(
            {
                "state": "company_approved",
                "company_approved_by_id": self.env.user.id,
                "company_approved_date": fields.Datetime.now(),
            }
        )
        self._check_escalation()
        return True

    def action_university_review(self):
        for record in self:
            if record.state not in ("company_approved", "flagged"):
                raise UserError(self.env._("The company must approve the record before the university reviews it."))
        self.write(
            {
                "state": "university_reviewed",
                "university_reviewed_by_id": self.env.user.id,
                "university_reviewed_date": fields.Datetime.now(),
            }
        )
        return True

    def action_flag(self, reason=None, note=None):
        label = note or (reason.name if hasattr(reason, "name") else "") or self.env._("Flagged by the university")
        self.write({"state": "flagged"})
        self._trigger_tripartite(label)
        return True

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------
    def _escalation_reasons(self):
        self.ensure_one()
        program = self.placement_id.program_id
        reasons = []
        threshold = program._get_rule("tripartite_attendance_pct")
        if self.days_expected and self.attendance_pct < threshold:
            reasons.append(
                self.env._("Attendance %(pct).0f%% is below %(limit).0f%%", pct=self.attendance_pct, limit=threshold)
            )
        rating_limit = program._get_rule("tripartite_rating_threshold")
        if self.rating and int(self.rating) <= rating_limit:
            reasons.append(
                self.env._("Rating %(rating)s is at or below %(limit)s", rating=self.rating, limit=rating_limit)
            )
        if not self.working_as_required:
            reasons.append(self.env._("Company says the student is not working as required"))
        return reasons

    def _check_escalation(self):
        for record in self:
            reasons = record._escalation_reasons()
            record.escalation_checked = True
            if reasons and not record.tripartite_triggered:
                trigger = (
                    "auto_not_working"
                    if not record.working_as_required
                    else (
                        "auto_rating"
                        if record.rating
                        and int(record.rating)
                        <= record.placement_id.program_id._get_rule("tripartite_rating_threshold")
                        else "auto_attendance"
                    )
                )
                record._trigger_tripartite("; ".join(reasons), trigger)
        return True

    def _trigger_tripartite(self, reason, trigger="manual"):
        Meeting = self.env["internship.meeting"]
        for record in self:
            placement = record.placement_id
            meeting = Meeting.create(
                {
                    "placement_id": placement.id,
                    "meeting_type": "tripartite",
                    "title": self.env._("Tripartite meeting: %(name)s", name=record.name),
                    "meeting_date": fields.Datetime.now() + relativedelta(days=7),
                    "trigger": trigger,
                    "trigger_reason": reason,
                    "monthly_id": record.id,
                }
            )
            meeting._add_default_attendees()
            record.write({"tripartite_triggered": True, "trigger_reason": reason, "meeting_id": meeting.id})
            record.message_post(body=self.env._("Tripartite meeting triggered: %(reason)s", reason=reason))
            tutor = placement.tutor_id or placement.user_id or default_coordinator(self.env)
            schedule_activity_once(
                placement,
                tutor,
                self.env._("Arrange tripartite meeting (%(month)s)", month=record.name),
                note=reason,
            )
        self.placement_id._recompute_risk()
        return True

    # ------------------------------------------------------------------
    # Crons
    # ------------------------------------------------------------------
    @api.model
    def _cron_create_monthly(self):
        today = fields.Date.context_today(self)
        created = self.browse()
        for placement in self.env["internship.placement"].search([("stage_code", "in", ("active", "on_hold"))]):
            before = self.search_count([("placement_id", "=", placement.id)])
            record = self._ensure_for(placement, today)
            if self.search_count([("placement_id", "=", placement.id)]) > before:
                created |= record
        return created

    @api.model
    def _cron_reminders(self):
        """Remind students before the due date; mark records late after due date + grace."""
        today = fields.Date.context_today(self)
        template = self.env.ref("internship_monitoring.mail_template_monthly_reminder", raise_if_not_found=False)
        pending = self.search([("state", "in", ("pending", "late"))])
        for record in pending:
            grace = record.placement_id.program_id._get_rule("monthly_late_grace_days")
            if record.due_date and record.state == "pending" and today > record.due_date + relativedelta(days=grace):
                record.state = "late"
            remind_from = record.due_date - relativedelta(days=3) if record.due_date else None
            if (
                remind_from
                and today >= remind_from
                and record.last_reminder_date != today
                and record.reminder_count < 5
            ):
                if template and record.placement_id.student_id.email:
                    template.send_mail(record.id)
                record._register_reminder()
        self._refresh_lateness()
        return True

    @api.model
    def _cron_escalation(self):
        records = self.search(
            [("state", "in", ("company_approved", "university_reviewed")), ("escalation_checked", "=", False)]
        )
        records._check_escalation()
        return records
