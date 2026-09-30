from odoo import api, fields, models


class InternshipCRMLead(models.Model):
    """DEPRECATED since 19.0.2: replaced by crm.lead (see internship_crm migrations).

    Kept read-only for one release so no data is lost; the table is never dropped here.
    """

    _name = "internship.crm.lead"
    _description = "Internship CRM Lead (legacy)"
    _order = "priority desc, expected_start_date, name"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Lead Name", required=True, tracking=True)
    student_id = fields.Many2one(
        "internship.student",
        string="Student",
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
    university_id = fields.Many2one(
        "internship.university",
        string="University",
        related="student_id.university_id",
        store=True,
        readonly=True,
    )
    crm_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead",
        ondelete="set null",
        tracking=True,
    )
    lead_source = fields.Selection(
        [
            ("referral", "Referral"),
            ("university", "University"),
            ("company", "Company"),
            ("portal", "Portal"),
            ("campus", "Campus Event"),
            ("other", "Other"),
        ],
        string="Lead Source",
        default="portal",
        tracking=True,
    )
    stage = fields.Selection(
        [
            ("new", "New"),
            ("contacted", "Contacted"),
            ("qualified", "Qualified"),
            ("proposal", "Proposal"),
            ("interview", "Interview"),
            ("accepted", "Accepted"),
            ("closed", "Closed"),
        ],
        string="Stage",
        default="new",
        tracking=True,
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Very High")],
        string="Priority",
        default="0",
        tracking=True,
    )
    expected_start_date = fields.Date(string="Expected Start Date")
    notes = fields.Text(string="Notes")
    active = fields.Boolean(default=True, tracking=True)
    crm_lead_ids = fields.One2many("crm.lead", "legacy_internship_lead_id", string="Migrated To")

    @api.onchange("student_id")
    def _onchange_student_id(self):
        if self.student_id:
            self.university_id = self.student_id.university_id

    @api.onchange("opportunity_id")
    def _onchange_opportunity_id(self):
        if self.opportunity_id:
            self.company_id = self.opportunity_id.company_id

    def action_contact(self):
        return self.write({"stage": "contacted"})

    def action_qualify(self):
        return self.write({"stage": "qualified"})

    def action_proposal(self):
        return self.write({"stage": "proposal"})

    def action_interview(self):
        return self.write({"stage": "interview"})

    def action_accept(self):
        return self.write({"stage": "accepted"})

    def action_close(self):
        return self.write({"stage": "closed"})
