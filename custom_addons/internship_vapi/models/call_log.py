import logging
from datetime import datetime

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.phone import to_e164
from ..services.vapi_client import VapiClient, VapiError

_logger = logging.getLogger(__name__)

PURPOSES = [
    ("lead_generation", "Lead generation"),
    ("document_chase", "Document chase"),
    ("attendance_reminder", "Attendance reminder"),
    ("interview_booking", "Interview booking"),
    ("feedback_request", "Feedback request"),
    ("inbound_enquiry", "Inbound enquiry"),
]
# Purposes handled by the "Workflow Chaser" assistant; the rest use the default (lead generation) one.
CHASER_PURPOSES = ("document_chase", "attendance_reminder", "feedback_request", "interview_booking")


class InternshipCallLog(models.Model):
    _name = "internship.call.log"
    _description = "Internship Call Log"
    _order = "call_datetime desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Call Reference", required=True, default="New")
    external_call_id = fields.Char(string="External Call ID", index=True, copy=False, readonly=True)
    student_id = fields.Many2one(
        "internship.student",
        string="Student",
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
    call_datetime = fields.Datetime(string="Call Date and Time", default=fields.Datetime.now)
    call_type = fields.Selection(
        [
            ("inbound", "Inbound"),
            ("outbound", "Outbound"),
            ("follow_up", "Follow-up"),
            ("screening", "Screening"),
        ],
        string="Call Type",
        default="outbound",
        tracking=True,
    )
    # v1 keys unchanged; v2 keys appended.
    status = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("connected", "Connected"),
            ("missed", "Missed"),
            ("completed", "Completed"),
            ("queued", "Queued"),
            ("ringing", "Ringing"),
            ("no_answer", "No answer"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="scheduled",
        tracking=True,
        index=True,
    )
    duration_seconds = fields.Integer(string="Duration (seconds)", default=0)
    summary = fields.Text(string="Summary")
    recording_url = fields.Char(string="Recording URL")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True, tracking=True)

    # v2
    lead_id = fields.Many2one("crm.lead", index=True, ondelete="set null", tracking=True)
    placement_id = fields.Many2one("internship.placement", index=True, ondelete="set null")
    line_manager_id = fields.Many2one("internship.line.manager", index=True, ondelete="set null")
    purpose = fields.Selection(PURPOSES, index=True, tracking=True)
    direction = fields.Selection([("inbound", "Inbound"), ("outbound", "Outbound")], default="outbound", index=True)
    assistant_id = fields.Char()
    phone_number_id = fields.Char()
    customer_number = fields.Char(string="Customer Number (E.164)")
    ended_reason = fields.Char()
    transcript = fields.Text()
    structured_data = fields.Json()
    cost = fields.Float(digits=(10, 4))
    scheduled_at = fields.Datetime(help="Do not dial before this time.")
    attempt_count = fields.Integer(copy=False)
    error_message = fields.Text(copy=False)
    target_model = fields.Char(help="Record the call is about (e.g. an overdue document request).")
    target_id = fields.Integer()

    _external_call_id_unique = models.Constraint(
        "unique(external_call_id)",
        "Each external call can only be imported once.",
    )

    # ------------------------------------------------------------------
    # v1 buttons
    # ------------------------------------------------------------------
    def action_connect(self):
        return self.write({"status": "connected"})

    def action_miss(self):
        return self.write({"status": "missed"})

    def action_complete(self):
        return self.write({"status": "completed"})

    def action_cancel(self):
        return self.filtered(lambda c: c.status == "queued").write({"status": "cancelled"})

    # ------------------------------------------------------------------
    # Queueing
    # ------------------------------------------------------------------
    @api.model
    def _target_values(self, target):
        """Who to call and what to link, for the supported target models."""
        values = {"target_model": target._name, "target_id": target.id}
        if target._name == "crm.lead":
            values.update(
                lead_id=target.id,
                student_id=target.student_id.id,
                number=target.phone or getattr(target, "mobile", False),
            )
        elif target._name == "internship.student":
            values.update(student_id=target.id, number=target.phone or target.partner_id.phone)
        elif target._name == "internship.line.manager":
            values.update(line_manager_id=target.id, number=target.phone)
        elif target._name == "internship.placement":
            company_number = target.line_manager_id.phone or target.internship_company_id.phone
            number = company_number if target.stage_code == "form_requested" else target.student_id.phone
            values.update(placement_id=target.id, student_id=target.student_id.id, number=number)
        elif "placement_id" in target._fields:
            placement = target.placement_id
            number = placement.student_id.phone
            if getattr(target, "requested_from", None) == "company":
                number = placement.line_manager_id.phone or placement.internship_company_id.phone
            values.update(placement_id=placement.id, student_id=placement.student_id.id, number=number)
        else:
            raise UserError(self.env._("Calls cannot be placed for %(model)s records.", model=target._description))
        return values

    @api.model
    def action_queue_call(self, purpose, target, scheduled_at=None):
        """Create a queued call for `target`; the queue cron dials it when allowed."""
        logs = self.browse()
        for record in target:
            values = self._target_values(record)
            number = to_e164(values.pop("number", None))
            if not number:
                raise UserError(self.env._("%(name)s has no valid phone number.", name=record.display_name))
            logs |= self.create(
                {
                    **values,
                    "name": self.env._(
                        "%(purpose)s: %(name)s", purpose=dict(PURPOSES)[purpose], name=record.display_name
                    ),
                    "purpose": purpose,
                    "direction": "outbound",
                    "call_type": "outbound",
                    "status": "queued",
                    "customer_number": number,
                    "scheduled_at": scheduled_at,
                    "call_datetime": scheduled_at or fields.Datetime.now(),
                }
            )
        return logs

    # ------------------------------------------------------------------
    # Rules for dialling
    # ------------------------------------------------------------------
    @api.model
    def _settings(self):
        get = self.env["ir.config_parameter"].sudo().get_param
        return {
            "enabled": get("internship_vapi.enabled") in ("True", "true", "1"),
            "window_start": float(get("internship_vapi.window_start", "9.0") or 9.0),
            "window_end": float(get("internship_vapi.window_end", "20.0") or 20.0),
            "window_days": get("internship_vapi.window_days", "0,1,2,3,4"),
            "timezone": get("internship_vapi.timezone", "Europe/London") or "Europe/London",
            "max_attempts": int(get("internship_vapi.max_attempts", "3") or 3),
            "default_assistant_id": get("internship_vapi.default_assistant_id"),
            "chaser_assistant_id": get("internship_vapi.chaser_assistant_id"),
            "phone_number_id": get("internship_vapi.phone_number_id"),
        }

    @api.model
    def _in_calling_window(self, settings, now=None):
        """Mon-Fri 09:00-20:00 Europe/London by default."""
        now = now or datetime.utcnow()
        local = pytz.utc.localize(now).astimezone(pytz.timezone(settings["timezone"]))
        days = {int(d) for d in str(settings["window_days"]).split(",") if d.strip().isdigit()}
        hour = local.hour + local.minute / 60.0
        return local.weekday() in days and settings["window_start"] <= hour < settings["window_end"]

    def _blocked_reason(self, settings):
        """Why this call must not be dialled now (None when it may be)."""
        self.ensure_one()
        if not settings["enabled"]:
            return self.env._("Voice AI calling is switched off.")
        if self.attempt_count >= settings["max_attempts"]:
            return self.env._("Maximum attempts reached.")
        if self.lead_id.do_not_call:
            return self.env._("The contact is marked Do Not Call.")
        if (
            self.purpose == "lead_generation"
            and self.lead_id.lead_category == "company"
            and not self.lead_id.tps_checked
        ):
            return self.env._("Marketing calls to companies need a TPS/CTPS check first.")
        return None

    def _assistant_for(self, settings):
        if self.purpose in CHASER_PURPOSES and settings["chaser_assistant_id"]:
            return settings["chaser_assistant_id"]
        return settings["default_assistant_id"]

    def _variable_values(self):
        self.ensure_one()
        placement = self.placement_id
        values = {
            "student_name": self.student_id.name or self.lead_id.contact_name or "",
            "company_name": placement.internship_company_id.name or self.lead_id.partner_name or "",
            "university_name": placement.university_id.name or self.student_id.university_id.name or "",
            "placement_ref": placement.name or "",
            "purpose": self.purpose or "",
        }
        if self.target_model and self.target_id and self.target_model in self.env:
            target = self.env[self.target_model].browse(self.target_id).exists()
            due = target and "due_date" in target._fields and target.due_date
            if due:
                values["due_date"] = due.strftime("%d %B %Y")
        return values

    def _metadata(self):
        self.ensure_one()
        return {
            "odoo_db": self.env.cr.dbname,
            "call_log_id": self.id,
            "lead_id": self.lead_id.id or None,
            "student_id": self.student_id.id or None,
            "placement_id": self.placement_id.id or None,
            "purpose": self.purpose,
        }

    def _dial(self, settings=None, client=None):
        settings = settings or self._settings()
        dialled = self.browse()
        for log in self:
            reason = log._blocked_reason(settings)
            if reason:
                if log.attempt_count >= settings["max_attempts"] or log.lead_id.do_not_call:
                    log.write({"status": "cancelled", "error_message": reason})
                else:
                    log.error_message = reason
                continue
            log.attempt_count += 1
            try:
                client = client or VapiClient(self.env)
                response = client.create_call(
                    log.customer_number,
                    log._assistant_for(settings),
                    metadata=log._metadata(),
                    variable_values=log._variable_values(),
                    phone_number_id=settings["phone_number_id"],
                )
            except VapiError as error:
                log.write(
                    {
                        "error_message": str(error),
                        "status": "failed" if log.attempt_count >= settings["max_attempts"] else "queued",
                    }
                )
                continue
            log.write(
                {
                    "external_call_id": response.get("id"),
                    "status": {"ringing": "ringing", "in-progress": "connected"}.get(
                        response.get("status"), "scheduled"
                    ),
                    "call_datetime": fields.Datetime.now(),
                    "assistant_id": log._assistant_for(settings),
                    "phone_number_id": settings["phone_number_id"],
                    "error_message": False,
                }
            )
            dialled |= log
        return dialled

    def action_dial_now(self):
        settings = self._settings()
        if not self._in_calling_window(settings):
            raise UserError(self.env._("Outside the calling window. The call stays queued."))
        return self._dial(settings)

    @api.model
    def _cron_dial_queue(self, limit=20):
        settings = self._settings()
        if not settings["enabled"] or not self._in_calling_window(settings):
            return self.browse()
        now = fields.Datetime.now()
        queued = self.search(
            [("status", "=", "queued"), "|", ("scheduled_at", "=", False), ("scheduled_at", "<=", now)],
            order="scheduled_at, id",
            limit=limit,
        )
        return queued._dial(settings)
