"""WhatsApp Business API sender via BSP."""

from typing import Any

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import WHATSAPP_API_TOKEN, WHATSAPP_API_URL, WHATSAPP_SENDER_ID, DRY_RUN


class WhatsAppSender:
    """
    Sends WhatsApp messages via BSP API (configurable endpoint).
    Uses pre-approved templates with variable substitution.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_token: str | None = None,
        sender_id: str | None = None,
    ):
        self.api_url = api_url or WHATSAPP_API_URL
        self.api_token = api_token or WHATSAPP_API_TOKEN
        self.sender_id = sender_id or WHATSAPP_SENDER_ID

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=120))
    async def send(self, to: str, template_name: str, variables: dict[str, Any]) -> dict[str, Any]:
        if DRY_RUN:
            logger.info(f"[DRY RUN] WhatsApp Template sent to {to}: {template_name} with variables: {variables}")
            return {
                "channel": "whatsapp",
                "status": "sent",
                "message_id": "dry-run-whatsapp-template-id",
                "raw": {"dry_run": True},
            }

        if not self.api_url or not self.api_token:
            raise RuntimeError("WhatsApp API not configured")

        endpoint = self._resolve_endpoint()
        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en_US"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(v)} for v in variables.values()
                        ],
                    }
                ],
            },
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        logger.info(f"WhatsApp sent to {to}: {template_name}")
        return {
            "channel": "whatsapp",
            "status": "sent",
            "message_id": data.get("messages", [{}])[0].get("id") or data.get("id") or data.get("message_id"),
            "raw": data,
        }

    def _resolve_endpoint(self) -> str:
        if self.api_url.startswith("https://graph.facebook.com/"):
            base = self.api_url.rstrip("/")
            if not self.sender_id:
                raise RuntimeError("WHATSAPP_SENDER_ID must be set for Meta Graph API")
            return f"{base}/{self.sender_id}/messages"
        return self.api_url

    async def send_text(self, to: str, message: str) -> dict[str, Any]:
        """Send plain text when templates aren't approved (sandbox/dev)."""
        if DRY_RUN:
            logger.info(f"[DRY RUN] WhatsApp Plain Text sent to {to}: {message}")
            return {"channel": "whatsapp", "status": "sent", "message_id": "dry-run-whatsapp-text-id", "raw": {"dry_run": True}}

        if not self.api_url or not self.api_token:
            raise RuntimeError("WhatsApp API not configured")

        endpoint = self._resolve_endpoint()
        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"body": message},
        }
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return {"channel": "whatsapp", "status": "sent", "message_id": data.get("messages", [{}])[0].get("id") or data.get("id"), "raw": data}
