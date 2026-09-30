from datetime import timedelta

from odoo import api, fields, models


class InternshipReport(models.Model):
    _name = "internship.report"
    _description = "Internship KPI Report"
    _order = "report_date desc, name"

    name = fields.Char(string="Report Name", required=True, default="Internship KPI Snapshot")
    date_from = fields.Date(string="From")
    date_to = fields.Date(string="To")
    university_id = fields.Many2one("internship.university", string="University")
    company_id = fields.Many2one("internship.company", string="Company")
    program_id = fields.Many2one("internship.program", string="Program")
    total_students = fields.Integer(string="Students", compute="_compute_kpis")
    total_opportunities = fields.Integer(string="Opportunities", compute="_compute_kpis")
    total_applications = fields.Integer(string="Applications", compute="_compute_kpis")
    total_placed = fields.Integer(string="Placed", compute="_compute_kpis")
    total_completed = fields.Integer(string="Completed", compute="_compute_kpis")
    placement_rate = fields.Float(string="Placement Rate (%)", compute="_compute_kpis", digits=(5, 2))
    completion_rate = fields.Float(string="Completion Rate (%)", compute="_compute_kpis", digits=(5, 2))
    notes = fields.Text(string="Notes")

    @api.depends("date_from", "date_to", "university_id", "company_id", "program_id")
    def _compute_kpis(self):
        for report in self:
            student_domain = []
            opportunity_domain = []
            application_domain = []
            completion_domain = []

            if report.university_id:
                student_domain.append(("university_id", "=", report.university_id.id))
                application_domain.append(("university_id", "=", report.university_id.id))
                completion_domain.append(("student_id.university_id", "=", report.university_id.id))
                opportunity_domain.append(("program_id.university_id", "=", report.university_id.id))
            if report.company_id:
                opportunity_domain.append(("company_id", "=", report.company_id.id))
                application_domain.append(("company_id", "=", report.company_id.id))
                completion_domain.append(("company_id", "=", report.company_id.id))
            if report.program_id:
                opportunity_domain.append(("program_id", "=", report.program_id.id))
                application_domain.append(("opportunity_id.program_id", "=", report.program_id.id))
                completion_domain.append(("opportunity_id.program_id", "=", report.program_id.id))
            if report.company_id or report.program_id:
                applications = self.env["internship.application"].search(application_domain)
                matching_student_ids = applications.mapped("student_id").ids
                student_domain.append(("id", "in", matching_student_ids))

            ranges = (
                (student_domain, "create_date", True),
                (opportunity_domain, "start_date", False),
                (application_domain, "application_date", False),
                (completion_domain, "completion_date", False),
            )
            for domain, date_field, is_datetime in ranges:
                if report.date_from:
                    start = fields.Datetime.to_datetime(report.date_from) if is_datetime else report.date_from
                    domain.append((date_field, ">=", start))
                if report.date_to:
                    end_date = report.date_to + timedelta(days=1)
                    end = fields.Datetime.to_datetime(end_date) if is_datetime else end_date
                    domain.append((date_field, "<", end))

            report.total_students = self.env["internship.student"].search_count(student_domain)
            report.total_opportunities = self.env["internship.opportunity"].search_count(opportunity_domain)
            report.total_applications = self.env["internship.application"].search_count(application_domain)
            report.total_placed = self.env["internship.application"].search_count(
                application_domain + [("status", "=", "accepted")]
            )
            report.total_completed = self.env["internship.completion"].search_count(
                completion_domain + [("status", "in", ["approved", "closed"])]
            )
            report.placement_rate = (
                100.0 * report.total_placed / report.total_applications if report.total_applications else 0.0
            )
            report.completion_rate = (
                100.0 * report.total_completed / report.total_placed if report.total_placed else 0.0
            )
