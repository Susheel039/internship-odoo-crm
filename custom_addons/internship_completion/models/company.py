from odoo import api, fields, models


class InternshipCompany(models.Model):
    _inherit = "internship.company"

    feedback_ids = fields.One2many("internship.student.feedback", "internship_company_id", string="Student Feedback")
    avg_feedback_score = fields.Float(
        string="Average Student Rating", compute="_compute_avg_feedback_score", store=True, digits=(3, 2)
    )

    @api.depends("feedback_ids.overall_rating")
    def _compute_avg_feedback_score(self):
        for company in self:
            ratings = [int(r) for r in company.feedback_ids.mapped("overall_rating") if r]
            company.avg_feedback_score = sum(ratings) / len(ratings) if ratings else 0.0
