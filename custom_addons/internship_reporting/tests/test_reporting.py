from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInternshipReporting(TransactionCase):
    def test_lifecycle_updates_live_kpis_and_certificate_action(self):
        partner = self.env["res.partner"].create({"name": "KPI Test Company"})
        university_partner = self.env["res.partner"].create({"name": "KPI Test University"})
        university = self.env["internship.university"].create(
            {
                "name": "KPI Test University",
                "partner_id": university_partner.id,
            }
        )
        student = self.env["internship.student"].create(
            {
                "name": "KPI Test Student",
                "partner_id": partner.id,
                "university_id": university.id,
            }
        )
        company = self.env["internship.company"].create(
            {
                "name": "KPI Test Company",
                "partner_id": partner.id,
            }
        )
        today = fields.Date.context_today(self)
        program = self.env["internship.program"].create(
            {
                "name": "KPI Test Program",
                "university_id": university.id,
                "start_date": today,
                "end_date": today,
            }
        )
        opportunity = self.env["internship.opportunity"].create(
            {
                "name": "KPI Test Opportunity",
                "company_id": company.id,
                "program_id": program.id,
                "start_date": today,
                "end_date": today,
            }
        )
        application = self.env["internship.application"].create(
            {
                "name": "KPI-APP-PLACED",
                "student_id": student.id,
                "opportunity_id": opportunity.id,
            }
        )
        with self.assertRaises(UserError):
            application.action_review()

        application.action_submit()
        application.action_review()
        application.action_interview()
        application.action_offer()
        application.action_accept()
        application.action_documentation()
        application.action_agreement()
        application.action_approve()
        application.action_place()

        self.env["internship.application"].create(
            {
                "name": "KPI-APP-SUBMITTED",
                "student_id": student.id,
                "opportunity_id": opportunity.id,
                "status": "submitted",
            }
        )
        completion = self.env["internship.completion"].create(
            {
                "name": "KPI-COMPLETION",
                "student_id": student.id,
                "opportunity_id": opportunity.id,
                "start_date": today,
                "end_date": today,
                "final_report": "Completed the assigned project and handover.",
                "evaluation_score": 92,
            }
        )
        completion.action_start()
        completion.action_complete()
        completion.action_approve()

        report = self.env["internship.report"].create(
            {
                "name": "KPI Test Snapshot",
                "date_from": today,
                "date_to": today,
                "university_id": university.id,
                "company_id": company.id,
                "program_id": program.id,
            }
        )
        self.assertEqual(report.total_students, 1)
        self.assertEqual(report.total_opportunities, 1)
        self.assertEqual(report.total_applications, 2)
        self.assertEqual(report.total_placed, 1)
        self.assertEqual(report.total_completed, 1)
        self.assertEqual(report.placement_rate, 50.0)
        self.assertEqual(report.completion_rate, 100.0)
        self.assertTrue(completion.certificate_issued)
        self.assertEqual(completion.approved_by, self.env.user)
        self.assertTrue(completion.action_print_certificate())
