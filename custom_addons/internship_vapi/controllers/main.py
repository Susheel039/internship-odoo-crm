import hmac
import ipaddress
import logging

from odoo import fields, http
from odoo.http import request

from ..services import tools, vapi_adapter
from ..services.lead_sync import upsert_lead
from ..services.phone import to_e164

_logger = logging.getLogger(__name__)

LEAD_PURPOSES = ("lead_generation", "inbound_enquiry")


class InternshipCallTrackingWebhook(http.Controller):
    """Vapi server URL. Same bearer-token auth for events and tool calls."""

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    @staticmethod
    def _is_local():
        try:
            return ipaddress.ip_address(request.httprequest.remote_addr or "").is_loopback
        except ValueError:
            return False

    def _check_auth(self):
        """None when authorised, else an error response. Non-local calls must use HTTPS."""
        expected = request.env["ir.config_parameter"].sudo().get_param("internship_vapi.webhook_token")
        supplied = request.httprequest.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not expected or not supplied or not hmac.compare_digest(supplied, expected):
            return request.make_json_response({"error": "unauthorized"}, status=401)
        if not self._is_local() and request.httprequest.scheme != "https":
            return request.make_json_response({"error": "https_required"}, status=403)
        return None

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------
    @http.route("/internship/call-tracking/webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def receive_call_report(self, **kwargs):
        error = self._check_auth()
        if error:
            return error
        payload = request.httprequest.get_json(silent=True)
        try:
            event = vapi_adapter.parse(payload)
        except vapi_adapter.PayloadError as parse_error:
            return request.make_json_response({"error": str(parse_error)}, status=400)
        if event.type == "end-of-call-report" and not event.call_id:
            return request.make_json_response({"error": "missing_call_id"}, status=400)

        env = request.env(su=True)
        stored, is_new = env["internship.vapi.event"]._store(event.type, event.call_id, payload)
        if event.type == "tool-calls":
            # Tool calls must always be answered, even on a retry.
            return request.make_json_response(self._run_tools(env, event))
        if not is_new and stored.processed:
            return request.make_json_response({"status": "duplicate", "record_id": stored.call_log_id.id})
        try:
            with env.cr.savepoint():
                call_log = self._process(env, event)
            stored.write({"processed": True, "call_log_id": call_log.id if call_log else False, "error": False})
        except Exception as process_error:  # noqa: BLE001 - keep the raw event, report failure
            _logger.exception("Vapi event %s for call %s could not be processed", event.type, event.call_id)
            stored.error = str(process_error)
            return request.make_json_response({"status": "error"}, status=500)
        if call_log is None:
            return request.make_json_response({"status": "ignored"}, status=202)
        return request.make_json_response({"status": "ok", "record_id": call_log.id})

    def _find_log(self, env, event):
        CallLog = env["internship.call.log"]
        log = CallLog.search([("external_call_id", "=", event.call_id)], limit=1) if event.call_id else CallLog
        if not log and event.metadata.get("call_log_id"):
            try:
                log = CallLog.browse(int(event.metadata["call_log_id"])).exists()
            except (TypeError, ValueError):
                log = CallLog
        return log

    @staticmethod
    def _relation(env, model, raw_id):
        try:
            return env[model].browse(int(raw_id)).exists().id or False
        except (TypeError, ValueError):
            return False

    def _process(self, env, event):
        if event.type == "status-update":
            log = self._find_log(env, event)
            status = event.log_status()
            if log and status:
                log.status = status
            return log or None
        if event.type != "end-of-call-report":
            return None
        log = self._find_log(env, event)
        metadata = event.metadata
        values = {
            "external_call_id": event.call_id,
            "call_datetime": event.started_at or fields.Datetime.now(),
            "call_type": event.direction,
            "direction": event.direction,
            "status": event.log_status(),
            "duration_seconds": event.duration_seconds,
            "summary": event.summary,
            "recording_url": event.recording_url,
            "transcript": event.transcript,
            "ended_reason": event.ended_reason,
            "cost": event.cost,
            "structured_data": event.structured_data or False,
            "assistant_id": event.assistant_id,
            "phone_number_id": event.phone_number_id,
        }
        if event.customer_number:
            values["customer_number"] = to_e164(event.customer_number) or event.customer_number
        for field_name, model in (
            ("student_id", "internship.student"),
            ("opportunity_id", "internship.opportunity"),
            ("placement_id", "internship.placement"),
            ("lead_id", "crm.lead"),
        ):
            if metadata.get(field_name):
                values[field_name] = self._relation(env, model, metadata[field_name])
        if log:
            log.write({k: v for k, v in values.items() if v not in (None, False) or k in ("structured_data",)})
        else:
            values.update(
                name=f"VAPI-{event.call_id}",
                purpose=metadata.get("purpose") or ("inbound_enquiry" if event.direction == "inbound" else False),
            )
            log = env["internship.call.log"].create(values)
        purpose = log.purpose or metadata.get("purpose")
        if purpose in LEAD_PURPOSES and (event.structured_data or event.summary):
            channel = "vapi_inbound" if event.direction == "inbound" else "vapi_outbound"
            upsert_lead(env, event.structured_data, channel, summary=event.summary, call_log=log)
        elif log.lead_id and event.summary:
            log.lead_id.message_post(body=event.summary)
        return log

    def _run_tools(self, env, event):
        log = self._find_log(env, event) or None
        results = [(call.id, call.name, tools.dispatch(env, call, call_log=log)) for call in event.tool_calls]
        return vapi_adapter.tool_results_response(results)

    # ------------------------------------------------------------------
    # Dedicated tool endpoint (same format as tool-calls webhooks)
    # ------------------------------------------------------------------
    @http.route("/internship/vapi/tool", type="http", auth="public", methods=["POST"], csrf=False)
    def vapi_tool(self, **kwargs):
        error = self._check_auth()
        if error:
            return error
        payload = request.httprequest.get_json(silent=True)
        try:
            event = vapi_adapter.parse(payload)
        except vapi_adapter.PayloadError as parse_error:
            return request.make_json_response({"error": str(parse_error)}, status=400)
        if event.type != "tool-calls":
            return request.make_json_response({"error": "expected tool-calls"}, status=400)
        return request.make_json_response(self._run_tools(request.env(su=True), event))
