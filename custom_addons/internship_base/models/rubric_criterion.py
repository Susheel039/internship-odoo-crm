from odoo import fields, models


class InternshipRubricCriterion(models.Model):
    _name = "internship.rubric.criterion"
    _description = "Marking Rubric Criterion"
    _inherit = ["internship.lookup.mixin"]

    max_score = fields.Float(default=10.0, required=True)
    program_id = fields.Many2one(
        "internship.program",
        string="Program",
        index=True,
        ondelete="cascade",
        help="Leave empty for a criterion shared by every programme.",
    )

    _max_score_positive = models.Constraint("CHECK(max_score > 0)", "The maximum score must be positive.")
