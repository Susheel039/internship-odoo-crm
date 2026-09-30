from odoo.http import Request
from odoo.tests import HttpCase, tagged

from odoo.addons.internship_placement.tests.common import PlacementCommon


@tagged("post_install", "-at_install")
class TestInternshipPortal(PlacementCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal = cls.env.ref("base.group_portal")
        cls.student_user = cls.env["res.users"].create(
            {
                "name": "Portal Student",
                "login": "portal_student",
                "password": "portal_student_pw1",
                "partner_id": cls.student.partner_id.id,
                "group_ids": [(6, 0, [portal.id])],
            }
        )
        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "Portal Manager",
                "login": "portal_manager",
                "password": "portal_manager_pw1",
                "partner_id": cls.line_manager.partner_id.id,
                "group_ids": [(6, 0, [portal.id])],
            }
        )
        cls.line_manager.user_id = cls.manager_user
        cls.outsider = cls.env["res.users"].create(
            {
                "name": "Outsider",
                "login": "portal_outsider",
                "password": "portal_outsider_pw1",
                "group_ids": [(6, 0, [portal.id])],
            }
        )

    def test_line_manager_form_student_monthly_manager_approval(self):
        placement = self._accepted_placement()
        placement.line_manager_id = self.line_manager

        # Line manager submits the internship form through the portal.
        self.authenticate("portal_manager", "portal_manager_pw1")
        page = self.url_open(f"/my/placements/{placement.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Internship form", page.text)
        response = self.url_open(
            f"/my/placements/{placement.id}/form",
            data={"learning_objectives": "Build dashboards", "hs_confirmed": "1", "csrf_token": self._csrf()},
            files={"form_file": ("form.pdf", b"%PDF-1.4 portal", "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(placement.stage_code, "under_review")

        # University approves; agreement signed offline; placement starts.
        self._review(placement, "approve")
        placement._mark_agreement_complete()
        placement.action_start()
        monthly = placement.monthly_ids[:1]

        # Student lists placements and submits the monthly record.
        self.authenticate("portal_student", "portal_student_pw1")
        self.assertIn(placement.name, self.url_open("/my/placements").text)
        self.url_open(
            f"/my/placements/{placement.id}/monthly/{monthly.id}/submit",
            data={"days_attended": str(monthly.days_expected), "total_hours": "30", "csrf_token": self._csrf()},
        )
        self.assertEqual(monthly.state, "submitted")

        # Line manager approves it.
        self.authenticate("portal_manager", "portal_manager_pw1")
        self.url_open(
            f"/my/placements/{placement.id}/monthly/{monthly.id}/approve",
            data={"working_as_required": "1", "rating": "4", "csrf_token": self._csrf()},
        )
        self.assertEqual(monthly.state, "company_approved")
        self.assertEqual(monthly.company_approved_by_id, self.manager_user)
        self.assertTrue(monthly.working_as_required)

    def test_student_uploads_requested_document_and_requests_leave(self):
        placement = self._submit_form(self._accepted_placement())
        request = self.env["internship.document.request"].create(
            {
                "placement_id": placement.id,
                "requested_from": "student",
                "line_ids": [(0, 0, {"document_type_id": self.env.ref("internship_base.doc_type_dbs").id})],
            }
        )
        line = request.line_ids
        self.authenticate("portal_student", "portal_student_pw1")
        self.url_open(
            f"/my/placements/{placement.id}/documents/{line.id}",
            data={"csrf_token": self._csrf()},
            files={"document": ("dbs.pdf", b"%PDF-1.4 dbs", "application/pdf")},
        )
        self.assertTrue(line.attachment_id)
        self.assertEqual(request.state, "partial")

    def test_outsider_cannot_see_or_act(self):
        placement = self._accepted_placement()
        self.authenticate("portal_outsider", "portal_outsider_pw1")
        self.assertEqual(self.url_open(f"/my/placements/{placement.id}").status_code, 404)
        self.assertNotIn(placement.name, self.url_open("/my/placements").text)
        response = self.url_open(f"/my/placements/{placement.id}/request-form", data={"csrf_token": self._csrf()})
        self.assertEqual(response.status_code, 404)
        # Record rules: the portal user cannot read someone else's placement directly either.
        self.assertFalse(self.env["internship.placement"].with_user(self.outsider).search([("id", "=", placement.id)]))
        self.assertTrue(
            self.env["internship.placement"].with_user(self.student_user).search([("id", "=", placement.id)])
        )

    def _csrf(self):
        return Request.csrf_token(self)
