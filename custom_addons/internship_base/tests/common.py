from odoo import fields
from odoo.tests import TransactionCase


class InternshipCommon(TransactionCase):
    """Minimal master data shared by the internship test suites."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env["res.users"])
        Partner = cls.env["res.partner"]
        cls.university = cls.env["internship.university"].create(
            {"name": "Test University", "partner_id": Partner.create({"name": "Test University"}).id}
        )
        cls.program = cls.env["internship.program"].create(
            {"name": "Test Programme", "university_id": cls.university.id}
        )
        cls.student = cls.env["internship.student"].create(
            {
                "name": "Test Student",
                "partner_id": Partner.create({"name": "Test Student", "email": "student@test.example"}).id,
                "university_id": cls.university.id,
                "program_id": cls.program.id,
                "date_of_birth": "2004-05-06",
                "student_id": "T-0001",
            }
        )
        cls.company = cls.env["internship.company"].create(
            {"name": "Test Company", "partner_id": Partner.create({"name": "Test Company"}).id}
        )
        cls.line_manager = cls.env["internship.line.manager"].create(
            {
                "partner_id": Partner.create({"name": "Test Line Manager"}).id,
                "company_id": cls.company.id,
                "can_approve_attendance": True,
                "can_sign_agreement": True,
                "can_issue_certificate": True,
            }
        )
        cls.opportunity = cls.env["internship.opportunity"].create(
            {"name": "Test Opportunity", "company_id": cls.company.id, "program_id": cls.program.id}
        )

    @classmethod
    def _new_application(cls, student=None, opportunity=None, **values):
        return cls.env["internship.application"].create(
            {
                "student_id": (student or cls.student).id,
                "opportunity_id": (opportunity or cls.opportunity).id,
                **values,
            }
        )

    @classmethod
    def _offer(cls, application):
        application.action_submit()
        application.action_shortlist()
        application.action_interview()
        application.action_offer()
        return application
