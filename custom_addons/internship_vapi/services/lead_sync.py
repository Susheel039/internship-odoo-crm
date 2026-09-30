"""Create or update crm.lead records from what the voice assistant learned."""

from odoo import fields

from odoo.addons.internship_base.services.activity import default_coordinator, schedule_activity_once

from .phone import to_e164

CATEGORIES = {"student", "company", "university", "other"}
INTEREST = {"cold", "warm", "hot"}


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def _parse_callback(value):
    if not value:
        return False
    try:
        return fields.Datetime.to_datetime(str(value).replace("T", " ").replace("Z", "")[:19])
    except ValueError:
        return False


def find_lead(env, phone=None, email=None):
    """Dedupe: E.164 phone first, then e-mail."""
    Lead = env["crm.lead"].sudo().with_context(active_test=False)
    number = to_e164(phone)
    if number:
        lead = Lead.search([("phone_sanitized", "=", number)], limit=1) or Lead.search(
            [("phone", "=", number)], limit=1
        )
        if lead:
            return lead
    if email:
        return Lead.search([("email_from", "=ilike", email.strip())], limit=1)
    return Lead.browse()


def upsert_lead(env, data, source_channel, summary=None, call_log=None):
    """`data` uses the keys of the assistant's structured-data schema (docs/vapi/ASSISTANT_SETUP.md)."""
    data = data or {}
    phone = data.get("phone") or (call_log.customer_number if call_log else None)
    email = (data.get("email") or "").strip() or False
    lead = find_lead(env, phone, email)
    values = {"source_channel": source_channel}
    name = data.get("name") or data.get("contact_name")
    if data.get("lead_category") in CATEGORIES:
        values["lead_category"] = data["lead_category"]
    if data.get("interest_level") in INTEREST:
        values["interest_level"] = data["interest_level"]
    if name:
        values["contact_name"] = name
    if data.get("organisation"):
        values["partner_name"] = data["organisation"]
    if data.get("role"):
        values["function"] = data["role"]
    if email:
        values["email_from"] = email
    if to_e164(phone):
        values["phone"] = to_e164(phone)
    if "consent_to_contact" in data:
        values["consent_to_contact"] = _as_bool(data["consent_to_contact"])
        if values["consent_to_contact"]:
            values["consent_date"] = fields.Datetime.now()
    if "recording_consent" in data:
        values["recording_consent"] = _as_bool(data["recording_consent"])
    callback = _parse_callback(data.get("callback_datetime"))
    if callback:
        values["callback_datetime"] = callback
    if lead:
        lead.write(values)
    else:
        values.setdefault("lead_category", "other")
        values["name"] = data.get("organisation") or name or env._("Voice AI enquiry")
        values["type"] = "lead"
        lead = env["crm.lead"].sudo().create(values)
    notes = data.get("notes")
    body = "<br/>".join(p for p in (summary, notes) if p)
    if body:
        lead.message_post(body=body)
    if callback:
        schedule_activity_once(
            lead,
            lead.user_id or default_coordinator(env),
            env._("Call back %(name)s", name=lead.contact_name or lead.name),
            deadline=callback.date(),
            act_type_xmlid="mail.mail_activity_data_call",
        )
    if call_log:
        call_log.sudo().lead_id = lead
    return lead
