# Internship CRM v2: workflow

Everything after a student accepts an offer happens on one record, the **placement**
(`internship.placement`). Stages are configurable (*Configuration › Placement Stages*), but
their **codes** drive the automation, so rename stages freely and keep the codes.

```
Application:  draft → submitted (Applied) → under_review (Shortlisted) → interview → offered
                                                                              │
                              rejected / withdrawn / declined  ◄──────────────┤
                                                                              ▼
                                                              accepted  ── creates the placement

Placement, phase 1 (admission / approval)
  form_requested ──(company submits internship form)──► under_review
  under_review ──(schedule meeting)──► meeting ──(held)──► under_review | more_docs
  under_review ──(university decision)──► agreement | more_docs | rejected ✗
  more_docs ──(all mandatory documents accepted; review round +1)──► under_review
  agreement ──(company → student → university sign)──► approved
                                   └─ other open applications auto-withdrawn

Placement, phase 2 (monitoring)
  approved ──(start / cron on planned start)──► active ◄──► on_hold
  active | on_hold ──(terminate: who + reason)──► terminated ✗  (+ exit meeting)
  monthly record each month: student submits → company confirms → university reviews
       low attendance / low rating / not working as required → tripartite meeting, risk red

Placement, phase 3 (completion / closure)
  active ──(end / cron after planned end)──► completion
       creates report attempt 1 + completion checklist
  report fail with attempts left → new attempt (resubmission deadline)
  final attempt fails ──► failed ✗
  checklist complete (report passed, company evaluation, certificate, student feedback)
       + university accepts ──► completed ✓
```

## Who does what

| Step | Who | Where |
|---|---|---|
| Apply, accept or decline an offer | Student | Application (portal: *My placements*) |
| Shortlist, interview, offer | Company / university | Application |
| Internship form (objectives, H&S, signed form) | Company line manager | Placement › *Offer & Form* (portal) |
| Review checklist and decision | University staff | *University Decision* button |
| Upload requested documents | Student / company | Document request (portal) |
| Sign agreement | Company, then student, then university | E-mailed signing link |
| Monthly record | Student submits, line manager confirms, tutor reviews | Monthly attendance (portal) |
| Leave, change requests | Student / company; both parties approve changes | Placement › *Leave & Changes* |
| Final report | Student submits, marker grades with rubric | Final reports |
| Evaluation and certificate | Line manager | Placement › *Completion* (portal) |
| Feedback | Student | Portal |
| Close | University | Completion checklist › *University Accepts* |

## Automations (daily unless noted)

| Job | What it does |
|---|---|
| Form and document request reminders | Chases overdue internship forms and document requests (every 3 days, max 3); refreshes risk flags |
| Start and end placements | approved → active on the planned start; active → completion after the planned end |
| Create monthly records | Current month's record for every active placement |
| Monthly reminders and lateness | Reminds students before the due date; marks records late after due + grace |
| Escalation check | Runs the tripartite rules on approved records not yet checked |
| Agreement reminders | Reminds the current signer every 3 days, max 3 |
| Report deadlines | Marks late report attempts; flags the tutor |
| Expiry alerts | Insurance, company pre-approval, right to work and visa expiry → coordinator to-do; lapsed pre-approval → expired |
| Document expiry | Registered documents past their expiry → expired |
| GDPR retention (weekly) | Flags students past their retention date for review. Never deletes |
| Voice AI call queue (every 5 min) | Dials queued calls inside the calling window, with the compliance checks |

All jobs are idempotent: running one twice does not duplicate activities, records or e-mails.

## Rules and where they come from

Workflow rules (form due days, monthly due day, grace days, report deadline, resubmission
window, maximum attempts, tripartite thresholds, expiry alert days, retention years) resolve
in this order: **programme → university default → system setting** (*Settings › Internship
CRM*) → built-in default. See `internship.program._get_rule()`.
