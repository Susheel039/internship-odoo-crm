from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.internship_placement.tests.common import PlacementCommon


@tagged("post_install", "-at_install")
class TestInternshipReporting(PlacementCommon):
    """KPIs follow the v2 lifecycle: applications -> placements -> completion."""

    def _report(self):
        return self.env["internship.report"].create(
            {
                "name": "KPI Test Snapshot",
                "university_id": self.university.id,
                "company_id": self.company.id,
                "program_id": self.program.id,
            }
        )

    def test_lifecycle_updates_live_kpis(self):
        application = self._new_application()
        with self.assertRaises(UserError):
            application.action_review()
        self._offer(application)
        application.action_student_accept()
        placement = application.placement_id
        self._new_application(status="submitted")
        report = self._report()
        self.assertEqual(report.total_applications, 2)
        self.assertEqual(report.total_placed, 0, "not placed until approved")
        self.assertEqual(report.placements_phase_1, 1)

        self._submit_form(placement)
        self._review(placement, "approve")
        placement._mark_agreement_complete()
        placement.action_start()
        report = self._report()
        self.assertEqual(report.total_students, 1)
        self.assertEqual(report.total_opportunities, 1)
        self.assertEqual(report.total_placed, 1)
        self.assertEqual(report.placement_rate, 50.0)
        self.assertEqual(report.placements_phase_2, 1)

        placement.action_to_completion()
        attempt = placement.report_attempt_ids
        attempt.action_submit()
        attempt.action_mark_pass()
        self.env["internship.company.evaluation"].create(
            {"placement_id": placement.id, "overall_rating": "5"}
        ).action_submit()
        self.env["internship.certificate"].create({"placement_id": placement.id}).action_issue()
        self.env["internship.student.feedback"].create({"placement_id": placement.id, "overall_rating": "4"})
        placement.completion_id.action_university_accept()

        report = self._report()
        self.assertEqual(report.total_completed, 1)
        self.assertEqual(report.completion_rate, 100.0)
        self.assertEqual(report.failed_rate, 0.0)
        self.assertEqual(report.avg_company_feedback, 4.0)

    def test_dashboard_and_legacy_certificate(self):
        action = self.env["internship.report"].action_open_dashboard()
        self.assertEqual(action["res_model"], "internship.report")
        completion = self.env["internship.completion"].create(
            {
                "name": "V1 completion",
                "student_id": self.student.id,
                "opportunity_id": self.opportunity.id,
                "start_date": self.today,
                "end_date": self.today,
                "final_report": "Completed the assigned project and handover.",
                "evaluation_score": 92,
            }
        )
        completion.action_start()
        completion.action_complete()
        completion.action_approve()
        self.assertTrue(completion.certificate_issued)
        self.assertEqual(completion.approved_by, self.env.user)
        self.assertTrue(completion.action_print_certificate())
