from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.internship_placement.tests.common import PlacementCommon

# 1x1 transparent PNG
SIGNATURE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


@tagged("post_install", "-at_install")
class TestAgreement(PlacementCommon):
    def _placement_in_signing(self):
        placement = self._submit_form(self._accepted_placement())
        self._review(placement, "approve")
        return placement, placement.agreement_id

    def _sign_all(self, agreement):
        for signer in agreement.signer_ids.sorted("sequence"):
            agreement._sign(signer, signer.partner_id.name, SIGNATURE, "203.0.113.7", "pytest")

    def test_approval_generates_and_sends_agreement(self):
        placement, agreement = self._placement_in_signing()
        self.assertEqual(placement.stage_code, "agreement")
        self.assertTrue(agreement.name.startswith("AGR-"))
        self.assertEqual(agreement.state, "sent_company")
        self.assertEqual(agreement.signer_ids.mapped("role"), ["company", "student", "university"])
        self.assertEqual(
            agreement.signer_ids[0].partner_id, self.line_manager.partner_id, "authorised line manager signs"
        )
        self.assertTrue(agreement.pdf_attachment_id)
        self.assertEqual(len(agreement.pdf_sha256), 64)
        self.assertTrue(all(len(s.sudo().access_token) >= 32 for s in agreement.signer_ids))

    def test_sequential_signing_approves_placement(self):
        other = self._offer(self._new_application())
        placement, agreement = self._placement_in_signing()
        company, student, university = agreement.signer_ids.sorted("sequence")
        with self.assertRaises(UserError):
            agreement._sign(student, "Out of turn", SIGNATURE)
        agreement._sign(company, "Line Manager", SIGNATURE, "203.0.113.7", "pytest")
        self.assertEqual(agreement.state, "sent_student")
        self.assertEqual(company.signed_ip, "203.0.113.7")
        agreement._sign(student, "Test Student", SIGNATURE)
        self.assertEqual(agreement.state, "awaiting_university")
        agreement._sign(university, "Coordinator", SIGNATURE)
        self.assertEqual(agreement.state, "fully_signed")
        self.assertTrue(agreement.signed_attachment_id)
        self.assertEqual(placement.stage_code, "approved")
        self.assertEqual(other.status, "cancelled")
        self.assertTrue(other.auto_withdrawn)
        self.assertEqual(self.opportunity.positions_filled, 1)

    @mute_logger("odoo.addons.internship_agreement.models.agreement")
    def test_tampered_document_is_refused(self):
        _placement, agreement = self._placement_in_signing()
        agreement.pdf_attachment_id.sudo().raw = b"%PDF-1.4 edited"
        with self.assertRaises(UserError):
            agreement._sign(agreement.current_signer_id, "Line Manager", SIGNATURE)

    def test_generate_for_migrated_placement(self):
        placement = self._submit_form(self._accepted_placement())
        placement._move_to("agreement", ("under_review",))  # e.g. a legacy placement without a document
        self.assertFalse(placement.agreement_id)
        placement.action_generate_agreement()
        self.assertEqual(placement.agreement_id.state, "sent_company")
        with self.assertRaises(UserError):
            placement.action_generate_agreement()

    def test_decline_and_reissue(self):
        placement, agreement = self._placement_in_signing()
        agreement._decline(agreement.current_signer_id, "Dates are wrong")
        self.assertEqual(agreement.state, "declined")
        self.assertEqual(agreement.declined_by_id, self.line_manager.partner_id)
        self.assertEqual(placement.stage_code, "agreement")
        action = agreement.action_regenerate()
        new = self.env["internship.agreement"].browse(action["res_id"])
        self.assertEqual(agreement.state, "voided")
        self.assertEqual(new.version, 2)
        self.assertEqual(new.state, "sent_company")
        self.assertEqual(placement.agreement_id, new)

    def test_reminders_every_three_days_max_three(self):
        _placement, agreement = self._placement_in_signing()
        Agreement = self.env["internship.agreement"]
        self.assertFalse(Agreement._cron_reminders(), "not yet due")
        agreement.current_signer_id.sent_date = fields.Datetime.now() - timedelta(days=4)
        self.assertEqual(Agreement._cron_reminders(), agreement)
        self.assertEqual(agreement.reminder_count, 1)
        self.assertFalse(Agreement._cron_reminders(), "throttled")
        agreement.write({"reminder_count": 3, "last_reminder_date": fields.Date.today() - timedelta(days=10)})
        self.assertFalse(Agreement._cron_reminders(), "capped at 3")

    def test_change_request_creates_amendment(self):
        placement, agreement = self._placement_in_signing()
        self._sign_all(agreement)
        placement.action_start()
        change = self.env["internship.change.request"].create(
            {
                "placement_id": placement.id,
                "change_type": "role",
                "new_role_title": "Data Engineer",
                "reason": "Promotion",
            }
        )
        change.action_company_approve()
        change.action_university_approve()
        change.action_apply()
        amendment = placement.agreement_id
        self.assertNotEqual(amendment, agreement)
        self.assertEqual(amendment.amendment_of_id, agreement)
        self.assertEqual(amendment.version, 2)
        self.assertEqual(amendment.state, "sent_company")
        self.assertEqual(agreement.state, "fully_signed", "the signed original stays on record")
        self._sign_all(amendment)
        self.assertEqual(placement.stage_code, "active", "amendments never move the placement")
