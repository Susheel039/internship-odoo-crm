from odoo import fields, models


class InternshipPerformance(models.Model):
    _name = "internship.performance"
    _description = "Internship Performance"
    _order = "review_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Performance Review", required=True, default="New")
    student_id = fields.Many2one(
        "internship.student",
        string="Student",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    opportunity_id = fields.Many2one(
        "internship.opportunity",
        string="Opportunity",
        ondelete="restrict",
        tracking=True,
    )
    review_date = fields.Date(string="Review Date", default=fields.Date.context_today)
    period_start = fields.Date(string="Period Start")
    period_end = fields.Date(string="Period End")
    score = fields.Float(string="Score", digits=(3, 1))
    supervisor_id = fields.Many2one(
        "res.partner",
        string="Supervisor",
        ondelete="set null",
        tracking=True,
    )
    status = fields.Selection(
        [
            ("needs_improvement", "Needs Improvement"),
            ("satisfactory", "Satisfactory"),
            ("good", "Good"),
            ("excellent", "Excellent"),
        ],
        string="Status",
        default="satisfactory",
        tracking=True,
    )
    comments = fields.Text(string="Comments")
    active = fields.Boolean(default=True, tracking=True)

    # v2
    placement_id = fields.Many2one("internship.placement", index=True, ondelete="set null", tracking=True)
    review_kind = fields.Selection(
        [("mid_term", "Mid-term review"), ("final", "Final review"), ("ad_hoc", "Ad hoc")],
        default="ad_hoc",
        tracking=True,
    )

    def action_set_satisfactory(self):
        return self.write({"status": "satisfactory"})

    def action_set_good(self):
        return self.write({"status": "good"})

    def action_set_excellent(self):
        return self.write({"status": "excellent"})

    def action_set_needs_improvement(self):
        return self.write({"status": "needs_improvement"})
