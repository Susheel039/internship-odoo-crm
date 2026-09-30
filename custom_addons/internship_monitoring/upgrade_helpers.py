"""Upgrade helpers for internship_monitoring (called from migrations/ and from tests)."""

from odoo.addons.internship_placement.upgrade_helpers import column_exists, link_to_placements

TABLES = ("internship_attendance", "internship_performance", "internship_meeting")

__all__ = ["TABLES", "column_exists", "link_to_placements"]
