from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..hooks import migrate_legacy_lifecycle
from .common import PlacementCommon


@tagged("post_install", "-at_install")
class TestPlacement(PlacementCommon):
    def test_accept_creates_placement_and_requests_form(self):
        placement = self._accepted_placement()
        self.assertTrue(placement.name.startswith("INT-"))
        self.assertEqual(placement.stage_code, "form_requested")
        self.assertEqual(placement.internship_company_id, self.company)
        self.assertEqual(placement.program_id, self.program)
        self.assertTrue(placement.form_due_date)
        self.assertTrue(placement.activity_ids, "company asked to complete the form")
        self.assertEqual(self.student.lifecycle_status, "offered")

    def test_form_submission_requires_objectives_hs_and_file(self):
        placement = self._accepted_placement()
        with self.assertRaises(UserError):
            placement.action_submit_form()
        self._submit_form(placement)
        self.assertEqual(placement.stage_code, "under_review")
        self.assertTrue(placement.form_submitted_date)

    def test_full_admission_flow_to_active(self):
        other = self._offer(self._new_application())
        placement = self._submit_form(self._accepted_placement())
        review, _action = self._review(placement, "approve")
        self.assertTrue(
            all([review.chk_company_vetted, review.chk_insurance_valid, review.chk_rtw_ok, review.chk_form_complete])
        )
        self.assertEqual(placement.stage_code, "agreement")
        placement._mark_agreement_complete()
        self.assertEqual(placement.stage_code, "approved")
        self.assertEqual(other.status, "cancelled")
        self.assertTrue(other.auto_withdrawn)
        self.assertEqual(self.opportunity.positions_filled, 1)
        self.assertEqual(self.student.lifecycle_status, "approved")
        placement.action_start()
        self.assertEqual(placement.stage_code, "active")
        self.assertEqual(placement.actual_start, self.today)
        self.assertEqual(self.student.lifecycle_status, "in_internship")

    def test_approval_blocked_by_checklist(self):
        placement = self._submit_form(self._accepted_placement())
        self.student.rtw_status = "pending"
        review = self.env["internship.university.review"].create({"placement_id": placement.id, "decision": "approve"})
        self.assertFalse(review.chk_rtw_ok)
        with self.assertRaises(UserError):
            review.action_decide()

    def test_more_documents_round(self):
        placement = self._submit_form(self._accepted_placement())
        _review, action = self._review(placement, "more_docs")
        self.assertEqual(placement.stage_code, "more_docs")
        self.assertEqual(action["res_model"], "internship.document.request.wizard")
        wizard = self.env["internship.document.request.wizard"].create(
            {
                "placement_id": placement.id,
                "requested_from": "student",
                "line_ids": [
                    (0, 0, {"document_type_id": self.env.ref("internship_base.doc_type_dbs").id, "mandatory": True})
                ],
            }
        )
        wizard.action_confirm()
        request = placement.document_request_ids
        self.assertTrue(request.name.startswith("DOC-"))
        self.assertEqual(request.state, "open")
        line = request.line_ids
        line.attachment_id = self.form_file
        self.assertEqual(request.state, "partial")
        line.action_accept()
        self.assertEqual(request.state, "complete")
        self.assertTrue(line.document_id, "accepted file registered")
        self.assertEqual(placement.stage_code, "under_review")
        self.assertEqual(placement.review_round, 2)

    def test_university_rejection(self):
        placement = self._submit_form(self._accepted_placement())
        with self.assertRaises(UserError):
            self._review(placement, "reject")
        self._review(
            placement, "reject", rejection_reason_id=self.env.ref("internship_base.reason_uni_rejection_hs").id
        )
        self.assertEqual(placement.stage_code, "rejected")
        self.assertTrue(placement.is_closed)
        self.assertEqual(self.student.lifecycle_status, "searching")

    def test_invalid_transition_raises(self):
        placement = self._accepted_placement()
        with self.assertRaises(UserError):
            placement.action_start()

    def test_hold_resume_terminate(self):
        placement = self._approved_placement()
        placement.action_start()
        with self.assertRaises(UserError):
            placement.action_hold()
        placement.action_hold(self.env.ref("internship_base.reason_hold_sickness"))
        self.assertEqual(placement.stage_code, "on_hold")
        self.assertEqual(placement.risk_flag, "amber")
        placement.action_resume()
        wizard = self.env["internship.terminate.wizard"].create(
            {
                "placement_id": placement.id,
                "initiated_by": "company",
                "reason_id": self.env.ref("internship_base.reason_termination_company").id,
            }
        )
        wizard.action_confirm()
        self.assertEqual(placement.stage_code, "terminated")
        self.assertEqual(placement.termination_initiated_by, "company")

    def test_one_open_placement_per_student(self):
        self._accepted_placement()
        second = self._offer(self._new_application())
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            second.action_student_accept()

    def test_cron_start_and_end(self):
        placement = self._approved_placement()
        placement.planned_start = self.today
        self.env["internship.placement"]._cron_start_end()
        self.assertEqual(placement.stage_code, "active")
        placement.write({"planned_start": "2000-01-01", "planned_end": "2000-02-01"})
        self.env["internship.placement"]._cron_start_end()
        self.assertEqual(placement.stage_code, "completion")

    def test_leave_working_days_and_change_request(self):
        placement = self._approved_placement()
        leave = self.env["internship.leave"].create(
            {"placement_id": placement.id, "date_from": "2026-09-28", "date_to": "2026-10-04"}
        )
        self.assertEqual(leave.days, 5, "Mon-Sun week = 5 working days")
        leave.action_approve()
        self.assertEqual(leave.approved_by_id, self.env.user)

        change = self.env["internship.change.request"].create(
            {"placement_id": placement.id, "change_type": "hours", "new_hours": 30, "reason": "Part-time study"}
        )
        self.assertTrue(change.agreement_amendment_needed)
        change.action_company_approve()
        self.assertEqual(change.state, "requested")
        change.action_university_approve()
        self.assertEqual(change.state, "approved")
        change.action_apply()
        self.assertEqual(placement.hours_per_week, 30)
        self.assertEqual(change.state, "applied")

    def test_invite_company_self_sourced(self):
        student = self.env["internship.student"].create(
            {"name": "Self Sourcer", "partner_id": self.env["res.partner"].create({"name": "Self Sourcer"}).id}
        )
        action = (
            self.env["internship.invite.company.wizard"]
            .create(
                {
                    "student_id": student.id,
                    "company_name": "Found Myself Ltd",
                    "contact_email": "hr@found.example",
                    "role_title": "Marketing Intern",
                }
            )
            .action_confirm()
        )
        placement = self.env["internship.placement"].browse(action["res_id"])
        self.assertEqual(placement.placement_source, "self_sourced")
        self.assertEqual(placement.internship_company_id.registration_source, "invited_by_student")
        self.assertTrue(placement.internship_company_id.sudo().invite_token)

    def test_legacy_migration_hook(self):
        apps = self.env["internship.application"]
        students = self.env["internship.student"]
        for status in ("documentation", "agreement", "approved", "placed"):
            student = self.env["internship.student"].create(
                {"name": f"Legacy {status}", "partner_id": self.student.partner_id.id}
            )
            students |= student
            apps |= self._new_application(student=student, status="accepted")
        duplicate = self._new_application(student=students[-1], status="accepted")
        self.env.cr.execute("CREATE TABLE _v2_app_lifecycle (application_id integer PRIMARY KEY, old_status varchar)")
        rows = list(zip(apps.ids, ("documentation", "agreement", "approved", "placed"), strict=True))
        rows.append((duplicate.id, "placed"))
        self.env.cr.executemany("INSERT INTO _v2_app_lifecycle VALUES (%s, %s)", rows)
        self.assertEqual(migrate_legacy_lifecycle(self.env), 5)
        self.assertEqual(apps.placement_id.mapped("stage_code"), ["under_review", "agreement", "approved", "active"])
        self.assertFalse(duplicate.placement_id.active, "second open placement kept but archived")
        self.assertEqual(migrate_legacy_lifecycle(self.env), 0, "idempotent: temp table dropped")
