import importlib.util
import pathlib

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.internship_placement.tests.common import PlacementCommon


def _load_migration():
    path = pathlib.Path(__file__).parents[1] / "migrations" / "19.0.2.0.0" / "post-migrate.py"
    spec = importlib.util.spec_from_file_location("internship_completion_post_migrate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestCompletion(PlacementCommon):
    def _in_completion(self, student=None):
        placement = self._approved_placement(student)
        placement.action_start()
        placement.action_to_completion()
        return placement

    def _submit(self, attempt):
        attempt.write({"report_title": "What I learned"})
        attempt.action_submit()
        return attempt

    def test_completion_start_creates_attempt_and_checklist(self):
        placement = self._in_completion()
        self.assertEqual(placement.stage_code, "completion")
        attempt = placement.report_attempt_ids
        self.assertEqual(attempt.attempt_no, 1)
        self.assertTrue(attempt.due_date)
        self.assertEqual(placement.completion_id.status, "in_progress")
        self.assertFalse(placement.completion_id.all_checks_done)

    def test_fail_then_resubmission_then_final_fail(self):
        placement = self._in_completion()
        first = self._submit(placement.report_attempt_ids)
        first.action_mark_fail()
        self.assertEqual(first.status, "rejected")
        self.assertTrue(first.resubmission_allowed)
        second = first.next_attempt_id
        self.assertEqual(second.attempt_no, 2)
        self.assertEqual(second.status, "returned")
        self._submit(second).action_mark_fail()
        self.assertEqual(second.status, "failed")
        self.assertFalse(second.next_attempt_id, "max 2 attempts by default")
        self.assertEqual(placement.stage_code, "failed")
        self.assertEqual(placement.completion_id.final_result, "failed")
        self.assertEqual(self.student.lifecycle_status, "failed")

    def test_full_completion_closes_placement(self):
        placement = self._in_completion()
        checklist = placement.completion_id
        attempt = self._submit(placement.report_attempt_ids)
        attempt.action_load_rubric()
        self.assertTrue(attempt.rubric_score_ids)
        attempt.rubric_score_ids[0].score = 20
        attempt.write({"grade": "68 (2:1)"})
        attempt.action_mark_pass()
        self.assertTrue(checklist.chk_report_passed)
        with self.assertRaises(UserError):
            checklist.action_university_accept()

        evaluation = self.env["internship.company.evaluation"].create(
            {"placement_id": placement.id, "overall_rating": "4", "would_rehire": True}
        )
        evaluation.action_submit()
        self.assertEqual(evaluation.submitted_by_id, self.line_manager)

        certificate = self.env["internship.certificate"].create({"placement_id": placement.id})
        self.assertTrue(certificate.name.startswith("CERT-"))
        certificate.action_issue()
        self.assertTrue(certificate.attachment_id)

        self.env["internship.student.feedback"].create(
            {"placement_id": placement.id, "overall_rating": "5", "would_recommend": True}
        )
        self.assertEqual(self.company.avg_feedback_score, 5.0)
        self.assertTrue(checklist.all_checks_done)
        checklist.action_university_accept()
        self.assertEqual(checklist.status, "closed")
        self.assertEqual(checklist.final_result, "completed")
        self.assertEqual(placement.stage_code, "completed")
        self.assertTrue(placement.actual_end)
        self.assertEqual(self.student.lifecycle_status, "completed")

    def test_certificate_needs_authorised_issuer(self):
        placement = self._in_completion()
        self.line_manager.can_issue_certificate = False
        certificate = self.env["internship.certificate"].create({"placement_id": placement.id})
        with self.assertRaises(UserError):
            certificate.action_issue()

    def test_rubric_score_bounds(self):
        placement = self._in_completion()
        attempt = placement.report_attempt_ids
        attempt.action_load_rubric()
        with self.assertRaises(ValidationError):
            attempt.rubric_score_ids[0].score = 1000

    def test_migration_links_legacy_submission_and_completion(self):
        placement = self._approved_placement()
        Submission = self.env["internship.submission"]
        legacy = Submission.create({"student_id": self.student.id, "opportunity_id": self.opportunity.id})
        old = self.env["internship.completion"].create(
            {"student_id": self.student.id, "opportunity_id": self.opportunity.id}
        )
        new = self.env["internship.completion"].create(
            {"student_id": self.student.id, "opportunity_id": self.opportunity.id}
        )
        _load_migration().migrate(self.env.cr, "19.0.0.1.0")
        legacy.invalidate_recordset()
        (old | new).invalidate_recordset()
        self.assertEqual(legacy.placement_id, placement)
        self.assertEqual(new.placement_id, placement, "newest completion wins")
        self.assertFalse(old.placement_id)
