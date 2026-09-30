from odoo import models

from .placement import FILLED_STAGES


class InternshipOpportunity(models.Model):
    _inherit = "internship.opportunity"

    def _compute_positions_filled(self):
        """Approved, running or completed placements count as filled positions."""
        counts = dict(
            self.env["internship.placement"]._read_group(
                [("opportunity_id", "in", self.ids), ("stage_code", "in", FILLED_STAGES)],
                ["opportunity_id"],
                ["__count"],
            )
        )
        for opportunity in self:
            opportunity.positions_filled = counts.get(opportunity, 0)
