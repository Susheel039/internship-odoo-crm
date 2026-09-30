from odoo import models


class InternshipPlacementLinkMixin(models.AbstractModel):
    """Link a workflow record to its placement.

    Declared here with the other shared mixins. Its fields (`placement_id` and the stored
    related `student_id`, `internship_company_id`, `university_id`, `program_id`) are added
    by internship_placement, the module that defines `internship.placement`.
    """

    _name = "internship.placement.link.mixin"
    _description = "Internship Placement Link Mixin"
