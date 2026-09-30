import hashlib
import json

from odoo import api, fields, models


class InternshipVapiEvent(models.Model):
    """Inbox of raw Vapi webhook events: stored first, processed once."""

    _name = "internship.vapi.event"
    _description = "Vapi Webhook Event"
    _order = "received_at desc, id desc"

    event_type = fields.Char(required=True, index=True)
    external_call_id = fields.Char(index=True)
    payload = fields.Json()
    hash = fields.Char(string="Hash", required=True, index=True)
    payload_hash = fields.Char(string="Payload Hash (19.0.2.0)", deprecated="Replaced by hash in 19.0.2.1")
    received_at = fields.Datetime(default=fields.Datetime.now, required=True)
    processed = fields.Boolean(index=True)
    error = fields.Text()
    call_log_id = fields.Many2one("internship.call.log", index=True, ondelete="set null")

    _unique_event = models.Constraint(
        "unique(external_call_id, event_type, hash)", "This webhook event was already received."
    )

    @api.model
    def _hash(self, payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    @api.model
    def _store(self, event_type, external_call_id, payload):
        """Return (event, is_new). Duplicates (Vapi retries) return the existing row."""
        digest = self._hash(payload)
        existing = self.search(
            [
                ("external_call_id", "=", external_call_id),
                ("event_type", "=", event_type),
                ("hash", "=", digest),
            ],
            limit=1,
        )
        if existing:
            return existing, False
        return self.create(
            {"event_type": event_type, "external_call_id": external_call_id, "payload": payload, "hash": digest}
        ), True
