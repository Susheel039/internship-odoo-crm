from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.internship_base.tests.common import InternshipCommon
from odoo.addons.internship_crm.upgrade_helpers import migrate_legacy_leads


@tagged("post_install", "-at_install")
class TestInternshipCrm(InternshipCommon):
    def test_legacy_leads_migrate_once(self):
        Legacy = self.env["internship.crm.lead"]
        qualified = Legacy.create(
            {
                "name": "L1",
                "student_id": self.student.id,
                "opportunity_id": self.opportunity.id,
                "lead_source": "campus",
                "stage": "proposal",
                "priority": "1",
            }
        )
        twin = self.env["crm.lead"].create({"name": "Existing twin", "type": "opportunity"})
        merged = Legacy.create({"name": "L2", "stage": "interview", "crm_id": twin.id})
        closed = Legacy.create({"name": "L3", "stage": "closed"})
        migrate_legacy_leads(self.env)

        Lead = self.env["crm.lead"].with_context(active_test=False)
        lead = Lead.search([("legacy_internship_lead_id", "=", qualified.id)])
        self.assertEqual(len(lead), 1)
        self.assertEqual(lead.stage_id, lead._internship_stage("qualified"))
        self.assertEqual(lead.source_channel, "campus_event")
        self.assertEqual(lead.lead_category, "student")
        self.assertEqual(lead.internship_company_id, self.company)
        self.assertEqual(twin.legacy_internship_lead_id, merged, "existing crm twin enriched, not duplicated")
        self.assertEqual(twin.stage_id.name, "Interview")
        lost = Lead.search([("legacy_internship_lead_id", "=", closed.id)])
        self.assertFalse(lost.active)
        self.assertTrue(lost.lost_reason_id)

        count = Lead.search_count([("legacy_internship_lead_id", "!=", False)])
        migrate_legacy_leads(self.env)
        self.assertEqual(Lead.search_count([("legacy_internship_lead_id", "!=", False)]), count, "idempotent")

    def test_convert_to_student(self):
        lead = self.env["crm.lead"].create(
            {
                "name": "Enquiry",
                "contact_name": "Chloe Evans",
                "email_from": "chloe@students.example",
                "university_id": self.university.id,
                "lead_category": "student",
                "consent_to_contact": True,
            }
        )
        lead.action_convert_to_student()
        self.assertEqual(lead.student_id.name, "Chloe Evans")
        self.assertEqual(lead.student_id.university_id, self.university)
        self.assertTrue(lead.student_id.gdpr_consent)
        with self.assertRaises(UserError):
            lead.action_convert_to_student()

    def test_convert_to_company_sends_invite(self):
        lead = self.env["crm.lead"].create(
            {
                "name": "Host enquiry",
                "partner_name": "Riverside Analytics Ltd",
                "contact_name": "Sam Patel",
                "email_from": "sam@riverside.example",
                "lead_category": "company",
            }
        )
        lead.action_convert_to_company()
        company = lead.internship_company_id
        self.assertEqual(company.name, "Riverside Analytics Ltd")
        self.assertEqual(company.registration_source, "invited_by_university")
        self.assertTrue(company.sudo().invite_token)
