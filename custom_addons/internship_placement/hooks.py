"""Install hook: turn pre-v2 application lifecycle rows into placements (migration step 2).

internship_base's 19.0.2.0.0 pre-migration stored the legacy status of every application
that was in documentation / agreement / approved / placed in the temp table
_v2_app_lifecycle. This module is new in v2, so its install hook (not a migration script)
creates the placements. Idempotent: applications that already have a placement are skipped
and the temp table is dropped once processed.
"""

import logging

_logger = logging.getLogger(__name__)

LEGACY_STAGE_MAP = {
    "documentation": "under_review",
    "agreement": "agreement",
    "approved": "approved",
    "placed": "active",
}


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
    return bool(cr.fetchone())


def migrate_legacy_lifecycle(env):
    cr = env.cr
    if not _table_exists(cr, "_v2_app_lifecycle"):
        return 0
    cr.execute("SELECT application_id, old_status FROM _v2_app_lifecycle ORDER BY application_id")
    rows = cr.fetchall()
    Placement = env["internship.placement"].with_context(tracking_disable=True, mail_create_nolog=True)
    Stage = env["internship.placement.stage"]
    created = archived = skipped = 0
    for application_id, old_status in rows:
        application = env["internship.application"].browse(application_id).exists()
        if not application or application.placement_id or not application.opportunity_id:
            skipped += 1
            continue
        values = Placement._prepare_from_application(application)
        values["stage_id"] = Stage._get_by_code(LEGACY_STAGE_MAP.get(old_status, "under_review")).id
        if old_status == "placed":
            values["actual_start"] = application.opportunity_id.start_date or application.application_date
        # One open placement per student: keep extra legacy placements, archived, for review.
        clash = Placement.search_count(
            [("student_id", "=", application.student_id.id), ("is_closed", "=", False), ("active", "=", True)]
        )
        if clash:
            values["active"] = False
            archived += 1
        placement = Placement.create(values)
        application.placement_id = placement
        placement.message_post(
            body=env._(
                "Migrated from v1: application %(app)s was '%(status)s'.", app=application.name, status=old_status
            )
        )
        created += 1
    cr.execute("DROP TABLE _v2_app_lifecycle")
    _logger.info(
        "internship_placement: created %s placements from legacy applications (%s archived as duplicates, %s skipped)",
        created,
        archived,
        skipped,
    )
    return created


def post_init_hook(env):
    migrate_legacy_lifecycle(env)
