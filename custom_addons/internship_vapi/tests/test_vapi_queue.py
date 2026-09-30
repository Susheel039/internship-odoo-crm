from datetime import datetime
from unittest.mock import MagicMock

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.internship_placement.tests.common import PlacementCommon

from ..services import tools
from ..services.calling_window import parse_calling_window
from ..services.vapi_adapter import ToolCall


@tagged("post_install", "-at_install")
class TestVapiQueue(PlacementCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("internship_vapi.enabled", "True")
        params.set_param("internship_vapi.default_assistant_id", "asst-leads")
        params.set_param("internship_vapi.chaser_assistant_id", "asst-chaser")
        params.set_param("internship_vapi.phone_number_id", "phone-1")
        cls.lead = cls.env["crm.lead"].create(
            {"name": "Company lead", "phone": "07700 900555", "lead_category": "company", "partner_name": "Acme"}
        )
        cls.CallLog = cls.env["internship.call.log"]

    def _fake_client(self):
        client = MagicMock()
        client.create_call.return_value = {"id": "vapi-123", "status": "queued"}
        return client

    def test_calling_window(self):
        with self.assertRaises(ValueError):
            parse_calling_window("weekdays 9 to 5")
        self.assertEqual(parse_calling_window("Sat-Sun 10:30-12:00 UTC")["days"], {5, 6})
        settings = self.CallLog._settings()
        self.assertTrue(self.CallLog._in_calling_window(settings, datetime(2026, 9, 30, 10, 0)))  # Wed 11:00 BST
        self.assertFalse(self.CallLog._in_calling_window(settings, datetime(2026, 9, 30, 20, 0)))  # 21:00 BST
        self.assertFalse(self.CallLog._in_calling_window(settings, datetime(2026, 10, 3, 10, 0)))  # Saturday

    def test_queue_and_dial_with_metadata(self):
        self.lead.tps_checked = True
        log = self.CallLog.action_queue_call("lead_generation", self.lead)
        self.assertEqual(log.status, "queued")
        self.assertEqual(log.customer_number, "+447700900555")
        client = self._fake_client()
        log._dial(client=client)
        self.assertEqual(log.external_call_id, "vapi-123")
        self.assertEqual(log.attempt_count, 1)
        _args, kwargs = client.create_call.call_args
        self.assertEqual(client.create_call.call_args.args[1], "asst-leads")
        metadata = kwargs["metadata"]
        self.assertEqual(metadata["call_log_id"], log.id)
        self.assertEqual(metadata["lead_id"], self.lead.id)
        self.assertEqual(metadata["odoo_db"], self.env.cr.dbname)
        self.assertEqual(self.lead.call_count, 1)

    def test_do_not_call_and_tps_block(self):
        log = self.CallLog.action_queue_call("lead_generation", self.lead)
        client = self._fake_client()
        log._dial(client=client)
        self.assertFalse(client.create_call.called, "company marketing call needs a TPS check")
        self.assertIn("TPS", log.error_message)
        self.lead.write({"tps_checked": True, "do_not_call": True})
        log._dial(client=client)
        self.assertEqual(log.status, "cancelled")
        self.assertFalse(client.create_call.called)

    def test_kill_switch_and_attempts(self):
        self.lead.tps_checked = True
        log = self.CallLog.action_queue_call("lead_generation", self.lead)
        self.env["ir.config_parameter"].sudo().set_param("internship_vapi.enabled", "False")
        client = self._fake_client()
        log._dial(client=client)
        self.assertFalse(client.create_call.called)
        self.env["ir.config_parameter"].sudo().set_param("internship_vapi.enabled", "True")
        log.attempt_count = 3
        log._dial(client=client)
        self.assertEqual(log.status, "cancelled")

    def test_chase_document_request_uses_chaser_assistant(self):
        placement = self._submit_form(self._accepted_placement())
        self.student.phone = "07700 900101"
        request = self.env["internship.document.request"].create(
            {"placement_id": placement.id, "requested_from": "student", "due_date": "2026-01-01"}
        )
        request.action_chase_by_phone()
        log = self.CallLog.search([("target_model", "=", request._name), ("target_id", "=", request.id)])
        self.assertEqual(log.purpose, "document_chase")
        client = self._fake_client()
        log._dial(client=client)
        self.assertEqual(client.create_call.call_args.args[1], "asst-chaser")
        self.assertIn("due_date", client.create_call.call_args.kwargs["variable_values"])

    def test_user_voice_channel(self):
        self.lead.tps_checked = True
        salesperson = self.env["res.users"].create({"name": "Sales Agent", "login": "sales_agent_voice"})
        self.lead.user_id = salesperson
        salesperson.write(
            {
                "channel_voice_phone_number_id": "user-phone-1",
                "channel_voice_assistant_id": "user-asst-1",
                "channel_voice_api_key": "user-key",
            }
        )
        log = self.CallLog.action_queue_call("lead_generation", self.lead)
        client = self._fake_client()
        log._dial(client=client)
        self.assertEqual(client.create_call.call_args.args[1], "user-asst-1")
        self.assertEqual(client.create_call.call_args.kwargs["phone_number_id"], "user-phone-1")
        self.assertEqual(log._voice_identity(self.CallLog._settings())["api_key"], "user-key")

        salesperson.channel_voice_enabled = False
        blocked = self.CallLog.action_queue_call("lead_generation", self.lead)
        client = self._fake_client()
        blocked._dial(client=client)
        self.assertFalse(client.create_call.called, "switched off: no fallback to the company account")
        self.assertIn("switched off", blocked.error_message)

    def test_queue_needs_phone(self):
        lead = self.env["crm.lead"].create({"name": "No phone"})
        with self.assertRaises(UserError):
            self.CallLog.action_queue_call("lead_generation", lead)

    def test_placement_status_tool_verifies_identity(self):
        placement = self._accepted_placement()
        call = ToolCall(
            id="t", name="get_placement_status", arguments={"student_id": "T-0001", "date_of_birth": "2004-05-06"}
        )
        answer = tools.dispatch(self.env, call)
        self.assertIn(placement.stage_id.name, answer)
        wrong = ToolCall(
            id="t", name="get_placement_status", arguments={"student_id": "T-0001", "date_of_birth": "2000-01-01"}
        )
        self.assertIn("could not verify", tools.dispatch(self.env, wrong))
        self.assertNotIn(self.student.name, tools.dispatch(self.env, wrong))

    def test_lead_tool_and_callback(self):
        call = ToolCall(
            id="t",
            name="create_or_update_lead",
            arguments={
                "name": "Priya Shah",
                "organisation": "Harbour Health",
                "phone": "07700 900777",
                "lead_category": "company",
                "interest_level": "hot",
                "consent_to_contact": True,
            },
        )
        self.assertIn("reference", tools.dispatch(self.env, call))
        lead = self.env["crm.lead"].search([("phone", "=", "+447700900777")])
        self.assertEqual(lead.interest_level, "hot")
        self.assertTrue(lead.consent_to_contact)
        tools.dispatch(
            self.env,
            ToolCall(id="u", name="create_or_update_lead", arguments={"phone": "+44 7700 900777", "notes": "again"}),
        )
        self.assertEqual(
            self.env["crm.lead"].search_count([("phone", "=", "+447700900777")]), 1, "deduplicated by phone"
        )
        booked = tools.dispatch(
            self.env,
            ToolCall(
                id="v",
                name="book_callback",
                arguments={"lead_ref": str(lead.id), "datetime_iso": "2031-05-01T14:30:00"},
            ),
        )
        self.assertIn("booked", booked)
        self.assertTrue(lead.callback_datetime)
        self.assertTrue(lead.activity_ids)
        self.assertIn("Sorry", tools.dispatch(self.env, ToolCall(id="w", name="drop_tables", arguments={})))
