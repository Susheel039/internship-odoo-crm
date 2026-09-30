from odoo import fields, models
from odoo.exceptions import UserError

RATINGS = [("1", "1 - Poor"), ("2", "2 - Fair"), ("3", "3 - Good"), ("4", "4 - Very good"), ("5", "5 - Excellent")]


class InternshipCompanyEvaluation(models.Model):
    _name = "internship.company.evaluation"
    _description = "Company Evaluation of the Student"
    _inherit = ["mail.thread", "internship.placement.link.mixin"]
    _order = "submitted_date desc, id desc"

    overall_rating = fields.Selection(RATINGS, required=True, tracking=True)
    final_feedback = fields.Text()
    skills_gained = fields.Text()
    would_rehire = fields.Boolean(tracking=True)
    submitted_by_id = fields.Many2one("internship.line.manager", string="Submitted By", tracking=True)
    submitted_date = fields.Date(readonly=True, copy=False, tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted")], default="draft", required=True, tracking=True, index=True
    )

    def action_submit(self):
        for evaluation in self:
            if evaluation.state != "draft":
                raise UserError(self.env._("This evaluation has already been submitted."))
            if not evaluation.submitted_by_id:
                evaluation.submitted_by_id = evaluation.placement_id.line_manager_id
        self.write({"state": "submitted", "submitted_date": fields.Date.context_today(self)})
        return True
