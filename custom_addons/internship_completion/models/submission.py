from odoo import fields, models


class InternshipSubmission(models.Model):
    _name = "internship.submission"
    _description = "Internship Submission"
    _order = "submitted_date desc, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Submission Reference", required=True, default="New")
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
    company_id = fields.Many2one(
        "internship.company",
        string="Company",
        related="opportunity_id.company_id",
        store=True,
        readonly=True,
    )
    title = fields.Char(string="Title")
    due_date = fields.Date(string="Due Date")
    submitted_date = fields.Date(string="Submitted Date", default=fields.Date.context_today)
    document = fields.Binary(string="Submitted Document", attachment=True)
    document_filename = fields.Char(string="Document Filename")
    document_url = fields.Char(string="Document URL")
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("returned", "Returned"),
            ("completed", "Completed"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    evaluation_score = fields.Float(string="Evaluation Score", digits=(3, 1))
    supervisor_feedback = fields.Text(string="Supervisor Feedback")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True, tracking=True)

    def action_submit(self):
        return self.write({"status": "submitted", "submitted_date": fields.Date.context_today(self)})

    def action_review(self):
        return self.write({"status": "under_review"})

    def action_approve(self):
        return self.write({"status": "approved"})

    def action_reject(self):
        return self.write({"status": "rejected"})

    def action_complete(self):
        return self.write({"status": "completed"})
