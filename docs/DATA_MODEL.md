# Internship CRM v2: data model

```
                      res.partner  (identity of every university, student, company, line manager)
                           ▲
 internship.university ────┼──── internship.university.contact (coordinator / tutor / admin)
   │ 1..n                   │
   ▼                        │
 internship.program ── rules, templates, rubric criteria, custom-field definitions
   │                        │
   ▼                        │
 internship.student ────────┘        internship.company ── sites, line managers, vetting
   │                                        │
   │   internship.opportunity ◄─────────────┘
   │          │
   ▼          ▼
 internship.application ──(accepted)──► internship.placement  ◄── the hub
                                              │
      ┌───────────────┬──────────────┬────────┼─────────┬──────────────┬───────────────┐
      ▼               ▼              ▼        ▼         ▼              ▼               ▼
 university.review  document.request  agreement  attendance.monthly  meeting    submission (report attempt)
                    └ request.line    └ signer   (+ daily attendance) └ attendee  └ rubric.score
 document (register)  leave  change.request   performance   company.evaluation  certificate
                                                             student.feedback    completion (checklist)
 crm.lead (lead_category, student/company/university/placement links) ── internship.call.log ── vapi.event
```

## Modules

| Module | Models |
|---|---|
| `internship_base` | university, university.contact, program, student, company, company.site, line.manager, opportunity, application; lookups: reason, document.type, academic.year, skill, sector, rubric.criterion; mixins: lookup, deadline, approval, external.ref; reason wizard |
| `internship_placement` | placement, placement.stage, university.review, document.request (+ line), document, leave, change.request; placement.link mixin; wizards: request documents, terminate, invite company |
| `internship_agreement` | agreement, agreement.signer |
| `internship_monitoring` | attendance.monthly, attendance (daily), performance, meeting, meeting.attendee |
| `internship_completion` | submission (report attempt), rubric.score, company.evaluation, certificate, student.feedback, completion (checklist) |
| `internship_crm` | crm.lead extension; internship.crm.lead (legacy, read-only) |
| `internship_vapi` | call.log, vapi.event; crm.lead call statistics |
| `internship_reporting` | report (live KPIs); graph and pivot analyses |
| `internship_portal` | portal controllers and templates (no new models) |

## Conventions

- **One hub.** Workflow records carry `placement_id` (index; `cascade` for child lines,
  `restrict` for documents of record such as agreements, certificates, report attempts).
  `internship.placement.link.mixin` adds stored `student_id`, `internship_company_id`,
  `university_id`, `program_id` for search and record rules.
- **Never `company_id` for internship companies on new models.** `company_id` is Odoo's
  `res.company`; new fields use `internship_company_id`. (Some v1 models still have a
  `company_id` to `internship.company`; mail is told to ignore it.)
- **References** from `ir.sequence`: `APP-`, `INT-`, `AGR-`, `DOC-`, `CERT-`, `MEET-`.
- **Files** only through `ir.attachment`.
- **Custom fields per programme** with `fields.Properties` (placement and student), defined
  on the programme.
- **Integrity:** one open placement per student (partial unique index); one monthly record
  per placement per month; one completion checklist per placement; external references
  unique per source.
- **Audit:** `tracking=True` on statuses, dates and approvals; chatter on every workflow form.

## What changed from v1 (data safety)

| v1 | v2 | How |
|---|---|---|
| Application statuses `documentation/agreement/approved/placed` | Placement stages `under_review/agreement/approved/active` | `internship_base` pre-migration records them; `internship_placement` install hook creates the placements |
| Attendance, performance, meetings, submissions, completions keyed by student | Also linked to the placement | Post-migrations match on student (+ opportunity) |
| `internship.crm.lead` | `crm.lead` | Post-migration copies each lead once; legacy model kept read-only |
| `internship.completion.final_report`, `evaluation_score` | Report attempts and company evaluation | Fields deprecated and hidden; columns and data kept |
| Relabelled only (keys unchanged) | Application and submission statuses, `company_registration_number` → "Companies House No.", meeting minutes / action items | No data change |
