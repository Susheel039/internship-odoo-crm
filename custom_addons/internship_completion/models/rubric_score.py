from odoo import api, fields, models
from odoo.exceptions import ValidationError


class InternshipRubricScore(models.Model):
    _name = "internship.rubric.score"
    _description = "Rubric Score"
    _order = "submission_id, id"

    submission_id = fields.Many2one("internship.submission", required=True, index=True, ondelete="cascade")
    criterion_id = fields.Many2one("internship.rubric.criterion", required=True, ondelete="restrict")
    max_score = fields.Float(related="criterion_id.max_score")
    score = fields.Float()
    comment = fields.Text()

    _unique_criterion = models.Constraint(
        "unique(submission_id, criterion_id)", "Each criterion is scored once per report attempt."
    )

    @api.constrains("score", "criterion_id")
    def _check_score(self):
        for line in self:
            if line.score < 0 or line.score > line.criterion_id.max_score:
                raise ValidationError(
                    self.env._(
                        "%(criterion)s must be scored between 0 and %(max)s.",
                        criterion=line.criterion_id.name,
                        max=line.criterion_id.max_score,
                    )
                )
