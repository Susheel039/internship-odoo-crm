"""Legacy internship.crm.lead -> crm.lead (v2 migration step 4). Shared by migrations and tests."""

import logging

_logger = logging.getLogger(__name__)

STAGE_MAP = {
    "new": "new",
    "contacted": "contacted",
    "qualified": "qualified",
    "proposal": "qualified",
    "interview": "interview",
    "accepted": "won",
    "closed": "lost",
}
SOURCE_MAP = {
    "referral": "referral",
    "university": "university",
    "company": "other",
    "portal": "portal",
    "campus": "campus_event",
    "other": "other",
}


def migrate_legacy_leads(env):
    """Copy every legacy lead into crm.lead once (idempotent through legacy_internship_lead_id)."""
    Lead = env["crm.lead"].with_context(tracking_disable=True, mail_create_nolog=True, active_test=False)
    Legacy = env["internship.crm.lead"].with_context(active_test=False)
    done = set(Lead.search([("legacy_internship_lead_id", "!=", False)]).legacy_internship_lead_id.ids)
    lost_reason = env.ref("internship_crm.lost_reason_legacy_closed", raise_if_not_found=False)
    created = updated = 0
    for legacy in Legacy.search([("id", "not in", list(done))]):
        student = legacy.student_id
        values = {
            "name": legacy.name,
            "type": "opportunity",
            "lead_category": "student" if student else "company",
            "student_id": student.id,
            "opportunity_id": legacy.opportunity_id.id,
            "internship_company_id": legacy.company_id.id,
            "university_id": legacy.university_id.id,
            "source_channel": SOURCE_MAP.get(legacy.lead_source, "other"),
            "priority": legacy.priority or "0",
            "date_deadline": legacy.expected_start_date,
            "description": legacy.notes,
            "legacy_internship_lead_id": legacy.id,
        }
        if student:
            values.update(partner_id=student.partner_id.id, email_from=student.email, phone=student.phone)
        values["stage_id"] = Lead._internship_stage(STAGE_MAP.get(legacy.stage, "new")).id
        if legacy.crm_id:
            # The legacy lead already had a native twin: enrich it instead of duplicating.
            lead = legacy.crm_id.with_context(tracking_disable=True)
            lead.write({k: v for k, v in values.items() if k not in ("name", "type") and v})
            updated += 1
        else:
            lead = Lead.create(values)
            created += 1
        if legacy.stage == "closed":
            lead.lost_reason_id = lost_reason
        if not legacy.active:
            lead.action_archive()
        lead.message_post(body=env._("Migrated from legacy internship lead %(name)s.", name=legacy.name))
    _logger.info("internship_crm 19.0.2.0.0: legacy leads -> crm.lead: %s created, %s merged", created, updated)
    return created + updated
