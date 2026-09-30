from odoo import fields, models


class InternshipCallLog(models.Model):
    """v2 call statuses, added without touching the v1 keys."""

    _inherit = "internship.call.log"

    status = fields.Selection(
        selection_add=[
            ("queued", "Queued"),
            ("ringing", "Ringing"),
            ("no_answer", "No answer"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        ondelete={
            "queued": "set default",
            "ringing": "set default",
            "no_answer": "set default",
            "failed": "set default",
            "cancelled": "set default",
        },
    )
