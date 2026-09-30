"""Thin Vapi REST client. Never logs the API key."""

import logging
import time

import requests

_logger = logging.getLogger(__name__)

API_BASE = "https://api.vapi.ai"
TIMEOUT = 10
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_TRIES = 3


class VapiError(Exception):
    pass


class VapiClient:
    def __init__(self, env):
        params = env["ir.config_parameter"].sudo()
        self.api_key = params.get_param("internship_vapi.api_key")
        self.base_url = params.get_param("internship_vapi.api_base", API_BASE).rstrip("/")
        if not self.api_key:
            raise VapiError("The Vapi API key is not configured (CRM > Configuration > Settings > Voice Assistant).")

    def _request(self, method, path, json=None):
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        delay = 1.0
        for attempt in range(1, MAX_TRIES + 1):
            try:
                response = requests.request(method, url, json=json, headers=headers, timeout=TIMEOUT)
            except requests.RequestException as error:
                _logger.warning("Vapi %s %s failed (attempt %s): %s", method, path, attempt, type(error).__name__)
                if attempt == MAX_TRIES:
                    raise VapiError(f"Vapi is unreachable: {type(error).__name__}") from error
            else:
                _logger.info("Vapi %s %s -> HTTP %s (attempt %s)", method, path, response.status_code, attempt)
                if response.status_code not in RETRY_STATUSES:
                    if response.status_code >= 400:
                        raise VapiError(f"Vapi returned HTTP {response.status_code}: {response.text[:300]}")
                    return response.json() if response.content else {}
                if attempt == MAX_TRIES:
                    raise VapiError(f"Vapi returned HTTP {response.status_code} after {MAX_TRIES} attempts")
            time.sleep(delay)
            delay *= 2
        raise VapiError("unreachable")

    def create_call(self, customer_number, assistant_id, metadata=None, variable_values=None, phone_number_id=None):
        body = {
            "assistantId": assistant_id,
            "phoneNumberId": phone_number_id,
            "customer": {"number": customer_number},
            "metadata": metadata or {},
        }
        if variable_values:
            body["assistantOverrides"] = {"variableValues": variable_values}
        return self._request("POST", "/call", json=body)

    def get_call(self, call_id):
        return self._request("GET", f"/call/{call_id}")

    def get_assistant(self, assistant_id):
        return self._request("GET", f"/assistant/{assistant_id}")

    def list_assistants(self):
        return self._request("GET", "/assistant?limit=1")
