"""Functions the voice assistant can call during a call (POST /internship/vapi/tool).

Every handler validates its arguments and returns a short, friendly string. Never a stack
trace, and never personal data beyond what the caller has proven they are entitled to.
"""

import logging

from odoo import fields

from odoo.addons.internship_base.services.activity import default_coordinator, schedule_activity_once

from .lead_sync import _parse_callback, upsert_lead

_logger = logging.getLogger(__name__)

NEXT_ACTION = {
    "form_requested": "Your host company needs to complete the internship form.",
    "under_review": "The university is reviewing your internship documents.",
    "more_docs": "Some more documents are needed. Please check your e-mail.",
    "meeting": "A meeting between the university and your host company is being arranged.",
    "agreement": "The placement agreement is out for signature.",
    "approved": "Your internship is approved and will start on the agreed date.",
    "active": "Please keep your monthly attendance records up to date.",
    "on_hold": "Your placement is on hold. Your coordinator will be in touch.",
    "completion": "Please submit your final report by the deadline.",
    "completed": "Your internship is complete. Congratulations!",
}


class ToolError(ValueError):
    """A friendly message for the caller."""


def create_or_update_lead(env, args, call_log=None):
    if not (args.get("phone") or args.get("email") or (call_log and call_log.customer_number)):
        raise ToolError("I need a phone number or an e-mail address to save your details.")
    lead = upsert_lead(env, args, "vapi_inbound", call_log=call_log)
    return f"Thanks, your details are saved (reference {lead.id})."


def book_callback(env, args, call_log=None):
    lead_ref = str(args.get("lead_ref") or "").strip()
    when = _parse_callback(args.get("datetime_iso"))
    if not lead_ref.isdigit() or not when:
        raise ToolError("I could not book that time. Could you give me the date and time again?")
    if when < fields.Datetime.now():
        raise ToolError("That time has already passed. Could you choose a later time?")
    lead = env["crm.lead"].sudo().browse(int(lead_ref)).exists()
    if not lead:
        raise ToolError("I could not find your enquiry. A colleague will call you back.")
    lead.write({"callback_datetime": when})
    schedule_activity_once(
        lead,
        lead.user_id or default_coordinator(env),
        env._("Call back %(name)s", name=lead.contact_name or lead.name),
        deadline=when.date(),
        act_type_xmlid="mail.mail_activity_data_call",
    )
    return f"Your callback is booked for {when.strftime('%d %B at %H:%M')} (UK time)."


def _student_by_identity(env, student_id, date_of_birth):
    student_ref = str(student_id or "").strip()
    dob = fields.Date.to_date(str(date_of_birth).strip()[:10]) if date_of_birth else None
    if not student_ref or not dob:
        raise ToolError("Please give me your student ID and your date of birth.")
    student = env["internship.student"].sudo().search([("student_id", "=", student_ref)], limit=2)
    # Both must match; the same answer is given whichever is wrong, so nothing leaks.
    if len(student) != 1 or student.date_of_birth != dob:
        raise ToolError("Sorry, I could not verify those details. Please contact your placement office.")
    return student


def get_placement_status(env, args, call_log=None):
    try:
        student = _student_by_identity(env, args.get("student_id"), args.get("date_of_birth"))
    except ToolError:
        raise
    except ValueError as error:
        raise ToolError("Please say your date of birth as day, month and year.") from error
    placement = student.placement_ids.filtered("active").sorted("id", reverse=True)[:1]
    if not placement:
        return "I cannot see an internship placement for you yet."
    next_action = NEXT_ACTION.get(placement.stage_code, "Your placement coordinator will contact you.")
    return f"Your placement is at the stage: {placement.stage_id.name}. {next_action}"


def confirm_monthly_submission(env, args, call_log=None):
    placement_ref = str(args.get("placement_ref") or "").strip()
    student_ref = str(args.get("student_id") or "").strip()
    if not placement_ref or not student_ref:
        raise ToolError("Please give me your placement reference and student ID.")
    placement = (
        env["internship.placement"]
        .sudo()
        .search([("name", "=", placement_ref), ("student_id.student_id", "=", student_ref)], limit=1)
    )
    if not placement:
        raise ToolError("Sorry, I could not find that placement.")
    today = fields.Date.context_today(placement)
    record = placement.monthly_ids.filtered(lambda m: m.year == today.year and m.month == str(today.month))
    if not record:
        return "There is no monthly record due for this month yet."
    if record.state in ("pending", "late"):
        return f"This month's record is not submitted yet. It is due on {record.due_date.strftime('%d %B')}."
    return "Yes, this month's record has been submitted. Thank you."


HANDLERS = {
    "create_or_update_lead": create_or_update_lead,
    "book_callback": book_callback,
    "get_placement_status": get_placement_status,
    "confirm_monthly_submission": confirm_monthly_submission,
}


def dispatch(env, tool_call, call_log=None):
    handler = HANDLERS.get(tool_call.name)
    if not handler:
        return "Sorry, I cannot do that. A colleague will follow up."
    try:
        return handler(env, tool_call.arguments, call_log=call_log)
    except ToolError as error:
        return str(error)
    except Exception:  # noqa: BLE001 - the caller must never hear a stack trace
        _logger.exception("Vapi tool %s failed", tool_call.name)
        return "Sorry, something went wrong on our side. A colleague will follow up."
