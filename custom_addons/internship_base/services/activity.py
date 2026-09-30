"""Idempotent activity scheduling shared by every internship module (crons call these daily)."""

from odoo import fields


def schedule_activity_once(
    record, user, summary, note=None, deadline=None, act_type_xmlid="mail.mail_activity_data_todo"
):
    """Schedule a to-do on `record` for `user` unless an open one with the same summary exists.

    Returns the new activity, or an empty recordset when nothing was scheduled.
    """
    Activity = record.env["mail.activity"]
    if not record or not user:
        return Activity
    record.ensure_one()
    existing = Activity.sudo().search_count(
        [
            ("res_model", "=", record._name),
            ("res_id", "=", record.id),
            ("user_id", "=", user.id),
            ("summary", "=", summary),
        ],
        limit=1,
    )
    if existing:
        return Activity
    return record.sudo().activity_schedule(
        act_type_xmlid,
        date_deadline=deadline or fields.Date.context_today(record),
        summary=summary,
        note=note or "",
        user_id=user.id,
    )


def default_coordinator(env):
    """Fallback owner of automated to-dos when a record has no responsible user."""
    return env.ref("base.user_admin", raise_if_not_found=False) or env.user
