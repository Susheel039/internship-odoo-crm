from odoo import fields, models


class InternshipPlacementLinkMixin(models.AbstractModel):
    """Link a workflow record to its placement, with the usual denormalised keys for search and rules.

    Lives here rather than in internship_base because it points at internship.placement.
    """

    _name = "internship.placement.link.mixin"
    _description = "Internship Placement Link Mixin"

    placement_id = fields.Many2one(
        "internship.placement", string="Placement", required=True, index=True, ondelete="cascade"
    )
    student_id = fields.Many2one(related="placement_id.student_id", store=True, index=True, string="Student")
    internship_company_id = fields.Many2one(
        related="placement_id.internship_company_id", store=True, index=True, string="Company"
    )
    university_id = fields.Many2one(related="placement_id.university_id", store=True, index=True, string="University")
    program_id = fields.Many2one(related="placement_id.program_id", store=True, index=True, string="Programme")
