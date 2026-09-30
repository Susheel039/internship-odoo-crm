import json

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from odoo.addons.internship_base.tests.common import InternshipCommon

TOKEN = "test-webhook-token-0123456789"
URL = "/internship/call-tracking/webhook"


@tagged("post_install", "-at_install")
class TestVapiWebhook(InternshipCommon, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("internship_vapi.webhook_token", TOKEN)

    def setUp(self):
        super().setUp()
        self.authenticate(None, None)  # anonymous, but bound to the test database

    def _post(self, payload, url=URL, token=TOKEN):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.url_open(url, data=json.dumps(payload), headers=headers)

    def _report(self, call_id="call-abc", purpose="inbound_enquiry", **extra):
        return {
            "message": {
                "type": "end-of-call-report",
                "endedReason": "customer-ended-call",
                "cost": 0.08,
                "call": {
                    "id": call_id,
                    "type": "inboundPhoneCall",
                    "startedAt": "2026-09-30T09:00:00Z",
                    "endedAt": "2026-09-30T09:03:00Z",
                    "customer": {"number": "+447700900888"},
                    "metadata": {"purpose": purpose, "student_id": self.student.id},
                },
                "artifact": {"transcript": "AI: Hello, this call is recorded..."},
                "analysis": {
                    "summary": "Asked about summer placements.",
                    "structuredData": {
                        "name": "Tom Reid",
                        "lead_category": "student",
                        "interest_level": "warm",
                        "consent_to_contact": True,
                        "email": "tom@students.example",
                    },
                },
                **extra,
            }
        }

    def test_auth(self):
        self.assertEqual(self._post(self._report(), token=None).status_code, 401)
        self.assertEqual(self._post(self._report(), token="wrong").status_code, 401)

    def test_end_of_call_creates_log_and_lead_once(self):
        response = self._post(self._report())
        self.assertEqual(response.status_code, 200, response.text)
        log = self.env["internship.call.log"].search([("external_call_id", "=", "call-abc")])
        self.assertEqual(log.status, "completed")
        self.assertEqual(log.duration_seconds, 180)
        self.assertEqual(log.direction, "inbound")
        self.assertEqual(log.student_id, self.student)
        lead = log.lead_id
        self.assertEqual(lead.source_channel, "vapi_inbound")
        self.assertEqual(lead.interest_level, "warm")
        self.assertEqual(lead.phone, "+447700900888")
        again = self._post(self._report())
        self.assertEqual(again.json()["status"], "duplicate")
        self.assertEqual(self.env["internship.vapi.event"].search_count([("external_call_id", "=", "call-abc")]), 1)
        self.assertEqual(self.env["crm.lead"].search_count([("phone", "=", "+447700900888")]), 1)

    def test_status_update_and_queued_log(self):
        log = self.env["internship.call.log"].create(
            {"name": "Queued", "status": "queued", "external_call_id": "call-s", "purpose": "attendance_reminder"}
        )
        self._post({"message": {"type": "status-update", "status": "ringing", "call": {"id": "call-s"}}})
        self.assertEqual(log.status, "ringing")

    def test_tool_endpoint(self):
        self.student.write({"student_id": "NBU-42", "date_of_birth": "2003-02-01"})
        payload = {
            "message": {
                "type": "tool-calls",
                "call": {"id": "call-t"},
                "toolCallList": [
                    {
                        "id": "tc1",
                        "name": "get_placement_status",
                        "parameters": {"student_id": "NBU-42", "date_of_birth": "2003-02-01"},
                    }
                ],
            }
        }
        body = self._post(payload, url="/internship/vapi/tool").json()
        self.assertEqual(body["results"][0]["toolCallId"], "tc1")
        self.assertIn("placement", body["results"][0]["result"])
        self.assertEqual(self._post(payload, url="/internship/vapi/tool", token="nope").status_code, 401)

    @mute_logger("odoo.http")
    def test_bad_payload(self):
        self.assertEqual(self._post({"message": "x"}).status_code, 400)
