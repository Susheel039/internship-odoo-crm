from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class InternshipMeeting(models.Model):
    _name = "internship.meeting"
    _description = "Internship Meeting"
    _order = "meeting_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Meeting Reference", required=True, default="New")
    student_id = fields.Many2one(
        "internship.student",
        string="Student",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    opportunity_id = fields.Many2one(
        "internship.opportunity",
        string="Opportunity",
        ondelete="restrict",
        tracking=True,
    )
    company_id = fields.Many2one(
        "internship.company",
        string="Company",
        related="opportunity_id.company_id",
        store=True,
        readonly=True,
    )
    meeting_date = fields.Datetime(
        string="Meeting Date",
        default=fields.Datetime.now,
        tracking=True,
    )
    # Keys are only ever added (see CONTRIBUTING.md); the four originals are unchanged.
    meeting_type = fields.Selection(
        [
            ("checkin", "Check-in"),
            ("review", "Review"),
            ("feedback", "Feedback"),
            ("support", "Support"),
            ("interview", "Interview"),
            ("university_company", "University-company meeting"),
            ("tripartite", "Tripartite meeting"),
            ("exit", "Exit meeting"),
        ],
        string="Type",
        default="review",
        tracking=True,
        index=True,
    )
    summary = fields.Text(string="Minutes")
    next_action = fields.Text(string="Action Items")
    active = fields.Boolean(default=True, tracking=True)

    # v2
    placement_id = fields.Many2one("internship.placement", index=True, ondelete="set null", tracking=True)
    internship_company_id = fields.Many2one(
        related="placement_id.internship_company_id", store=True, index=True, string="Placement Company"
    )
    university_id = fields.Many2one(related="placement_id.university_id", store=True, index=True)
    title = fields.Char()
    duration_minutes = fields.Integer(default=60)
    calendar_event_id = fields.Many2one("calendar.event", copy=False, readonly=True)
    video_url = fields.Char(string="Video Link")
    trigger = fields.Selection(
        [
            ("manual", "Manual"),
            ("auto_attendance", "Low attendance"),
            ("auto_rating", "Low rating"),
            ("auto_not_working", "Not working as required"),
        ],
        default="manual",
        tracking=True,
    )
    trigger_reason = fields.Char()
    monthly_id = fields.Many2one("internship.attendance.monthly", index=True, ondelete="set null")
    attendee_ids = fields.One2many("internship.meeting.attendee", "meeting_id", string="Attendees")
    additional_docs_needed = fields.Boolean(help="On completion, open the document request wizard.")
    follow_up_date = fields.Date(tracking=True)
    state = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("completed", "Completed"),
            ("rescheduled", "Rescheduled"),
            ("cancelled", "Cancelled"),
        ],
        default="scheduled",
        required=True,
        tracking=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            placement = self.env["internship.placement"].browse(vals.get("placement_id"))
            if placement:
                vals.setdefault("student_id", placement.student_id.id)
                vals.setdefault("opportunity_id", placement.opportunity_id.id)
            if vals.get("name", "New") == "New":
                vals["name"] = vals.get("title") or self.env["ir.sequence"].next_by_code("internship.meeting") or "New"
        return super().create(vals_list)

    def _add_default_attendees(self):
        """University coordinator/tutor, student and line manager, as relevant for the meeting type."""
        for meeting in self:
            placement = meeting.placement_id
            candidates = [
                ("university", (placement.tutor_id or placement.user_id).partner_id),
                ("student", placement.student_id.partner_id),
            ]
            if meeting.meeting_type != "exit" or placement.termination_initiated_by != "student":
                candidates.append(
                    ("company", placement.line_manager_id.partner_id or placement.internship_company_id.partner_id)
                )
            if meeting.meeting_type == "university_company":
                candidates = [c for c in candidates if c[0] != "student"]
            existing = meeting.attendee_ids.partner_id
            meeting.write(
                {
                    "attendee_ids": [
                        (0, 0, {"partner_id": partner.id, "role": role})
                        for role, partner in candidates
                        if partner and partner not in existing
                    ]
                }
            )
        return True

    def action_sync_calendar(self):
        """Create or update the calendar event (with a Discuss video link when none is set)."""
        Event = self.env["calendar.event"].sudo()
        for meeting in self:
            start = meeting.meeting_date or fields.Datetime.now()
            values = {
                "name": meeting.title or meeting.name,
                "start": start,
                "stop": start + relativedelta(minutes=meeting.duration_minutes or 60),
                "partner_ids": [(6, 0, meeting.attendee_ids.partner_id.ids)],
                "description": meeting.trigger_reason or "",
                "res_model_id": self.env["ir.model"]._get_id(meeting._name),
                "res_id": meeting.id,
            }
            if meeting.video_url:
                values["videocall_location"] = meeting.video_url
            if meeting.calendar_event_id:
                meeting.calendar_event_id.sudo().write(values)
                event = meeting.calendar_event_id.sudo()
            else:
                event = Event.create(values)
                meeting.calendar_event_id = event
            if not event.videocall_location:
                event._set_discuss_videocall_location()
            if not meeting.video_url:
                meeting.video_url = event.videocall_location
        return True

    def action_complete(self):
        for meeting in self:
            if meeting.state not in ("scheduled", "rescheduled"):
                raise UserError(self.env._("Only scheduled meetings can be completed."))
        self.write({"state": "completed"})
        action = True
        for meeting in self:
            placement = meeting.placement_id
            if meeting.meeting_type == "university_company" and placement.stage_code == "meeting":
                if meeting.additional_docs_needed:
                    action = placement.action_meeting_more_docs()
                else:
                    placement.action_meeting_no_more_docs()
            elif meeting.additional_docs_needed and placement:
                action = placement.action_request_documents()
        self.placement_id._recompute_risk()
        return action

    def action_reschedule(self):
        return self.write({"state": "rescheduled"})

    def action_cancel(self):
        return self.write({"state": "cancelled"})
