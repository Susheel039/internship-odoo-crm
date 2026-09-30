from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.internship_monitoring import upgrade_helpers
from odoo.addons.internship_placement.tests.common import PlacementCommon


@tagged("post_install", "-at_install")
class TestMonitoring(PlacementCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.placement = cls._approved_placement()
        cls.placement.write({"planned_start": date(2026, 1, 1), "planned_end": date(2026, 12, 31)})
        cls.placement.action_start()
        cls.placement.actual_start = date(2026, 1, 1)  # started in January: full months since
        cls.placement.monthly_ids.unlink()  # recreated per test with the backdated start

    def _month(self, year=2026, month=9):
        return self.env["internship.attendance.monthly"]._ensure_for(self.placement, date(year, month, 15))

    def test_start_creates_current_monthly_record(self):
        student = self.env["internship.student"].create(
            {"name": "Starter", "partner_id": self.student.partner_id.id, "rtw_status": "verified"}
        )
        placement = self._approved_placement(student)
        placement.action_start()
        self.assertEqual(len(placement.monthly_ids), 1)
        record = placement.monthly_ids
        self.assertEqual(record.state, "pending")
        self.assertEqual(record.due_date.day, 5, "due on the 5th of the next month")

    def test_unique_month_and_due_date(self):
        record = self._month()
        self.assertEqual(record, self._month(), "ensure is idempotent")
        self.assertEqual(record.date_start, date(2026, 9, 1))
        self.assertEqual(record.date_end, date(2026, 9, 30))
        self.assertEqual(record.days_expected, 22)
        self.assertEqual(record.due_date, date(2026, 10, 5))

    def test_attendance_pct_excludes_approved_leave(self):
        record = self._month()
        leave = self.env["internship.leave"].create(
            {
                "placement_id": self.placement.id,
                "leave_type": "sick",
                "date_from": "2026-09-14",
                "date_to": "2026-09-18",
            }
        )
        leave.action_approve()
        self.assertEqual(record.sick_days, 5)
        record.days_attended = 17
        self.assertAlmostEqual(record.attendance_pct, 100.0)

    def _submit_and_approve(self, record, attended, rating="4", working="yes"):
        record.days_attended = attended
        record.action_student_submit()
        record.write({"rating": rating, "working_as_required": working})
        record.action_company_approve()
        return record

    def test_good_month_does_not_escalate(self):
        record = self._submit_and_approve(self._month(), 22)
        self.assertEqual(record.state, "company_approved")
        self.assertFalse(record.tripartite_triggered)
        record.action_university_review()
        self.assertEqual(record.state, "university_reviewed")
        self.assertEqual(self.placement.risk_flag, "green")

    def test_low_attendance_triggers_tripartite(self):
        record = self._submit_and_approve(self._month(), 10)
        self.assertTrue(record.tripartite_triggered)
        self.assertIn("Attendance", record.trigger_reason)
        meeting = record.meeting_id
        self.assertEqual(meeting.meeting_type, "tripartite")
        self.assertEqual(meeting.trigger, "auto_attendance")
        self.assertEqual(set(meeting.attendee_ids.mapped("role")), {"university", "student", "company"})
        self.assertEqual(self.placement.risk_flag, "red")
        meeting.action_complete()
        self.assertEqual(self.placement.risk_flag, "green", "resolved once the meeting is held")

    def test_low_rating_and_not_working_trigger(self):
        record = self._submit_and_approve(self._month(2026, 8), 21, rating="2")
        self.assertEqual(record.meeting_id.trigger, "auto_rating")
        record = self._submit_and_approve(self._month(2026, 7), 23, rating="4", working="no")
        self.assertEqual(record.meeting_id.trigger, "auto_not_working")

    def test_company_approval_needs_confirmation_and_permission(self):
        record = self._month()
        record.action_student_submit()
        with self.assertRaises(UserError):
            record.action_company_approve()
        manager_user = self.env["res.users"].create(
            {
                "name": "LM User",
                "login": "lm_user_monitoring",
                "group_ids": [
                    (6, 0, [self.env.ref("base.group_user").id, self.env.ref("internship_base.group_line_manager").id])
                ],
            }
        )
        self.line_manager.write({"user_id": manager_user.id, "can_approve_attendance": False})
        record.write({"rating": "4", "working_as_required": "yes"})
        with self.assertRaises(UserError):
            record.with_user(manager_user).sudo(False)._check_can_company_approve()

    def test_cron_marks_late(self):
        record = self._month(2026, 1)
        self.env["internship.attendance.monthly"]._cron_reminders()
        self.assertEqual(record.state, "late")
        self.assertTrue(record.is_late)
        self.assertEqual(self.placement.risk_flag, "amber")

    def test_university_company_meeting_outcome(self):
        placement = self._submit_form(
            self._accepted_placement(
                student=self.env["internship.student"].create(
                    {"name": "Meeting Student", "partner_id": self.student.partner_id.id, "rtw_status": "verified"}
                )
            )
        )
        action = placement.action_schedule_meeting()
        self.assertEqual(placement.stage_code, "meeting")
        meeting = self.env["internship.meeting"].browse(action["res_id"])
        self.assertEqual(meeting.meeting_type, "university_company")
        meeting.action_sync_calendar()
        self.assertTrue(meeting.calendar_event_id)
        self.assertTrue(meeting.video_url)
        meeting.additional_docs_needed = True
        result = meeting.action_complete()
        self.assertEqual(placement.stage_code, "more_docs")
        self.assertEqual(result["res_model"], "internship.document.request.wizard")

    def test_daily_log_feeds_monthly(self):
        Attendance = self.env["internship.attendance"]
        for day, status in ((1, "present"), (2, "half_day"), (3, "absent")):
            Attendance.create(
                {
                    "student_id": self.student.id,
                    "placement_id": self.placement.id,
                    "attendance_date": date(2026, 6, day),
                    "status": status,
                }
            )
        record = self._month(2026, 6)
        self.assertEqual(len(record.attendance_ids), 3)
        self.assertEqual(record.days_attended, 1.5)

    def test_termination_schedules_exit_meeting(self):
        self.placement._terminate("student", self.env.ref("internship_base.reason_termination_health"))
        meeting = self.placement.exit_meeting_id
        self.assertEqual(meeting.meeting_type, "exit")
        self.assertNotIn(
            "company", meeting.attendee_ids.mapped("role"), "student-initiated exit is student + university"
        )

    def test_migration_links_legacy_rows(self):
        legacy = self.env["internship.performance"].create(
            {"student_id": self.student.id, "opportunity_id": self.opportunity.id, "score": 7}
        )
        self.assertFalse(legacy.placement_id)
        upgrade_helpers.link_to_placements(self.env.cr, "internship_performance")
        legacy.invalidate_recordset()
        self.assertEqual(legacy.placement_id, self.placement)
        upgrade_helpers.link_to_placements(self.env.cr, "internship_performance")  # idempotent

    def test_cron_creates_monthly_for_active(self):
        self.placement.monthly_ids.unlink()
        created = self.env["internship.attendance.monthly"]._cron_create_monthly()
        self.assertIn(self.placement, created.placement_id)
        self.assertFalse(self.env["internship.attendance.monthly"]._cron_create_monthly(), "idempotent")
