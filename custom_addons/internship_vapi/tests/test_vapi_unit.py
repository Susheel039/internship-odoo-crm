from unittest.mock import MagicMock, patch

from odoo.tests import BaseCase, tagged

from ..services import vapi_adapter
from ..services.phone import to_e164
from ..services.vapi_client import VapiClient, VapiError


@tagged("post_install", "-at_install")
class TestVapiAdapter(BaseCase):
    def test_e164(self):
        self.assertEqual(to_e164("07700 900123"), "+447700900123")
        self.assertEqual(to_e164("+44 7700 900123"), "+447700900123")
        self.assertFalse(to_e164("12"))
        self.assertFalse(to_e164(None))

    def test_end_of_call_report(self):
        event = vapi_adapter.parse(
            {
                "message": {
                    "type": "end-of-call-report",
                    "endedReason": "customer-did-not-answer",
                    "cost": 0.12,
                    "call": {
                        "id": "c1",
                        "type": "outboundPhoneCall",
                        "startedAt": "2026-09-30T10:00:00Z",
                        "endedAt": "2026-09-30T10:02:30Z",
                        "metadata": {"call_log_id": 5},
                        "customer": {"number": "+447700900123"},
                    },
                    "artifact": {"transcript": "AI: Hello", "recording": {"stereoUrl": "https://rec"}},
                    "analysis": {"summary": "Short", "structuredData": {"interest_level": "warm"}},
                }
            }
        )
        self.assertEqual(event.call_id, "c1")
        self.assertEqual(event.duration_seconds, 150)
        self.assertEqual(event.direction, "outbound")
        self.assertEqual(event.log_status(), "no_answer")
        self.assertEqual(event.recording_url, "https://rec")
        self.assertEqual(event.structured_data, {"interest_level": "warm"})
        self.assertEqual(event.cost, 0.12)

    def test_tool_call_shapes(self):
        documented = vapi_adapter.parse(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [{"id": "t1", "name": "book_callback", "parameters": {"a": 1}}],
                }
            }
        )
        openai_style = vapi_adapter.parse(
            {
                "message": {
                    "type": "tool-calls",
                    "toolCallList": [
                        {"id": "t2", "type": "function", "function": {"name": "x", "arguments": '{"b": 2}'}}
                    ],
                }
            }
        )
        self.assertEqual(
            (documented.tool_calls[0].name, documented.tool_calls[0].arguments), ("book_callback", {"a": 1})
        )
        self.assertEqual((openai_style.tool_calls[0].name, openai_style.tool_calls[0].arguments), ("x", {"b": 2}))
        body = vapi_adapter.tool_results_response([("t1", "book_callback", "done")])
        self.assertEqual(body, {"results": [{"toolCallId": "t1", "name": "book_callback", "result": "done"}]})

    def test_malformed(self):
        with self.assertRaises(vapi_adapter.PayloadError):
            vapi_adapter.parse("nope")
        with self.assertRaises(vapi_adapter.PayloadError):
            vapi_adapter.parse({"message": {"no": "type"}})

    def _client(self):
        env = MagicMock()
        env["ir.config_parameter"].sudo().get_param.side_effect = lambda key, default=None: (
            "secret-key" if key == "internship_vapi.api_key" else default
        )
        return VapiClient(env)

    def test_client_retries_then_succeeds(self):
        busy = MagicMock(status_code=503, text="busy", content=b"x")
        ok = MagicMock(status_code=201, content=b"{}")
        ok.json.return_value = {"id": "call-1", "status": "queued"}
        with (
            patch("odoo.addons.internship_vapi.services.vapi_client.requests.request", side_effect=[busy, ok]) as req,
            patch("odoo.addons.internship_vapi.services.vapi_client.time.sleep"),
        ):
            result = self._client().create_call("+447700900123", "asst", {"call_log_id": 1}, {"student_name": "A"})
        self.assertEqual(result["id"], "call-1")
        self.assertEqual(req.call_count, 2)
        body = req.call_args.kwargs["json"]
        self.assertEqual(body["customer"], {"number": "+447700900123"})
        self.assertEqual(body["assistantOverrides"]["variableValues"], {"student_name": "A"})
        self.assertEqual(req.call_args.kwargs["timeout"], 10)

    def test_client_gives_up_on_client_error(self):
        bad = MagicMock(status_code=400, text="bad number", content=b"x")
        with (
            patch("odoo.addons.internship_vapi.services.vapi_client.requests.request", return_value=bad),
            self.assertRaises(VapiError),
        ):
            self._client().create_call("+447700900123", "asst")
