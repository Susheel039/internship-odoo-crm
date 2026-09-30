# Vapi assistant setup

How to configure the two Vapi assistants that work with the `internship_vapi` module.
Check the current Vapi dashboard and [docs.vapi.ai](https://docs.vapi.ai) for exact field
names. All payload parsing on the Odoo side lives in
`custom_addons/internship_vapi/services/vapi_adapter.py`, so a Vapi format change touches
one file.

## 1. Odoo side first

Settings › Internship CRM › **Voice AI (Vapi)**:

| Setting | Value |
|---|---|
| Enable calling | Off until testing is finished (kill switch) |
| Vapi API Key | Private API key from the Vapi dashboard |
| Webhook Token | A long random string, e.g. `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| Phone Number ID | The Vapi phone number used for outbound calls (UK number) |
| Lead Generation Assistant ID | Assistant A below |
| Workflow Chaser Assistant ID | Assistant B below |
| Calling window | Mon–Fri (`0,1,2,3,4`), 09:00–20:00, `Europe/London` |
| Max Attempts | 3 |

Keys and tokens are stored as system parameters, never in Git, and never logged.

Queued calls are dialled by the cron **Internship: Voice AI call queue** every 5 minutes,
only when: calling is enabled, it is inside the window, the lead is not *Do Not Call*,
company marketing calls have *TPS/CTPS Checked*, and attempts are below the maximum.

## 2. Server URL and headers (both assistants)

| Item | Value |
|---|---|
| Server URL | `https://<your-odoo-host>/internship/call-tracking/webhook` |
| Header | `Authorization: Bearer <Webhook Token>` |
| Server messages | `status-update`, `end-of-call-report`, `tool-calls` |
| Tool server URL | `https://<your-odoo-host>/internship/vapi/tool` (same header) |

Odoo answers `401` to a missing or wrong token and refuses plain HTTP from anywhere but
localhost. Every event is stored in *CRM › Webhook Events* before it is processed, and
retries of the same event are ignored.

Metadata Odoo sends with every outbound call: `odoo_db`, `call_log_id`, `lead_id`,
`student_id`, `placement_id`, `purpose`. Leave it untouched so reports link back.

## 3. Assistant A: Lead Generation

Outbound calls to companies and students, and inbound enquiries.

**First message**

> Hello, this is the internship team's virtual assistant calling from {{university_name}}.
> This call is recorded for quality and training. Is now a good time for a quick chat?

**System prompt outline**

- UK English, friendly and brief. Say the call is recorded **in the first sentence**.
- Say that you are an AI assistant if asked, and never pretend to be a person.
- Ask for explicit consent before saving contact details or calling again
  (`consent_to_contact`), and ask separately whether recording is OK (`recording_consent`).
- For companies: explain the internship scheme, ask about roles, sites, hours and whether
  they would host a student; offer a callback with a coordinator.
- For students: ask about course, year, interests and preferred locations.
- **Never** give legal, immigration or visa advice. Say a coordinator will follow up.
- Hand off to a human whenever the caller asks, or is upset or confused.
- Before ending, call `create_or_update_lead` and, if a callback was agreed, `book_callback`.

**Variable values**: `{{student_name}}`, `{{company_name}}`, `{{university_name}}`, `{{purpose}}`.

## 4. Assistant B: Workflow Chaser

Reminders for overdue documents, internship forms, monthly attendance records and feedback.

**First message**

> Hello {{student_name}}, this is the placement office's virtual assistant. This call is
> recorded. I'm calling about your internship {{placement_ref}}.

**System prompt outline**

- UK English, polite, under two minutes. Recording disclosure first.
- Purpose-specific script:
  - `document_chase`: remind that documents (or, for companies, the internship form) are due
    by `{{due_date}}`.
  - `attendance_reminder`: remind about this month's record, due `{{due_date}}`.
    `confirm_monthly_submission` can check whether it is already in.
  - `feedback_request`: ask the line manager to complete the evaluation.
- Verify identity with `get_placement_status` (student ID and date of birth) before
  discussing any placement detail. Never read out personal data.
- No legal or visa advice; offer a human callback.

**Variable values**: `{{student_name}}`, `{{company_name}}`, `{{placement_ref}}`,
`{{due_date}}`, `{{purpose}}`, `{{university_name}}`.

## 5. Structured data schema (analysis plan)

Maps 1:1 to `crm.lead` fields (see `services/lead_sync.py`):

```json
{
  "type": "object",
  "properties": {
    "name":               {"type": "string",  "description": "Caller's full name -> contact_name"},
    "organisation":       {"type": "string",  "description": "Company or university -> partner_name"},
    "role":               {"type": "string",  "description": "Job title -> function"},
    "email":              {"type": "string",  "description": "-> email_from"},
    "phone":              {"type": "string",  "description": "UK number; stored as E.164 -> phone"},
    "lead_category":      {"type": "string",  "enum": ["student", "company", "university", "other"]},
    "interest_level":     {"type": "string",  "enum": ["cold", "warm", "hot"]},
    "callback_datetime":  {"type": "string",  "description": "ISO 8601, UK time"},
    "consent_to_contact": {"type": "boolean"},
    "recording_consent":  {"type": "boolean"},
    "notes":              {"type": "string",  "description": "Posted to the lead's chatter"}
  }
}
```

After an `end-of-call-report` with purpose `lead_generation` or `inbound_enquiry`, Odoo
creates or updates a `crm.lead` (dedupe by E.164 phone, then e-mail), sets the source
channel, interest and consent, schedules a callback activity, and posts the summary.

## 6. Tools (function calling)

All tools use the tool server URL above and return a short sentence the assistant can read
out. Errors come back as friendly sentences, never stack traces.

| Tool | Parameters | Returns |
|---|---|---|
| `create_or_update_lead` | `name`, `organisation`, `role`, `email`, `phone`, `lead_category`, `interest_level`, `notes`, `consent_to_contact` | Confirmation with the lead reference |
| `book_callback` | `lead_ref` (from the previous tool), `datetime_iso` | Confirmation, or a request for another time |
| `get_placement_status` | `student_id`, `date_of_birth` (YYYY-MM-DD) | Stage name and next action, **only if both match**. Otherwise a generic "could not verify" |
| `confirm_monthly_submission` | `placement_ref`, `student_id` | Whether this month's record is submitted |

JSON schema for each tool's parameters: every field is a `string`, except
`consent_to_contact`, which is a `boolean`.

## 7. Test plan

1. **Web call, no phone line.** In the Vapi dashboard use *Talk to assistant* (web call)
   with the server URL pointing at a staging Odoo (use a tunnel such as `cloudflared` for a
   local stack). Check that a *Webhook Event* and a *Call Log* appear, and that the
   `end-of-call-report` fills transcript, summary, cost and ended reason.
2. **Lead creation.** As a "company", give a name, organisation, UK mobile in `07…` form
   and consent. Expect one `crm.lead` with the phone in `+44…` form, source *Voice AI
   (inbound)*, interest level and a chatter summary. Call again with the same number:
   still one lead.
3. **Callback.** Agree a callback time and check the lead's *Callback At* and the *Call*
   activity.
4. **Identity check.** Ask for placement status with a wrong date of birth: generic refusal
   and nothing personal disclosed. Then with the right one: stage and next action only.
5. **Outbound queue.** With calling disabled, press *Call with AI* on a lead: the call log
   stays *Queued*. Enable calling inside the window: the cron dials within 5 minutes.
   Mark the lead *Do Not Call*: the queued call is cancelled.
6. **Security.** `curl -X POST` the webhook without the header and expect `401`.
7. **Automated tests.** `make test MODULE=internship_vapi` runs the adapter, client (mocked
   HTTP), queue rules, tools and webhook tests.
