from datetime import timedelta

from odoo import api, fields, models

FILLED_STAGES = ("approved", "active", "on_hold", "completion", "completed")


class InternshipReport(models.Model):
    """Live KPI snapshot. Numbers are computed on read from placements, applications and calls."""

    _name = "internship.report"
    _description = "Internship KPI Report"
    _order = "report_date desc, name"

    name = fields.Char(string="Report Name", required=True, default="Internship KPI Snapshot")
    report_date = fields.Date(default=fields.Date.context_today)
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")
    university_id = fields.Many2one("internship.university", string="University")
    company_id = fields.Many2one("internship.company", string="Company")
    program_id = fields.Many2one("internship.program", string="Programme")
    notes = fields.Text(string="Notes")

    total_students = fields.Integer(string="Students", compute="_compute_kpis")
    total_opportunities = fields.Integer(string="Opportunities", compute="_compute_kpis")
    total_applications = fields.Integer(string="Applications", compute="_compute_kpis")
    total_placed = fields.Integer(string="Placed", compute="_compute_kpis", help="Placements approved or later.")
    total_completed = fields.Integer(string="Completed", compute="_compute_kpis")
    total_failed = fields.Integer(string="Failed", compute="_compute_kpis")
    placement_rate = fields.Float(string="Placement Rate (%)", compute="_compute_kpis", digits=(5, 2))
    completion_rate = fields.Float(string="Completion Rate (%)", compute="_compute_kpis", digits=(5, 2))
    failed_rate = fields.Float(string="Failed Rate (%)", compute="_compute_kpis", digits=(5, 2))
    placements_phase_1 = fields.Integer(string="In Admission", compute="_compute_kpis")
    placements_phase_2 = fields.Integer(string="In Monitoring", compute="_compute_kpis")
    placements_phase_3 = fields.Integer(string="In Completion", compute="_compute_kpis")
    late_monthly = fields.Integer(string="Late Monthly Records", compute="_compute_kpis")
    red_risk = fields.Integer(string="Red-risk Placements", compute="_compute_kpis")
    avg_company_feedback = fields.Float(
        string="Avg. Company Rating by Students", compute="_compute_kpis", digits=(3, 2)
    )
    total_calls = fields.Integer(string="AI Calls", compute="_compute_kpis")
    leads_from_calls = fields.Integer(string="Leads from Calls", compute="_compute_kpis")
    students_from_calls = fields.Integer(string="Students Converted from Calls", compute="_compute_kpis")

    def _date_domain(self, field_name, is_datetime=False):
        domain = []
        if self.date_from:
            domain.append(
                (field_name, ">=", fields.Datetime.to_datetime(self.date_from) if is_datetime else self.date_from)
            )
        if self.date_to:
            end = self.date_to + timedelta(days=1)
            domain.append((field_name, "<", fields.Datetime.to_datetime(end) if is_datetime else end))
        return domain

    @api.depends("date_from", "date_to", "university_id", "company_id", "program_id")
    def _compute_kpis(self):
        for report in self:
            student_domain, opportunity_domain, application_domain, placement_domain = [], [], [], []
            if report.university_id:
                student_domain.append(("university_id", "=", report.university_id.id))
                application_domain.append(("university_id", "=", report.university_id.id))
                opportunity_domain.append(("program_id.university_id", "=", report.university_id.id))
                placement_domain.append(("university_id", "=", report.university_id.id))
            if report.company_id:
                opportunity_domain.append(("company_id", "=", report.company_id.id))
                application_domain.append(("company_id", "=", report.company_id.id))
                placement_domain.append(("internship_company_id", "=", report.company_id.id))
            if report.program_id:
                opportunity_domain.append(("program_id", "=", report.program_id.id))
                application_domain.append(("opportunity_id.program_id", "=", report.program_id.id))
                placement_domain.append(("program_id", "=", report.program_id.id))
            if report.company_id or report.program_id:
                matching = self.env["internship.application"].search(application_domain).student_id.ids
                student_domain.append(("id", "in", matching))

            student_domain += report._date_domain("create_date", True)
            opportunity_domain += report._date_domain("start_date")
            application_domain += report._date_domain("application_date")
            placement_domain += report._date_domain("create_date", True)

            Placement = self.env["internship.placement"].with_context(active_test=False)
            placements = Placement.search(placement_domain + [("active", "=", True)])
            report.total_students = self.env["internship.student"].search_count(student_domain)
            report.total_opportunities = self.env["internship.opportunity"].search_count(opportunity_domain)
            report.total_applications = self.env["internship.application"].search_count(application_domain)
            report.total_placed = len(placements.filtered(lambda p: p.stage_code in FILLED_STAGES))
            report.total_completed = len(placements.filtered(lambda p: p.stage_code == "completed"))
            report.total_failed = len(placements.filtered(lambda p: p.stage_code == "failed"))
            report.placements_phase_1 = len(placements.filtered(lambda p: p.phase == "1" and not p.is_closed))
            report.placements_phase_2 = len(placements.filtered(lambda p: p.phase == "2" and not p.is_closed))
            report.placements_phase_3 = len(placements.filtered(lambda p: p.phase == "3" and not p.is_closed))
            report.red_risk = len(placements.filtered(lambda p: p.risk_flag == "red"))
            report.late_monthly = self.env["internship.attendance.monthly"].search_count(
                [("placement_id", "in", placements.ids), ("state", "=", "late")]
            )
            finished = report.total_completed + report.total_failed
            report.placement_rate = (
                100.0 * report.total_placed / report.total_applications if report.total_applications else 0.0
            )
            report.completion_rate = (
                100.0 * report.total_completed / report.total_placed if report.total_placed else 0.0
            )
            report.failed_rate = 100.0 * report.total_failed / finished if finished else 0.0

            feedback = self.env["internship.student.feedback"].search([("placement_id", "in", placements.ids)])
            ratings = [int(r) for r in feedback.mapped("overall_rating") if r]
            report.avg_company_feedback = sum(ratings) / len(ratings) if ratings else 0.0

            call_domain = report._date_domain("call_datetime", True)
            # Aggregate counts only: staff without CRM access still see the totals.
            calls = self.env["internship.call.log"].sudo().search(call_domain)
            call_leads = calls.lead_id | self.env["crm.lead"].sudo().with_context(active_test=False).search(
                [("source_channel", "in", ("vapi_inbound", "vapi_outbound"))] + report._date_domain("create_date", True)
            )
            report.total_calls = len(calls)
            report.leads_from_calls = len(call_leads)
            report.students_from_calls = len(call_leads.filtered("student_id"))

    @api.model
    def action_open_dashboard(self):
        """Dashboard: the all-time live snapshot (created on first use)."""
        report = self.env.ref("internship_reporting.report_live_dashboard", raise_if_not_found=False)
        if not report:
            report = self.create({"name": self.env._("Live dashboard")})
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Dashboard"),
            "res_model": self._name,
            "res_id": report.id,
            "view_mode": "form",
            "target": "current",
        }
