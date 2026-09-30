# Internship CRM

Custom Odoo 19 Community add-ons for internship admissions, CRM, monitoring,
completion, call tracking, and management reporting. Odoo core is not modified.

## Run locally

```sh
make up            # creates .env and config/odoo.conf from the examples, starts Docker
make init DEMO=1   # new database internship_dev with all modules (+ UK demo data)
```

Open <http://localhost:8069> and sign in as `admin` / `admin`, then change the
password. `make help` lists every shortcut.

Database credentials live only in `.env` (gitignored); `config/odoo.conf` is
also gitignored and created from `config/odoo.conf.example`. The defaults are
for development only. PostgreSQL is published on `127.0.0.1:5432` only.

## Included add-ons

- `internship_base`: universities, students, companies, programs, opportunities,
	applications, access groups, and the application-to-placement workflow.
- `internship_crm`: internship lead pipeline, linked CRM leads, and stage kanban.
- `internship_monitoring`: attendance, meetings, and performance reviews.
- `internship_completion`: submissions with document upload, final evaluation,
	approval, and printable PDF certificates.
- `internship_vapi`: call log records and an authenticated Vapi end-of-call
	webhook receiver.
- `internship_reporting`: live KPI snapshots and native application/completion
	graph and pivot analysis.

## Update and test

Never upgrade the working database blind. `make upgrade` backs it up into
`backups/`, clones it to `internship_dev_upgrade_test`, upgrades and tests the
clone, and leaves `internship_dev` untouched:

```sh
make upgrade           # safe: clone only
make upgrade-apply     # after the above passes: upgrade internship_dev too
```

Run the test suite on a fresh throwaway database with demo data (as CI does):

```sh
make test                              # all modules
make test MODULE=internship_reporting  # one module
```

Backups: `make backup`, `make restore BACKUP=backups/<dir>`. Lint: `make lint`.
See [CONTRIBUTING.md](CONTRIBUTING.md) for branching, commits and migration rules.

## Vapi webhook setup

Set a long random token as the Odoo system parameter
`internship_vapi.webhook_token` using Settings > Technical > System Parameters.
Configure the Vapi server URL as:

`https://<your-public-odoo-host>/internship/call-tracking/webhook`

The endpoint expects `Authorization: Bearer <token>` and Vapi's
`end-of-call-report` event. Include Odoo database IDs as `student_id` and
`opportunity_id` in the call metadata to link imported calls. Repeated call IDs
update the existing call record instead of creating duplicates. The endpoint
requires HTTPS and a configured token in any non-local deployment. Outbound
call initiation and provider credentials are not included; those require a
Vapi account and deployment-specific credentials.

## Operational follow-up

Before production use, replace local credentials, configure HTTPS and backups,
define record-level university/company rules for your tenancy model, validate
role access with real users, and complete user acceptance testing with your
internship policies and certificate branding.
