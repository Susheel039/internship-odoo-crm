from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import InternshipCommon


@tagged("post_install", "-at_install")
class TestInternshipBase(InternshipCommon):
    def test_rule_fallback_programme_university_system(self):
        self.assertEqual(self.program._get_rule("form_due_days"), 7, "university default")
        self.university.default_rules_form_due_days = 10
        self.assertEqual(self.program._get_rule("form_due_days"), 10)
        self.program.form_due_days = 3
        self.assertEqual(self.program._get_rule("form_due_days"), 3)
        self.env["ir.config_parameter"].sudo().set_param("internship_base.rule_max_report_attempts", "4")
        self.university.default_rules_max_report_attempts = 0
        self.assertEqual(self.program._get_rule("max_report_attempts"), 4, "system parameter")
        self.assertEqual(self.env["internship.program"]._get_rule("resubmission_days"), 14, "empty recordset")

    def test_application_sequence_and_flow(self):
        application = self._new_application()
        self.assertTrue(application.name.startswith("APP-"))
        with self.assertRaises(ValidationError):
            application.action_shortlist()
        self._offer(application)
        self.assertEqual(application.status, "offered")
        self.assertTrue(application.offer_made)
        self.assertEqual(self.student.lifecycle_status, "offered")
        application.action_student_accept()
        self.assertEqual(application.status, "accepted")
        self.assertEqual(application.student_response, "accepted")

    def test_decline_and_reject_with_reason_wizard(self):
        declined = self._offer(self._new_application())
        wizard = (
            self.env["internship.reason.wizard"]
            .with_context(active_model="internship.application", active_ids=declined.ids)
            .create(
                {
                    "reason_type": "decline",
                    "method": "action_student_decline",
                    "reason_id": self.env.ref("internship_base.reason_decline_location").id,
                }
            )
        )
        wizard.action_confirm()
        self.assertEqual(declined.status, "declined")
        self.assertEqual(declined.decline_reason_id, self.env.ref("internship_base.reason_decline_location"))

        rejected = self._new_application()
        rejected.action_submit()
        rejected.action_reject(self.env.ref("internship_base.reason_rejection_skills"), "Not enough SQL")
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.rejection_reason, "Not enough SQL")

    def test_reason_wizard_refuses_private_methods(self):
        application = self._new_application()
        wizard = (
            self.env["internship.reason.wizard"]
            .with_context(active_model="internship.application", active_ids=application.ids)
            .create({"reason_type": "rejection", "method": "unlink", "reason_required": False})
        )
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertTrue(application.exists())

    def test_company_vetting_and_invite_token(self):
        self.assertFalse(self.company._is_vetted())
        self.company.action_vetting_approve()
        self.assertTrue(self.company._is_vetted())
        self.company._generate_invite_token()
        token = self.company.sudo().invite_token
        self.assertTrue(len(token) >= 32)
        self.assertTrue(self.company._check_invite_token(token))
        self.assertFalse(self.company._check_invite_token("wrong"))

    def test_expiry_cron_expires_lapsed_approval(self):
        self.company.action_vetting_approve()
        self.company.approved_until = "2000-01-01"
        self.env["internship.company"]._cron_expiry_alerts()
        self.assertEqual(self.company.vetting_state, "expired")
        self.assertTrue(self.company.activity_ids, "coordinator alerted")
        activity_count = len(self.company.activity_ids)
        self.env["internship.company"]._cron_expiry_alerts()
        self.assertEqual(len(self.company.activity_ids), activity_count, "cron is idempotent")

    def test_gdpr_retention_flags_but_never_deletes(self):
        self.student.expected_graduation = "2001-06-30"
        self.assertTrue(self.student.retention_until)
        self.env["internship.student"]._cron_gdpr_retention()
        self.assertTrue(self.student.retention_flagged)
        self.assertTrue(self.student.active)

    def test_lookup_code_unique(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["internship.skill"].create({"name": "Python again", "code": "python"}).flush_recordset()
