import hmac
from datetime import datetime, timezone

from odoo import fields, http
from odoo.http import request


class InternshipCallTrackingWebhook(http.Controller):
    @http.route(
        "/internship/call-tracking/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def receive_call_report(self, **kwargs):
        parameters = request.env["ir.config_parameter"].sudo()
        expected_token = parameters.get_param("internship_vapi.webhook_token")
        authorization = request.httprequest.headers.get("Authorization", "")
        supplied_token = authorization.removeprefix("Bearer ")
        if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
            return request.make_json_response({"error": "unauthorized"}, status=401)

        payload = request.httprequest.get_json(silent=True)
        if not isinstance(payload, dict):
            return request.make_json_response({"error": "invalid_json"}, status=400)
        message = payload.get("message", payload)
        if not isinstance(message, dict):
            return request.make_json_response({"error": "invalid_message"}, status=400)
        if message.get("type") != "end-of-call-report":
            return request.make_json_response({"status": "ignored"}, status=202)

        call = message.get("call") or {}
        if not isinstance(call, dict):
            return request.make_json_response({"error": "invalid_call"}, status=400)
        external_call_id = call.get("id")
        if not external_call_id:
            return request.make_json_response({"error": "missing_call_id"}, status=400)

        call_model = request.env["internship.call.log"].sudo()
        existing = call_model.search([("external_call_id", "=", str(external_call_id))], limit=1)
        metadata = call.get("metadata") or message.get("metadata") or {}
        artifact = message.get("artifact") or {}
        analysis = message.get("analysis") or {}
        if not isinstance(metadata, dict) or not isinstance(artifact, dict) or not isinstance(analysis, dict):
            return request.make_json_response({"error": "invalid_call_metadata"}, status=400)
        started_at = self._parse_datetime(call.get("startedAt"))
        ended_at = self._parse_datetime(call.get("endedAt"))
        duration = max(0, int((ended_at - started_at).total_seconds())) if started_at and ended_at else 0
        if not duration:
            try:
                duration = max(0, int(call.get("durationSeconds") or message.get("durationSeconds") or 0))
            except (TypeError, ValueError):
                duration = 0

        call_type = call.get("type", "")
        values = {
            "name": "VAPI-%s" % external_call_id,
            "external_call_id": str(external_call_id),
            "call_datetime": started_at or fields.Datetime.now(),
            "call_type": "inbound" if "inbound" in call_type.lower() else "outbound",
            "status": "completed",
            "duration_seconds": duration,
            "summary": analysis.get("summary") or call.get("summary"),
            "recording_url": message.get("recordingUrl") or artifact.get("recordingUrl") or call.get("recordingUrl"),
            "student_id": self._relation_id("internship.student", metadata.get("student_id")),
            "opportunity_id": self._relation_id("internship.opportunity", metadata.get("opportunity_id")),
        }
        if existing:
            existing.write(values)
            record = existing
        else:
            record = call_model.create(values)
        return request.make_json_response({"status": "ok", "record_id": record.id})

    @staticmethod
    def _parse_datetime(value):
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            return False
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _relation_id(model_name, raw_id):
        if not raw_id:
            return False
        try:
            record_id = int(raw_id)
        except (TypeError, ValueError):
            return False
        record = request.env[model_name].sudo().browse(record_id).exists()
        return record.id or False