from odoo import fields, models

from .company_evaluation import RATINGS


class InternshipStudentFeedback(models.Model):
    _name = "internship.student.feedback"
    _description = "Student Feedback on the Placement"
    _inherit = ["internship.placement.link.mixin"]
    _order = "create_date desc"

    overall_rating = fields.Selection(RATINGS, required=True)
    learning_quality = fields.Selection(RATINGS)
    supervision_quality = fields.Selection(RATINGS)
    would_recommend = fields.Boolean()
    comments = fields.Text()
    anonymous_to_company = fields.Boolean(
        default=True, help="Hide the student's name when the company views this feedback."
    )
