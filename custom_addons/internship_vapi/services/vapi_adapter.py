"""All knowledge of Vapi's webhook payload shapes lives here.

If Vapi changes its server-message format, only this file should need to change.
Reference: https://docs.vapi.ai/server-url/events
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

# Vapi call status -> internship.call.log status
STATUS_MAP = {
    "scheduled": "scheduled",
    "queued": "queued",
    "ringing": "ringing",
    "in-progress": "connected",
    "forwarding": "connected",
    "ended": "completed",
}
NO_ANSWER_REASONS = {"customer-did-not-answer", "customer-busy", "voicemail", "no-answer"}
FAILED_REASON_PREFIXES = ("pipeline-error", "twilio-failed", "vonage-failed", "call.start.error", "assistant-error")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class VapiEvent:
    type: str
    call_id: str | None = None
    call_type: str = ""
    status: str | None = None
    metadata: dict = field(default_factory=dict)
    customer_number: str | None = None
    assistant_id: str | None = None
    phone_number_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int = 0
    ended_reason: str | None = None
    summary: str | None = None
    transcript: str | None = None
    recording_url: str | None = None
    structured_data: dict = field(default_factory=dict)
    cost: float = 0.0
    tool_calls: list = field(default_factory=list)

    @property
    def direction(self):
        return "inbound" if "inbound" in (self.call_type or "").lower() else "outbound"

    def log_status(self):
        """Map to an internship.call.log status."""
        if self.type == "end-of-call-report":
            reason = (self.ended_reason or "").lower()
            if reason in NO_ANSWER_REASONS:
                return "no_answer"
            if reason.startswith(FAILED_REASON_PREFIXES):
                return "failed"
            return "completed"
        return STATUS_MAP.get(self.status or "", None)


class PayloadError(ValueError):
    """The payload is not a Vapi server message we understand."""


def _parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed


def _dict(value):
    return value if isinstance(value, dict) else {}


def _arguments(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def parse_tool_calls(message):
    """Accept both documented shapes: {id, name, parameters} and OpenAI-style {id, function: {name, arguments}}."""
    calls = []
    for item in message.get("toolCallList") or []:
        if not isinstance(item, dict):
            continue
        function = _dict(item.get("function"))
        name = item.get("name") or function.get("name")
        arguments = item.get("parameters") if "parameters" in item else function.get("arguments")
        if item.get("id") and name:
            calls.append(ToolCall(id=str(item["id"]), name=str(name), arguments=_arguments(arguments)))
    if not calls:
        for item in message.get("toolWithToolCallList") or []:
            tool_call = _dict(_dict(item).get("toolCall"))
            function = _dict(tool_call.get("function"))
            name = _dict(item).get("name") or function.get("name")
            arguments = tool_call.get("parameters") if "parameters" in tool_call else function.get("arguments")
            if tool_call.get("id") and name:
                calls.append(ToolCall(id=str(tool_call["id"]), name=str(name), arguments=_arguments(arguments)))
    return calls


def parse(payload):
    """Turn a webhook body into a VapiEvent. Raises PayloadError on malformed input."""
    if not isinstance(payload, dict):
        raise PayloadError("invalid_json")
    message = payload.get("message", payload)
    if not isinstance(message, dict) or not message.get("type"):
        raise PayloadError("invalid_message")
    call = message.get("call") or {}
    if not isinstance(call, dict):
        raise PayloadError("invalid_call")
    artifact = _dict(message.get("artifact"))
    analysis = _dict(message.get("analysis"))
    metadata = call.get("metadata") or message.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise PayloadError("invalid_call_metadata")
    started = _parse_datetime(call.get("startedAt") or message.get("startedAt"))
    ended = _parse_datetime(call.get("endedAt") or message.get("endedAt"))
    duration = int((ended - started).total_seconds()) if started and ended else 0
    if not duration:
        try:
            duration = int(float(message.get("durationSeconds") or call.get("durationSeconds") or 0))
        except (TypeError, ValueError):
            duration = 0
    recording = artifact.get("recording")
    recording_url = (
        message.get("recordingUrl")
        or artifact.get("recordingUrl")
        or (_dict(recording).get("stereoUrl") or _dict(recording).get("url") if isinstance(recording, dict) else None)
        or call.get("recordingUrl")
    )
    try:
        cost = float(message.get("cost") or call.get("cost") or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    structured = analysis.get("structuredData") or artifact.get("structuredData") or {}
    return VapiEvent(
        type=str(message["type"]),
        call_id=str(call["id"]) if call.get("id") else None,
        call_type=str(call.get("type") or ""),
        status=message.get("status") or call.get("status"),
        metadata=metadata,
        customer_number=_dict(call.get("customer")).get("number") or _dict(message.get("customer")).get("number"),
        assistant_id=call.get("assistantId"),
        phone_number_id=call.get("phoneNumberId"),
        started_at=started,
        ended_at=ended,
        duration_seconds=max(0, duration),
        ended_reason=message.get("endedReason") or call.get("endedReason"),
        summary=analysis.get("summary") or message.get("summary") or call.get("summary"),
        transcript=artifact.get("transcript") or message.get("transcript"),
        recording_url=recording_url,
        structured_data=structured if isinstance(structured, dict) else {},
        cost=cost,
        tool_calls=parse_tool_calls(message) if message["type"] == "tool-calls" else [],
    )


def tool_results_response(results):
    """Body Vapi expects back for tool-calls: {"results": [{"toolCallId", "name", "result"}]}."""
    return {
        "results": [
            {"toolCallId": call_id, "name": name, "result": result if isinstance(result, str) else json.dumps(result)}
            for call_id, name, result in results
        ]
    }
