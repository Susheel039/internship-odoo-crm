from odoo import api, fields, models


class InternshipUniversityReview(models.Model):
    _inherit = "internship.university.review"

    meeting_id = fields.Many2one("internship.meeting", string="Meeting", index=True, ondelete="set null")

    @api.model_create_multi
    def create(self, vals_list):
        reviews = super().create(vals_list)
        for review in reviews.filtered(lambda r: not r.meeting_id):
            meeting = review.placement_id.meeting_ids.filtered(lambda m: m.meeting_type == "university_company").sorted(
                "meeting_date", reverse=True
            )[:1]
            review.meeting_id = meeting
        return reviews
