from odoo import fields, models


class InternshipPlacementLinkMixin(models.AbstractModel):
    """Fields of the placement link mixin declared in internship_base."""

    _inherit = "internship.placement.link.mixin"

    placement_id = fields.Many2one(
        "internship.placement", string="Placement", required=True, index=True, ondelete="cascade"
    )
    student_id = fields.Many2one(related="placement_id.student_id", store=True, index=True, string="Student")
    internship_company_id = fields.Many2one(
        related="placement_id.internship_company_id", store=True, index=True, string="Internship Company"
    )
    university_id = fields.Many2one(related="placement_id.university_id", store=True, index=True, string="University")
    program_id = fields.Many2one(related="placement_id.program_id", store=True, index=True, string="Program")
