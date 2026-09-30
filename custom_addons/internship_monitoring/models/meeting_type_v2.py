from odoo import fields, models


class InternshipMeeting(models.Model):
    """v2 meeting types, added without touching the v1 keys."""

    _inherit = "internship.meeting"

    meeting_type = fields.Selection(
        selection_add=[
            ("interview", "Interview"),
            ("university_company", "University-company meeting"),
            ("tripartite", "Tripartite meeting"),
            ("exit", "Exit meeting"),
        ],
        ondelete={
            "interview": "set default",
            "university_company": "set default",
            "tripartite": "set default",
            "exit": "set default",
        },
    )
