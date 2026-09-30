import base64

from dateutil.relativedelta import relativedelta

from odoo.addons.internship_base.tests.common import InternshipCommon


class PlacementCommon(InternshipCommon):
    """Adds helpers that walk a placement through the admission phase."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({"insurance_expiry": cls.today + relativedelta(years=2)})
        cls.company.action_vetting_approve()
        cls.student.write({"rtw_status": "verified"})
        cls.opportunity.write(
            {"start_date": cls.today + relativedelta(days=30), "end_date": cls.today + relativedelta(days=120)}
        )
        cls.form_file = cls.env["ir.attachment"].create(
            {"name": "form.pdf", "datas": base64.b64encode(b"%PDF-1.4 test"), "mimetype": "application/pdf"}
        )

    @classmethod
    def _accepted_placement(cls, student=None):
        application = cls._offer(cls._new_application(student=student))
        application.action_student_accept()
        return application.placement_id

    @classmethod
    def _submit_form(cls, placement):
        placement.write(
            {
                "learning_objectives": "<p>Build and test an API.</p>",
                "hs_confirmed": True,
                "form_attachment_id": cls.form_file.id,
                "line_manager_id": cls.line_manager.id,
            }
        )
        placement.action_submit_form()
        return placement

    @classmethod
    def _review(cls, placement, decision, **values):
        review = cls.env["internship.university.review"].create(
            {"placement_id": placement.id, "decision": decision, **values}
        )
        return review, review.action_decide()

    @classmethod
    def _approved_placement(cls, student=None):
        placement = cls._submit_form(cls._accepted_placement(student))
        cls._review(placement, "approve")
        placement._mark_agreement_complete()
        return placement
