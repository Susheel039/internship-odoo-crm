"""30 CRM leads, each walked through its own pipeline journey (demo / training data).

Run after seed_workflow_demo.py (it links won leads to the companies and students created
there):

    make demo-data

Every lead starts at New and moves stage by stage with tracking on, so the chatter shows the
journey (stage changes, notes, AI calls, callbacks, conversion or loss) with realistic dates.
The 30 leads cover the cases the CRM has to handle:

 happy paths, fast-track referrals, conversions to company and student records, losses at
 every stage (with reasons), unanswered calls up to the attempt limit, Do Not Call, missing
 TPS check, missing consent, consent withdrawn, callbacks (upcoming and overdue), duplicate
 contacts merged by phone / e-mail, re-opened leads, inbound AI enquiries, n8n automation,
 hand-off to a human (visa questions), and a student whose placement was later rejected.

Idempotent: if the marker lead exists, nothing is created.
"""

from datetime import datetime, timedelta

env = env  # noqa: F821 - provided by `odoo shell`
env = env(user=env.ref("base.user_admin"))  # messages authored by Administrator, not OdooBot
NOW = datetime.now()
MARKER = "J01 Harbour Health NHS Trust - clinical informatics interns"

Lead = env["crm.lead"]
if Lead.with_context(active_test=False).search_count([("name", "=", MARKER)]):
    print("SEED: CRM journeys already present, nothing to do")
    raise SystemExit(0)

CallLog = env["internship.call.log"]
stage = Lead._internship_stage
admin = env.ref("base.user_admin")
nbu = env["internship.university"].search([("code", "=", "NBU")], limit=1)


def lost_reason(name):
    return env["crm.lost.reason"].search([("name", "=", name)], limit=1) or env["crm.lost.reason"].create(
        {"name": name}
    )


def company(name):
    return env["internship.company"].search([("name", "=", name)], limit=1)


phone_numbers = iter(range(500, 999))


def uk_phone():
    return f"+44 7700 900{next(phone_numbers):03d}"


def backdate(lead, since_id, when):
    """Give every message posted on the lead since `since_id` the date `when`."""
    env.cr.execute(
        "UPDATE mail_message SET date = %s WHERE model = 'crm.lead' AND res_id = %s AND id > %s",
        (when, lead.id, since_id),
    )


def commit_tracking():
    """Odoo writes stage-change tracking at commit time; run it now so each step gets its own entry."""
    env.flush_all()
    env.cr.precommit.run()


def last_message_id():
    env.cr.execute("SELECT COALESCE(MAX(id), 0) FROM mail_message")
    return env.cr.fetchone()[0]


def call(lead, when, status, summary=None, purpose="lead_generation", direction="outbound"):
    return CallLog.create(
        {
            "name": f"AI call: {lead.contact_name or lead.name}",
            "lead_id": lead.id,
            "purpose": purpose,
            "direction": direction,
            "call_type": direction,
            "status": status,
            "call_datetime": when,
            "duration_seconds": {"completed": 210, "no_answer": 0, "failed": 0}.get(status, 0),
            "customer_number": lead.phone,
            "ended_reason": {
                "completed": "customer-ended-call",
                "no_answer": "customer-did-not-answer",
                "failed": "pipeline-error",
            }.get(status),
            "cost": 0.12 if status == "completed" else 0.0,
            "summary": summary,
            "attempt_count": 1,
            "transcript": "AI: Hello, this call is recorded for quality and training. ..."
            if status == "completed"
            else False,
        }
    )


# Each journey: list of steps (days_ago, stage_code or None, note, call_status or None)
J = []


def journey(code, name, category, channel, interest, contact, organisation, steps, **extra):
    J.append(
        {
            "code": code,
            "name": f"{code} {name}",
            "category": category,
            "channel": channel,
            "interest": interest,
            "contact": contact,
            "organisation": organisation,
            "steps": steps,
            **extra,
        }
    )


# ---------------- Companies (15) ----------------
journey(
    "J01",
    "Harbour Health NHS Trust - clinical informatics interns",
    "company",
    "referral",
    "hot",
    "Dr Nia Rees",
    "Harbour Health NHS Trust",
    [
        (58, "new", "Referral from the university's NHS partnership team.", None),
        (55, "contacted", "Intro call held: they host 4 interns a year in clinical informatics.", "completed"),
        (48, "qualified", "Roles, Leeds site and September start confirmed. Insurance certificate received.", None),
        (40, "interview", "Site visit with the placement coordinator done.", None),
        (33, "won", "Agreed to host. Company record vetted and placements created.", None),
    ],
    link_company="Harbour Health NHS Trust",
)
journey(
    "J02",
    "Riverside Analytics - data placements (fast track)",
    "company",
    "vapi_outbound",
    "hot",
    "Sam Patel",
    "Riverside Analytics Ltd",
    [
        (45, "new", "Outbound AI campaign to data-analytics firms.", "completed"),
        (43, "qualified", "Fast track: decision maker on the first call, needs 3 data interns.", None),
        (38, "won", "Signed up the same week. Company vetted.", None),
    ],
    link_company="Riverside Analytics Ltd",
)
journey(
    "J03",
    "Northern Lights Studio - UX intern (won, vetting pending)",
    "company",
    "vapi_inbound",
    "warm",
    "Eve Marsh",
    "Northern Lights Studio",
    [
        (30, "new", "Inbound AI enquiry: small studio wants a UX intern.", "completed"),
        (27, "contacted", "Explained the scheme and the vetting checks.", None),
        (20, "qualified", "Role and mentor confirmed.", None),
        (15, "won", "Converted. Vetting is pending: risk assessment not yet uploaded.", None),
    ],
    link_company="Northern Lights Studio",
)
journey(
    "J04",
    "Castleford Logistics - lost at Qualified (no budget)",
    "company",
    "campus_event",
    "cold",
    "Rob Hale",
    "Castleford Logistics",
    [
        (50, "new", "Met at the autumn careers fair.", None),
        (46, "contacted", "Follow-up call.", "completed"),
        (40, "qualified", "Interested, but only for unpaid roles.", None),
        (35, "lost", "No budget for paid placements this year (the scheme requires pay).", None),
    ],
    lost="No budget",
)
journey(
    "J05",
    "Pinewood Care Homes - lost at Contacted (not interested)",
    "company",
    "vapi_outbound",
    "cold",
    "Mark Doyle",
    "Pinewood Care Homes",
    [
        (26, "new", "Outbound AI campaign to care providers.", None),
        (25, "contacted", "Spoke to the manager.", "completed"),
        (24, "lost", "Not interested in hosting students.", None),
    ],
    lost="Not interested",
)
journey(
    "J06",
    "Atlas Legal Services - lost at Interview (chose another university)",
    "company",
    "referral",
    "warm",
    "Jo Briggs",
    "Atlas Legal Services",
    [
        (60, "new", "Referral from an alumna.", None),
        (57, "contacted", "Call booked.", "completed"),
        (50, "qualified", "Two paralegal internships.", None),
        (44, "interview", "Met the coordinator.", None),
        (37, "lost", "Chose another university's scheme with an earlier start date.", None),
    ],
    lost="Chose another provider",
)
journey(
    "J07",
    "Greenway Energy - 3 unanswered AI calls (attempt limit)",
    "company",
    "vapi_outbound",
    "cold",
    "Zara Khan",
    "Greenway Energy",
    [
        (21, "new", "Outbound campaign.", "no_answer"),
        (18, None, "Second attempt.", "no_answer"),
        (
            15,
            "contacted",
            "Third attempt - no answer. Max attempts reached; e-mail follow-up sent instead.",
            "no_answer",
        ),
    ],
)
journey(
    "J08",
    "Blue Harbour Cafe - asked for Do Not Call",
    "company",
    "vapi_outbound",
    "cold",
    "Owner",
    "Blue Harbour Cafe",
    [
        (19, "new", "Outbound campaign.", None),
        (
            17,
            "contacted",
            "Owner asked not to be called again. Marked Do Not Call; queued calls cancelled.",
            "completed",
        ),
    ],
    do_not_call=True,
)
journey(
    "J09",
    "Oakline Retail Group - TPS not checked (call blocked)",
    "company",
    "vapi_outbound",
    "warm",
    "Liam Carter",
    "Oakline Retail Group",
    [
        (6, "new", "Added to the retail campaign. The AI call is held until the TPS/CTPS check is done.", None),
    ],
    tps_checked=False,
    queue_blocked=True,
)
journey(
    "J10",
    "Brightwater Engineering - summer scheme (callback booked)",
    "company",
    "campus_event",
    "hot",
    "Kate Owens",
    "Brightwater Engineering plc",
    [
        (35, "new", "Met at the engineering fair.", None),
        (31, "contacted", "Positive first call.", "completed"),
        (24, "qualified", "Wants 5 mechanical design interns.", None),
        (12, "interview", "Asked for a callback with the head of engineering on Thursday.", "completed"),
    ],
    callback_days=2,
)
journey(
    "J11",
    "Meridian Finance - new from careers fair (AI call queued)",
    "company",
    "campus_event",
    "warm",
    "Hannah Webb",
    "Meridian Finance LLP",
    [
        (2, "new", "Business card from the finance fair. AI call queued for tomorrow morning.", None),
    ],
    queue_call=True,
)
journey(
    "J12",
    "Kestrel Software - duplicate merged by phone",
    "company",
    "vapi_inbound",
    "warm",
    "Omar Aziz",
    "Kestrel Software",
    [
        (29, "new", "Inbound AI enquiry.", "completed"),
        (
            22,
            "contacted",
            "Same caller rang again from the same number: matched to this lead (no duplicate).",
            "completed",
        ),
        (16, "qualified", "Two backend roles, hybrid in Manchester.", None),
    ],
)
journey(
    "J13",
    "Hollis & Grant Architects - re-opened after loss",
    "company",
    "referral",
    "warm",
    "Clara Hollis",
    "Hollis & Grant Architects",
    [
        (70, "new", "Referral.", None),
        (66, "lost", "Not this year - office move.", None),
        (9, "new", "Re-opened: they called back after the move and now want a design intern.", "completed"),
    ],
    lost_then_reopened=True,
)
journey(
    "J14",
    "Silverline Media - inbound AI enquiry",
    "company",
    "vapi_inbound",
    "warm",
    "Priya Nair",
    "Silverline Media",
    [
        (11, "new", "Inbound AI call asking how hosting works.", "completed"),
        (10, "contacted", "Information pack e-mailed after the call.", None),
    ],
)
journey(
    "J15",
    "Quayside Hotels - from n8n web form automation",
    "company",
    "n8n",
    "cold",
    "Events Team",
    "Quayside Hotels",
    [
        (1, "new", "Created by the n8n automation from the website 'Host an intern' form.", None),
    ],
)

# ---------------- Students (12) ----------------
journey(
    "J16",
    "Chloe Evans - inbound AI enquiry, converted to student",
    "student",
    "vapi_inbound",
    "hot",
    "Chloe Evans",
    False,
    [
        (40, "new", "Rang the AI line about software placements.", "completed"),
        (38, "contacted", "Coordinator follow-up call.", None),
        (33, "qualified", "Eligible: year 2 Computer Science, right to work verified.", None),
        (29, "won", "Registered as a student and applying to opportunities.", None),
    ],
    convert="student",
)
journey(
    "J17",
    "Ravi Shah - portal sign-up, converted and applied",
    "student",
    "portal",
    "warm",
    "Ravi Shah",
    False,
    [
        (36, "new", "Signed up on the student portal.", None),
        (34, "qualified", "Business Management, wants finance placements.", None),
        (30, "won", "Student record created; applied to Finance Graduate Intern.", None),
    ],
    convert="student",
)
journey(
    "J18",
    "Ella Price - design student at interview",
    "student",
    "vapi_inbound",
    "hot",
    "Ella Price",
    False,
    [
        (20, "new", "Inbound AI enquiry.", "completed"),
        (18, "contacted", "Portfolio received.", None),
        (14, "qualified", "Strong UX portfolio.", None),
        (8, "interview", "Interview with Northern Lights Studio booked.", None),
    ],
)
journey(
    "J19",
    "Noah Clarke - visa question handed to a human",
    "student",
    "vapi_inbound",
    "warm",
    "Noah Clarke",
    False,
    [
        (13, "new", "Asked the AI whether his student visa allows a paid placement.", "completed"),
        (
            12,
            "qualified",
            "The AI gave no visa advice and handed over to the international student adviser, as required.",
            None,
        ),
    ],
)
journey(
    "J20",
    "Mia Hughes - consent withdrawn",
    "student",
    "vapi_inbound",
    "cold",
    "Mia Hughes",
    False,
    [
        (25, "new", "Inbound enquiry, consent to contact given.", "completed"),
        (22, "contacted", "Follow-up e-mail.", None),
        (18, "lost", "Withdrew consent to be contacted. Consent removed; no further calls.", None),
    ],
    lost="Consent withdrawn",
    consent=False,
)
journey(
    "J21",
    "Leo Ahmed - no consent recorded yet",
    "student",
    "portal",
    "warm",
    "Leo Ahmed",
    False,
    [
        (4, "new", "Portal enquiry without the consent box ticked: cannot be called until consent is recorded.", None),
    ],
    consent=False,
)
journey(
    "J22",
    "Ruby Scott - referred by her tutor",
    "student",
    "university",
    "warm",
    "Ruby Scott",
    False,
    [
        (16, "new", "Referred by her academic tutor.", None),
        (14, "contacted", "Intro call.", "completed"),
        (10, "qualified", "Marketing student, wants an agency placement.", None),
    ],
)
journey(
    "J23",
    "Finn Walsh - did not attend interview",
    "student",
    "vapi_inbound",
    "cold",
    "Finn Walsh",
    False,
    [
        (42, "new", "Inbound enquiry.", "completed"),
        (39, "contacted", "Follow-up.", None),
        (35, "qualified", "Data Science student.", None),
        (30, "interview", "Interview booked with Riverside Analytics.", None),
        (27, "lost", "Did not attend the interview and did not reply to two reminders.", "no_answer"),
    ],
    lost="Did not attend",
)
journey(
    "J24",
    "Grace Morgan - duplicate merged by e-mail",
    "student",
    "portal",
    "warm",
    "Grace Morgan",
    False,
    [
        (15, "new", "Portal sign-up.", None),
        (9, "contacted", "Signed up again with the same e-mail: matched to this lead instead of a duplicate.", None),
    ],
)
journey(
    "J25",
    "Oscar Bell - cold student lead",
    "student",
    "campus_event",
    "cold",
    "Oscar Bell",
    False,
    [
        (3, "new", "Left details at the freshers' fair.", None),
    ],
)
journey(
    "J26",
    "Lily Walker - callback overdue",
    "student",
    "vapi_inbound",
    "hot",
    "Lily Walker",
    False,
    [
        (12, "new", "Inbound AI enquiry.", "completed"),
        (11, "contacted", "Asked for a callback last Friday; not done yet (overdue activity).", None),
    ],
    callback_days=-3,
)
journey(
    "J27",
    "Theo Reed - converted, placement later rejected",
    "student",
    "referral",
    "warm",
    "Theo Reed",
    False,
    [
        (90, "new", "Referral from a friend on placement.", None),
        (86, "qualified", "Eligible.", None),
        (
            80,
            "won",
            "Became a student; accepted an offer. The university later rejected the placement on H&S grounds.",
            None,
        ),
    ],
    convert="student",
    link_rejected_placement=True,
)

# ---------------- University and other (3) ----------------
journey(
    "J28",
    "Westfield University - partnership won",
    "university",
    "university",
    "hot",
    "Prof. Anne Moss",
    "Westfield University",
    [
        (75, "new", "Enquiry from the careers service.", None),
        (70, "contacted", "Demo of the platform.", "completed"),
        (62, "qualified", "Wants to use the platform for 2 programmes.", None),
        (55, "interview", "Meeting with the Pro-Vice-Chancellor.", None),
        (48, "won", "Partnership agreed from next academic year.", None),
    ],
)
journey(
    "J29",
    "Eastgate College - framework agreement pending",
    "university",
    "referral",
    "warm",
    "Dr Sam Ortiz",
    "Eastgate College",
    [
        (28, "new", "Referral from Westfield.", None),
        (24, "contacted", "Intro call.", "completed"),
        (17, "qualified", "Framework agreement with the legal team.", None),
    ],
)
journey(
    "J30",
    "Northern Careers Expo - event organiser",
    "other",
    "other",
    "cold",
    "Expo Team",
    "Northern Careers Expo",
    [
        (5, "new", "Organiser offering a stand at the spring expo.", None),
    ],
)

# ---------------------------------------------------------------------------
created = Lead
for spec in J:
    first_day = spec["steps"][0][0]
    email_domain = (spec["organisation"] or "students").split()[0].lower().replace("&", "and")
    lead = Lead.create(
        {
            "name": spec["name"],
            "type": "opportunity",
            "lead_category": spec["category"],
            "stage_id": stage("new").id,
            "source_channel": spec["channel"],
            "interest_level": spec["interest"],
            "contact_name": spec["contact"],
            "partner_name": spec["organisation"] or False,
            "email_from": f"{spec['contact'].split()[-1].lower()}@{email_domain}.example",
            "phone": uk_phone(),
            "consent_to_contact": spec.get("consent", True),
            "consent_date": (NOW - timedelta(days=first_day)) if spec.get("consent", True) else False,
            "recording_consent": spec["channel"].startswith("vapi"),
            "tps_checked": spec["category"] == "company" and spec.get("tps_checked", True),
            "tps_checked_date": (NOW - timedelta(days=first_day)).date()
            if spec["category"] == "company" and spec.get("tps_checked", True)
            else False,
            "university_id": nbu.id if spec["category"] == "student" else False,
            "priority": {"hot": "3", "warm": "2", "cold": "1"}[spec["interest"]],
            "user_id": admin.id,
        }
    )
    commit_tracking()
    env.cr.execute("UPDATE crm_lead SET create_date = %s WHERE id = %s", (NOW - timedelta(days=first_day), lead.id))
    backdate(lead, 0, NOW - timedelta(days=first_day))
    for index, (days_ago, stage_code, note, call_status) in enumerate(spec["steps"]):
        when = NOW - timedelta(days=days_ago, hours=index)
        before = last_message_id()
        values = {}
        if stage_code and (index or stage_code != "new"):
            values["stage_id"] = stage(stage_code).id
            if stage_code == "lost" and spec.get("lost"):
                values["lost_reason_id"] = lost_reason(spec["lost"]).id
            if stage_code == "new" and spec.get("lost_then_reopened"):
                values["lost_reason_id"] = False
        if values:
            lead.write(values)
        lead.message_post(body=note)
        if call_status:
            call(
                lead,
                when,
                call_status,
                summary=note if call_status == "completed" else False,
                purpose="inbound_enquiry" if spec["channel"] == "vapi_inbound" else "lead_generation",
                direction="inbound" if spec["channel"] == "vapi_inbound" else "outbound",
            )
        commit_tracking()
        backdate(lead, before, when)

    # Outcomes and special cases
    if spec.get("do_not_call"):
        lead.do_not_call = True
        log = CallLog.create(
            {
                "name": "Queued follow-up (cancelled)",
                "lead_id": lead.id,
                "purpose": "lead_generation",
                "status": "cancelled",
                "customer_number": lead.phone,
                "error_message": "The contact is marked Do Not Call.",
            }
        )
    if spec.get("queue_call") or spec.get("queue_blocked"):
        log = CallLog.action_queue_call("lead_generation", lead, scheduled_at=NOW + timedelta(days=1))
        settings = dict(CallLog._settings(), enabled=True)
        reason = log._blocked_reason(settings)
        if reason:
            log.error_message = reason
    if spec.get("callback_days") is not None:
        when = NOW + timedelta(days=spec["callback_days"])
        lead.callback_datetime = when
        lead.activity_schedule(
            "mail.mail_activity_data_call",
            date_deadline=when.date(),
            summary=f"Call back {spec['contact']}",
            user_id=admin.id,
        )
    if spec.get("link_company"):
        linked = company(spec["link_company"])
        if linked:
            lead.internship_company_id = linked
    if spec.get("convert") == "student":
        existing = env["internship.student"].search([("name", "=", spec["contact"])], limit=1)
        if existing:
            lead.student_id = existing
        else:
            lead.action_convert_to_student()
    if spec.get("link_rejected_placement"):
        rejected = env["internship.placement"].search([("stage_code", "=", "rejected")], limit=1)
        if rejected:
            lead.placement_id = rejected
    created |= lead

env.cr.commit()
print("SEED: CRM journeys done:", len(created), "leads")
print(
    "SEED: leads by stage",
    {s.name: c for s, c in Lead._read_group([("lead_category", "!=", False)], ["stage_id"], ["__count"])},
)
print("SEED: calls", CallLog.search_count([]))
