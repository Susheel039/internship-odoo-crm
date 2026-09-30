from odoo import fields, models


class InternshipMeetingAttendee(models.Model):
    _name = "internship.meeting.attendee"
    _description = "Meeting Attendee"
    _order = "meeting_id, role"

    meeting_id = fields.Many2one("internship.meeting", required=True, index=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    role = fields.Selection(
        [("university", "University"), ("student", "Student"), ("company", "Company")], required=True
    )
    attendance_state = fields.Selection(
        [("invited", "Invited"), ("accepted", "Accepted"), ("attended", "Attended"), ("absent", "Absent")],
        default="invited",
        required=True,
    )

    _unique_partner = models.Constraint("unique(meeting_id, partner_id)", "This person is already invited.")
