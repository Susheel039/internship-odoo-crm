# Internship CRM

UK internship management platform on **Odoo 19 Community**, connecting universities,
students and host companies (line managers) from application to certificate, with a Vapi
voice assistant for lead generation and chasing. Odoo core is not modified: everything is
in `custom_addons/`.

## Quick start

```sh
make up            # creates .env and config/odoo.conf from the examples, starts Docker
make init DEMO=1   # new database internship_dev with all modules (+ UK demo data)
```

Open <http://localhost:8069>, sign in as `admin` / `admin`, then change the password.
`make help` lists every shortcut.

- Credentials live only in `.env` (gitignored). `config/odoo.conf` is gitignored too and is
  created from `config/odoo.conf.example`.
- PostgreSQL is published on `127.0.0.1:5432` only.
- Debugger: `cp docker-compose.override.yml.example docker-compose.override.yml`,
  `docker compose up -d --build`, then use **Attach to Odoo (debugpy)** in VS Code.

## Modules

| Module | What it adds |
|---|---|
| `internship_base` | Universities (+ contacts), programmes (workflow rules, templates, rubric, custom fields), students (compliance, visa, adjustments, GDPR retention), companies (sites, vetting, invitations), line managers, opportunities, applications; lookups; shared mixins; groups and record rules; expiry and retention crons; settings |
| `internship_placement` | The placement hub: configurable stages, university review, document requests and register, leave, change requests, termination, self-sourced placements |
| `internship_agreement` | Three-party agreement (QWeb PDF + SHA-256), sequential in-app e-signature with public signing links, amendments |
| `internship_monitoring` | Monthly attendance (student, company, university), escalation to tripartite meetings, meetings with calendar sync, daily log, performance reviews |
| `internship_completion` | Final report attempts with rubric and resubmission, company evaluation, certificate, student feedback, completion checklist |
| `internship_crm` | Internship leads on native `crm.lead`: categories, links, UK contact compliance, conversions; legacy leads migrated |
| `internship_vapi` | Vapi calls: queue with calling window and compliance checks, webhook inbox, tools, automatic lead capture |
| `internship_reporting` | Live KPI dashboard and analyses (placements, monthly attendance, applications, completions, calls, leads) |
| `internship_portal` | Portal pages for students and line managers (`/my/placements`) |

Dependency graph, models and conventions: [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Dashboard and demo data

**Internship CRM › Dashboard** shows KPI cards (students, open applications, placements in
admission and on placement, at-risk placements, completion rate, hot leads, AI calls this
month) and charts: the placement pipeline by stage, open placements by phase, monthly
attendance against the tripartite threshold, placement health, applications by status, the
CRM pipeline, leads by source and AI calls per week, plus the placements needing attention
and upcoming callbacks. Filter by university. Click any card, bar or slice to open the
records behind it.

To explore the workflow with realistic data, load the demo story into a **demo** database
(never into real data):

```sh
make init DB=internship_v2_demo DEMO=1
make demo-data DB=internship_v2_demo
```

It creates 20 CRM leads across New → Contacted → Qualified → Interview → Won / Lost (each
lead's notes explain what that stage means and the next step), won leads converted into
companies and students, two months of AI call logs, applications at every status, and
placements in every stage: form requested through agreement, active with monthly attendance
history (one escalated to a tripartite meeting, some late), on hold, terminated, final report,
completed with certificate and feedback, and failed after resubmission.

## Workflow

```
Application → accepted → Placement
  Phase 1  form requested → documents under review ⇄ more documents / meeting → agreement in signing → approved
  Phase 2  active ⇄ on hold   (monthly records; escalation → tripartite meeting)   → terminated
  Phase 3  final report & closure → completed | failed
```

Full stage table, who does what and the automations: [docs/WORKFLOW.md](docs/WORKFLOW.md).

## Upgrading safely

Never upgrade the working database blind:

```sh
make upgrade           # backup → clone to internship_dev_upgrade_test → upgrade + test the clone
make upgrade-legacy    # same, but first seeds pre-v2 sample rows into the clone (tests migrations)
make upgrade-apply     # only after the above pass: upgrade internship_dev itself
```

Backups go to `backups/<db>_<timestamp>/` (database dump + filestore):
`make backup`, `make restore BACKUP=backups/<dir>`.

v1 → v2 data migration (idempotent; nothing is dropped):

1. Applications in *documentation / agreement / approved / placed* become placements in the
   matching stage (a student's extra open placements are archived, never lost).
2. Attendance, performance, meetings, submissions and completion records are linked to placements.
3. `internship.crm.lead` rows are copied into `crm.lead` (the legacy table stays, read-only).
4. v1 completion fields `final_report` and `evaluation_score` are hidden but kept.

## Tests and linting

```sh
make test                              # fresh throwaway DB with demo data (same as CI)
make test MODULE=internship_placement  # one module
make lint                              # ruff, ruff-format, pylint-odoo, XML/YAML checks
```

GitHub Actions (`.github/workflows/ci.yml`) runs lint and the full install + tests on every
push and pull request to `main` and `v2/**`.

## Voice AI (Vapi)

1. CRM › Configuration › **Voice Assistant** (the Voice Assistant block of the CRM settings): API key, webhook token, assistant IDs,
   phone number ID, calling window. Leave *Enabled* off until tested. The webhook and tool
   URLs to paste into Vapi are shown there, with *Test Connection* and *Generate New Token*.
2. In Vapi, set the server URL to `https://<host>/internship/call-tracking/webhook` and the
   tool URL to `https://<host>/internship/vapi/tool`, both with the header
   `Authorization: Bearer <webhook token>`.
3. Assistants, prompts, the structured-data schema, tool definitions and a test plan:
   [docs/vapi/ASSISTANT_SETUP.md](docs/vapi/ASSISTANT_SETUP.md).

Calls are only dialled inside the window (default Mon–Fri 09:00–20:00 UK time), never to
*Do Not Call* contacts, and marketing calls to companies need a TPS/CTPS check first.

## Before production

- Set `proxy_mode`, `list_db = False`, a single-database `dbfilter` and workers in
  `config/odoo.conf` (see the commented production block), and serve over HTTPS.
- Change the master password and every default credential in `.env`.
- Schedule `make backup` (or your own dump + filestore backup) and test a restore.
- Review group membership and record rules with real users for your tenancy model.
- Replace certificate and agreement wording with your institution's approved text.

Contributing, branching, commit style and the migration rules: [CONTRIBUTING.md](CONTRIBUTING.md).
