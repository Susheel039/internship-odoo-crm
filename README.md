# INTERNTION CRM

Custom Odoo 19 Community add-ons for internship admissions, CRM, monitoring,
completion, call tracking, and management reporting. Odoo core is not modified.

## Run locally

1. Copy `.env.example` to `.env` and set local database credentials.
2. Start the stack with `docker compose up -d`.
3. Open <http://localhost:8069> and sign in with the administrator account
	 configured when the database was created.
4. Install or upgrade the add-ons from Apps, or run the update command below.

The local defaults in `.env.example` are for development only. Change them
before exposing this stack outside your machine.

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

Upgrade all installed custom modules:

```sh
docker exec internship_odoo odoo --config /etc/odoo/odoo.conf \
	--database internship_dev --stop-after-init \
	-u internship_base,internship_crm,internship_monitoring,internship_completion,internship_vapi,internship_reporting
```

Run the reporting/lifecycle regression test on an unused HTTP port:

```sh
docker exec internship_odoo odoo --config /etc/odoo/odoo.conf \
	--http-port=8070 --database internship_dev --stop-after-init \
	--test-enable --test-tags /internship_reporting -u internship_reporting
```

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
