"""Demo data that walks through the whole Internship CRM v2 workflow.

Run on a DEMO database only (never on real data):

    make demo-data DB=internship_v2_demo

Creates fictional UK universities, companies, line managers, students, CRM leads at every
stage (with notes explaining each step), AI call logs over the last 8 weeks, applications at
every status, and placements in every stage with monthly attendance history, an escalation,
document requests, leave, meetings, report marking, evaluations, certificates and feedback.
Idempotent: does nothing if the demo marker company already exists.
"""

import base64
import logging
import random
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

_logger = logging.getLogger("seed_workflow_demo")
random.seed(42)

env = env  # noqa: F821 - provided by `odoo shell`
env = env(context=dict(env.context, tracking_disable=True, mail_notrack=True, mail_create_nolog=True))
TODAY = date.today()
NOW = datetime.now()
MARKER = "Harbour Health NHS Trust"

if env["internship.company"].search_count([("name", "=", MARKER)]):
    print("SEED: demo data already present, nothing to do")
    raise SystemExit(0)

Partner = env["res.partner"]
uk = env.ref("base.uk")
admin = env.ref("base.user_admin")
PDF = env["ir.attachment"].create(
    {"name": "demo-document.pdf", "datas": base64.b64encode(b"%PDF-1.4 demo document"), "mimetype": "application/pdf"}
)
phone_counter = iter(range(310, 999))


def phone():
    return f"+44 7700 900{next(phone_counter):03d}"


def partner(name, email, company=False):
    return Partner.create({"name": name, "email": email, "phone": phone(), "is_company": company, "country_id": uk.id})


def set_create_date(record, when):
    env.cr.execute(f"UPDATE {record._table} SET create_date = %s WHERE id = %s", (when, record.id))  # noqa: S608


# ----------------------------------------------------------------------
# Master data
# ----------------------------------------------------------------------
year = env["internship.academic.year"]._get_for_date(TODAY) or env.ref("internship_base.academic_year_2026_27")
universities = {}
for name, code, ukprn in (
    ("Northbridge University", "NBU", "10099901"),
    ("Southmere University", "SMU", "10099902"),
    ("Kingsgate College London", "KCL", "10099903"),
):
    uni = env["internship.university"].search([("name", "=", name)], limit=1) or env["internship.university"].create(
        {"name": name, "code": code, "partner_id": partner(name, f"placements@{code.lower()}.example", True).id}
    )
    uni.write({"ukprn": uni.ukprn or ukprn, "user_ids": [(4, admin.id)]})
    universities[code] = uni

programs = {}
for code, uni in universities.items():
    programs[code] = env["internship.program"].create(
        {
            "name": f"{code} Placement Year {year.name}",
            "university_id": uni.id,
            "academic_year_id": year.id,
            "department": "School of Computing and Business",
            "start_date": TODAY - relativedelta(months=8),
            "end_date": TODAY + relativedelta(months=6),
            "min_duration_weeks": 8,
            "max_duration_weeks": 52,
            "required_hours_per_week": 30,
            "state": "open",
        }
    )

companies = {}
for name, sector, size, vetting in (
    (MARKER, "healthcare", "500_plus", "approved"),
    ("Riverside Analytics Ltd", "technology", "51_200", "approved"),
    ("Brightwater Engineering plc", "engineering", "201_500", "approved"),
    ("Oakline Retail Group", "retail", "500_plus", "approved"),
    ("Meridian Finance LLP", "finance", "11_50", "approved"),
    ("Northern Lights Studio", "creative", "1_10", "pending"),
):
    slug = name.split()[0].lower()
    company = env["internship.company"].create(
        {
            "name": name,
            "partner_id": partner(name, f"careers@{slug}.example", True).id,
            "company_registration_number": f"0{random.randint(1000000, 9999999)}",
            "company_size": size,
            "contact_person": "Early Careers Team",
            "contact_email": f"careers@{slug}.example",
            "phone": phone(),
            "insurance_policy_no": f"EL-{random.randint(100000, 999999)}",
            "insurance_expiry": TODAY + relativedelta(months=14 if vetting == "approved" else 1),
            "risk_assessment_date": TODAY - relativedelta(months=2),
            "sector_ids": [(4, env.ref(f"internship_base.sector_{sector}").id)],
            "user_ids": [(4, admin.id)],
            "site_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Head office",
                        "city": random.choice(["Leeds", "Manchester", "London", "Bristol"]),
                        "work_mode": "hybrid",
                    },
                )
            ],
        }
    )
    if vetting == "approved":
        company.action_vetting_approve()
    companies[name] = company

managers = {}
for company in companies.values():
    first = random.choice(["Olivia", "Amir", "Grace", "Tom", "Priya", "Daniel"])
    managers[company.id] = env["internship.line.manager"].create(
        {
            "partner_id": partner(
                f"{first} {company.name.split()[0]}", f"{first.lower()}@{company.name.split()[0].lower()}.example"
            ).id,
            "company_id": company.id,
            "job_title": random.choice(["Engineering Manager", "Team Lead", "Head of Data", "Operations Manager"]),
            "can_approve_attendance": True,
            "can_sign_agreement": True,
            "can_issue_certificate": True,
        }
    )

opportunities = []
roles = [
    "Software Engineering Intern",
    "Data Analyst Placement",
    "Clinical Informatics Intern",
    "Mechanical Design Placement",
    "Retail Operations Intern",
    "Finance Graduate Intern",
    "UX Research Intern",
    "Cloud Support Placement",
]
company_list = [c for c in companies.values() if c.vetting_state == "approved"]
for index, role in enumerate(roles):
    company = company_list[index % len(company_list)]
    code = list(programs)[index % 3]
    opportunities.append(
        env["internship.opportunity"].create(
            {
                "name": role,
                "job_title": role,
                "company_id": company.id,
                "program_id": programs[code].id,
                "location": company.site_ids[:1].city,
                "work_mode": random.choice(["on_site", "hybrid", "remote"]),
                "hours_per_week": 37.5,
                "is_paid": True,
                "salary_amount": random.choice([21000, 23500, 25000, 27000]),
                "salary_note": "per annum, pro rata",
                "application_deadline": TODAY - relativedelta(months=7),
                "start_date": TODAY - relativedelta(months=6),
                "end_date": TODAY + relativedelta(months=6),
                "number_of_positions": random.choice([2, 3, 4]),
                "skill_ids": [
                    (4, env.ref("internship_base.skill_python").id),
                    (4, env.ref("internship_base.skill_communication").id),
                ],
                "state": "open",
            }
        )
    )

# ----------------------------------------------------------------------
# CRM: leads at every stage, explaining the funnel
# ----------------------------------------------------------------------
Lead = env["crm.lead"]
stage = Lead._internship_stage
STORY = {
    "new": "NEW: captured but not yet contacted. Next: call or e-mail within 2 working days (Call with AI).",
    "contacted": "CONTACTED: first conversation done. Next: qualify (roles, sites, dates, eligibility).",
    "qualified": "QUALIFIED: real need confirmed. Next: book an interview / site visit with the coordinator.",
    "interview": "INTERVIEW: meeting booked or held. Next: agree to host (company) or apply (student).",
    "won": "WON: converted. Companies become internship.company records and get an invitation; "
    "students become internship.student records and can apply.",
    "lost": "LOST: not going ahead this year. Reason recorded; eligible for next year's campaign.",
}
lead_specs = [
    # (name, category, stage, channel, interest, contact, organisation)
    ("Harbour Health: clinical informatics interns", "company", "won", "referral", "hot", "Dr Nia Rees", MARKER),
    (
        "Riverside Analytics: data placements",
        "company",
        "won",
        "vapi_outbound",
        "hot",
        "Sam Patel",
        "Riverside Analytics Ltd",
    ),
    (
        "Brightwater: summer engineering scheme",
        "company",
        "interview",
        "campus_event",
        "hot",
        "Kate Owens",
        "Brightwater Engineering plc",
    ),
    (
        "Oakline Retail: store operations interns",
        "company",
        "qualified",
        "vapi_outbound",
        "warm",
        "Liam Carter",
        "Oakline Retail Group",
    ),
    (
        "Meridian Finance: audit intern",
        "company",
        "qualified",
        "referral",
        "warm",
        "Hannah Webb",
        "Meridian Finance LLP",
    ),
    (
        "Northern Lights Studio: UX intern",
        "company",
        "contacted",
        "vapi_inbound",
        "warm",
        "Eve Marsh",
        "Northern Lights Studio",
    ),
    ("Castleford Logistics", "company", "contacted", "vapi_outbound", "cold", "Rob Hale", "Castleford Logistics"),
    ("Greenway Energy", "company", "new", "campus_event", "warm", "Zara Khan", "Greenway Energy"),
    ("Pinewood Care Homes", "company", "new", "vapi_outbound", "cold", "Mark Doyle", "Pinewood Care Homes"),
    ("Atlas Legal Services", "company", "lost", "referral", "cold", "Jo Briggs", "Atlas Legal Services"),
    ("Enquiry: Chloe Evans (Computing)", "student", "won", "vapi_inbound", "hot", "Chloe Evans", False),
    ("Enquiry: Ravi Shah (Business)", "student", "won", "portal", "warm", "Ravi Shah", False),
    ("Enquiry: Ella Price (Design)", "student", "interview", "vapi_inbound", "warm", "Ella Price", False),
    ("Enquiry: Noah Clarke (Engineering)", "student", "qualified", "campus_event", "warm", "Noah Clarke", False),
    ("Enquiry: Mia Hughes (Finance)", "student", "contacted", "vapi_inbound", "cold", "Mia Hughes", False),
    ("Enquiry: Leo Ahmed (Computing)", "student", "new", "vapi_inbound", "warm", "Leo Ahmed", False),
    ("Enquiry: Ruby Scott (Marketing)", "student", "new", "portal", "cold", "Ruby Scott", False),
    ("Enquiry: Finn Walsh (Data)", "student", "lost", "vapi_inbound", "cold", "Finn Walsh", False),
    (
        "Westfield University partnership",
        "university",
        "qualified",
        "university",
        "warm",
        "Prof. Anne Moss",
        "Westfield University",
    ),
    (
        "Do-not-call example: Blue Harbour Cafe",
        "company",
        "contacted",
        "vapi_outbound",
        "cold",
        "Owner",
        "Blue Harbour Cafe",
    ),
]
leads = Lead
for index, (name, category, stage_code, channel, interest, contact, organisation) in enumerate(lead_specs):
    lead = Lead.create(
        {
            "name": name,
            "type": "opportunity",
            "lead_category": category,
            "stage_id": stage(stage_code).id,
            "source_channel": channel,
            "interest_level": interest,
            "contact_name": contact,
            "partner_name": organisation or False,
            "email_from": f"{contact.split()[-1].lower()}@{(organisation or 'students').split()[0].lower()}.example",
            "phone": phone(),
            "consent_to_contact": stage_code not in ("new", "lost"),
            "consent_date": NOW - timedelta(days=10) if stage_code not in ("new", "lost") else False,
            "recording_consent": channel.startswith("vapi"),
            "tps_checked": category == "company",
            "tps_checked_date": TODAY - relativedelta(days=20) if category == "company" else False,
            "do_not_call": name.startswith("Do-not-call"),
            "university_id": universities["NBU"].id if category == "student" else False,
            "description": STORY[stage_code],
            "priority": {"hot": "3", "warm": "2", "cold": "1"}[interest],
            "expected_revenue": 0,
        }
    )
    if stage_code == "lost":
        lead.lost_reason_id = env.ref("internship_crm.lost_reason_legacy_closed", raise_if_not_found=False)
    if interest == "hot" and stage_code in ("interview", "qualified"):
        lead.callback_datetime = NOW + timedelta(days=random.randint(1, 6), hours=random.randint(1, 5))
    set_create_date(lead, NOW - timedelta(days=60 - index * 3))
    lead.message_post(body=STORY[stage_code])
    leads |= lead

# won leads -> real records (the conversion step of the funnel)
for lead in leads.filtered(lambda lead: lead.stage_id == stage("won")):
    if lead.lead_category == "company":
        company = env["internship.company"].search([("name", "=", lead.partner_name)], limit=1)
        lead.write({"internship_company_id": company.id})
        lead.message_post(body=f"Converted: company record {company.name} (vetted and hosting placements).")
    else:
        lead.action_convert_to_student()

# ----------------------------------------------------------------------
# Voice AI call log over the last 8 weeks
# ----------------------------------------------------------------------
CallLog = env["internship.call.log"]
outcomes = ["completed"] * 6 + ["no_answer"] * 2 + ["failed"]
for index in range(46):
    lead = leads[index % len(leads)]
    when = NOW - timedelta(days=random.randint(0, 55), hours=random.randint(0, 8))
    status = random.choice(outcomes)
    CallLog.create(
        {
            "name": f"Call {index + 1:03d}: {lead.contact_name}",
            "lead_id": lead.id,
            "purpose": "inbound_enquiry" if lead.source_channel == "vapi_inbound" else "lead_generation",
            "direction": "inbound" if lead.source_channel == "vapi_inbound" else "outbound",
            "call_type": "inbound" if lead.source_channel == "vapi_inbound" else "outbound",
            "status": status,
            "call_datetime": when,
            "duration_seconds": random.randint(60, 420) if status == "completed" else 0,
            "customer_number": lead.phone,
            "cost": round(random.uniform(0.04, 0.35), 2) if status == "completed" else 0.0,
            "ended_reason": {
                "completed": "customer-ended-call",
                "no_answer": "customer-did-not-answer",
                "failed": "pipeline-error",
            }[status],
            "summary": "Discussed internship hosting and next steps." if status == "completed" else False,
            "attempt_count": 1,
        }
    )
for lead in leads.filtered(lambda lead: lead.stage_id == stage("new") and not lead.do_not_call)[:2]:
    CallLog.action_queue_call("lead_generation", lead, scheduled_at=NOW + timedelta(hours=2))

# ----------------------------------------------------------------------
# Students, applications and placements in every stage
# ----------------------------------------------------------------------
first_names = [
    "Amelia",
    "Oliver",
    "Isla",
    "George",
    "Ava",
    "Arthur",
    "Freya",
    "Harry",
    "Lily",
    "Jack",
    "Sophie",
    "Charlie",
    "Evie",
    "Alfie",
    "Poppy",
    "Oscar",
    "Grace",
    "Theo",
    "Florence",
    "Henry",
    "Rosie",
    "Archie",
    "Ivy",
    "Leo",
]
last_names = [
    "Clarke",
    "Hughes",
    "Patel",
    "Morgan",
    "Turner",
    "Robinson",
    "Ali",
    "Evans",
    "Walker",
    "Wright",
    "Khan",
    "Green",
]
students = env["internship.student"]
for index, first in enumerate(first_names):
    code = list(universities)[index % 3]
    name = f"{first} {last_names[index % len(last_names)]}"
    student = env["internship.student"].create(
        {
            "name": name,
            "partner_id": partner(
                name, f"{first.lower()}.{last_names[index % len(last_names)].lower()}@students.{code.lower()}.example"
            ).id,
            "student_id": f"{code}-{2400000 + index}",
            "university_id": universities[code].id,
            "program_id": programs[code].id,
            "academic_year_id": year.id,
            "year_of_study": random.choice(["2", "3"]),
            "course": random.choice(
                ["BSc Computer Science", "BA Business Management", "BEng Mechanical Engineering", "BSc Data Science"]
            ),
            "date_of_birth": date(2003 + index % 3, 1 + index % 12, 1 + index % 27),
            "rtw_status": "verified",
            "gdpr_consent": True,
            "gdpr_consent_date": TODAY - relativedelta(months=9),
            "academic_tutor_id": admin.id,
        }
    )
    students |= student


def form(placement):
    placement.write(
        {
            "learning_objectives": "<p>Deliver a real project in an agile team; reflect on professional practice.</p>",
            "hs_confirmed": True,
            "form_attachment_id": PDF.id,
            "line_manager_id": managers[placement.internship_company_id.id].id,
        }
    )
    placement.action_submit_form()


def approve(placement):
    env["internship.university.review"].create({"placement_id": placement.id, "decision": "approve"}).action_decide()
    agreement = placement.agreement_id
    for signer in agreement.signer_ids.sorted("sequence"):
        agreement._sign(
            signer,
            signer.partner_id.name,
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            "203.0.113.10",
            "demo",
        )


def start(placement, months_ago):
    placement.action_start()
    started = TODAY - relativedelta(months=months_ago)
    placement.write({"actual_start": started, "planned_start": started})
    placement.monthly_ids.unlink()
    Monthly = env["internship.attendance.monthly"]
    for back in range(months_ago, -1, -1):
        Monthly._ensure_for(placement, TODAY - relativedelta(months=back))


def fill_months(placement, attendance_profile, rating_profile):
    """Submit and approve past months with the given attendance ratios and ratings."""
    months = placement.monthly_ids.sorted(lambda m: (m.year, int(m.month)))
    for record, ratio, rating in zip(months[:-1], attendance_profile, rating_profile, strict=False):
        record.write(
            {
                "days_attended": round(record.days_expected * ratio),
                "total_hours": round(record.days_expected * ratio * 7.5),
            }
        )
        record.action_student_submit()
        record.write(
            {"rating": str(rating), "working_as_required": rating > 2, "strengths": "Reliable and keen to learn."}
        )
        record.action_company_approve()
        if not record.tripartite_triggered:
            record.action_university_review()


student_iter = iter(students)
opportunity_iter = iter(opportunities * 4)
placements = {}


def accepted(tag):
    student = next(student_iter)
    opportunity = next(opportunity_iter)
    application = env["internship.application"].create(
        {
            "student_id": student.id,
            "opportunity_id": opportunity.id,
            "interviewer_id": managers[opportunity.company_id.id].id,
        }
    )
    application.action_submit()
    application.write({"application_date": TODAY - relativedelta(days=random.randint(120, 200))})
    application.action_shortlist()
    application.write({"interview_date": NOW - timedelta(days=100), "interview_score": random.randint(6, 9)})
    application.action_interview()
    application.action_offer()
    application.action_student_accept()
    placements[tag] = application.placement_id
    return application.placement_id


# Phase 1: admission / approval
accepted("form_requested")
accepted("form_requested_2")
form(accepted("under_review"))
p = accepted("more_docs")
form(p)
env["internship.university.review"].create({"placement_id": p.id, "decision": "more_docs"}).action_decide()
env["internship.document.request.wizard"].create(
    {
        "placement_id": p.id,
        "requested_from": "student",
        "line_ids": [(0, 0, {"document_type_id": env.ref("internship_base.doc_type_dbs").id, "mandatory": True})],
    }
).action_confirm()
p = accepted("meeting")
form(p)
p.action_schedule_meeting()
p = accepted("agreement")
form(p)
env["internship.university.review"].create({"placement_id": p.id, "decision": "approve"}).action_decide()
first_signer = p.agreement_id.signer_ids.sorted("sequence")[:1]
p.agreement_id._sign(
    first_signer,
    first_signer.partner_id.name,
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
    "203.0.113.11",
    "demo",
)
p = accepted("approved")
form(p)
approve(p)
p.planned_start = TODAY + relativedelta(days=14)
p = accepted("rejected")
form(p)
env["internship.university.review"].create(
    {
        "placement_id": p.id,
        "decision": "reject",
        "rejection_reason_id": env.ref("internship_base.reason_uni_rejection_hs").id,
    }
).action_decide()

# Phase 2: monitoring
for tag, months, attendance, ratings in (
    ("active_good", 5, [0.98, 0.95, 1.0, 0.97, 0.96], [4, 5, 4, 5, 4]),
    ("active_ok", 4, [0.92, 0.9, 0.95, 0.9], [3, 4, 3, 4]),
    ("active_risk", 4, [0.95, 0.85, 0.7, 0.62], [4, 3, 3, 2]),
    ("active_late", 3, [0.97, 0.95, 0.9], [4, 4, 4]),
    ("active_new", 1, [], []),
):
    p = accepted(tag)
    form(p)
    approve(p)
    start(p, months)
    fill_months(p, attendance, ratings)
# a late record (not submitted, past due + grace)
late_record = placements["active_late"].monthly_ids.sorted(lambda m: (m.year, int(m.month)))[-2:-1]
if late_record:
    late_record.write({"state": "pending", "student_confirmed": False, "submitted_date": False})
    late_record.due_date = TODAY - relativedelta(days=10)
    env["internship.attendance.monthly"]._cron_reminders()
env["internship.leave"].create(
    {
        "placement_id": placements["active_good"].id,
        "leave_type": "annual",
        "date_from": TODAY + relativedelta(days=7),
        "date_to": TODAY + relativedelta(days=11),
    }
).action_approve()
env["internship.change.request"].create(
    {
        "placement_id": placements["active_ok"].id,
        "change_type": "hours",
        "new_hours": 30,
        "reason": "Part-time study commitment",
    }
)
p = accepted("on_hold")
form(p)
approve(p)
start(p, 2)
p.action_hold(env.ref("internship_base.reason_hold_sickness"), "Student signed off sick for four weeks.")
p = accepted("terminated")
form(p)
approve(p)
start(p, 2)
p._terminate("company", env.ref("internship_base.reason_termination_company"), "Project cancelled.")

# Phase 3: completion / closure
for tag, outcome in (
    ("completion", "in_progress"),
    ("completed", "completed"),
    ("completed_2", "completed"),
    ("failed", "failed"),
):
    p = accepted(tag)
    form(p)
    approve(p)
    start(p, 6)
    fill_months(p, [0.97, 0.96, 0.94, 0.98, 0.95, 0.96], [4, 4, 5, 4, 5, 4])
    p.write({"planned_end": TODAY - relativedelta(days=3)})
    p.action_to_completion()
    attempt = p.report_attempt_ids[:1]
    if outcome == "in_progress":
        attempt.write({"report_title": "Reflective report: my year at " + p.internship_company_id.name})
        attempt.action_submit()
        continue
    attempt.write({"report_title": "Reflective report"})
    attempt.action_submit()
    if outcome == "failed":
        attempt.action_mark_fail()
        second = attempt.next_attempt_id
        second.action_submit()
        second.action_mark_fail()
        continue
    attempt.action_load_rubric()
    for score in attempt.rubric_score_ids:
        score.score = round(score.criterion_id.max_score * random.uniform(0.6, 0.85))
    attempt.write({"grade": "68 (2:1)"})
    attempt.action_mark_pass()
    env["internship.company.evaluation"].create(
        {
            "placement_id": p.id,
            "overall_rating": "5",
            "would_rehire": True,
            "skills_gained": "Python, stakeholder communication",
        }
    ).action_submit()
    env["internship.certificate"].create({"placement_id": p.id}).action_issue()
    env["internship.student.feedback"].create(
        {
            "placement_id": p.id,
            "overall_rating": random.choice(["4", "5"]),
            "learning_quality": "5",
            "supervision_quality": "4",
            "would_recommend": True,
        }
    )
    p.completion_id.action_university_accept()

# Remaining students: open applications at every other status (the admission funnel)
for status in ("draft", "submitted", "submitted", "under_review", "interview", "offered", "rejected", "declined"):
    student = next(student_iter, False) or students[random.randint(0, len(students) - 1)]
    application = env["internship.application"].create(
        {"student_id": student.id, "opportunity_id": next(opportunity_iter).id}
    )
    try:
        if status != "draft":
            application.action_submit()
        if status in ("under_review", "interview", "offered", "rejected", "declined"):
            application.action_shortlist()
        if status in ("interview", "offered", "declined"):
            application.action_interview()
        if status in ("offered", "declined"):
            application.action_offer()
        if status == "rejected":
            application.action_reject(env.ref("internship_base.reason_rejection_skills"))
        if status == "declined":
            application.action_student_decline(env.ref("internship_base.reason_decline_location"))
    except Exception as error:  # noqa: BLE001 - demo only: keep going if a student already has a placement
        _logger.info("demo application skipped: %s", error)

env["internship.placement"].search([])._recompute_risk()
env.cr.commit()
print("SEED: done")
print(
    "SEED: leads by stage",
    {s.name: c for s, c in Lead._read_group([("lead_category", "!=", False)], ["stage_id"], ["__count"])},
)
print(
    "SEED: placements by stage",
    {s.code: c for s, c in env["internship.placement"]._read_group([], ["stage_id"], ["__count"])},
)
