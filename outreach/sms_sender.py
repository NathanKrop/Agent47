"""SMS sender via Africa's Talking."""

import asyncio
from typing import Any

from datetime import datetime, timezone, timedelta
import africastalking
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import AT_API_KEY, AT_SENDER_ID, AT_USERNAME, DRY_RUN, SMS_START_HOUR_EAT, SMS_END_HOUR_EAT


class SmsSender:
    """
    Sends SMS via Africa's Talking API.
    Formats message using SMS_TEMPLATES.
    Handles Kenyan number formatting.
    """

    def __init__(
        self,
        username: str | None = None,
        api_key: str | None = None,
        sender_id: str | None = None,
    ):
        self.username = username or AT_USERNAME
        self.api_key = api_key or AT_API_KEY
        self.sender_id = sender_id or AT_SENDER_ID
        self._initialized = False

    def _init_sdk(self) -> None:
        if not self._initialized and self.api_key:
            africastalking.initialize(self.username, self.api_key)
            self._initialized = True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=120))
    async def send(self, to: str, message: str) -> dict[str, Any]:
        # Validate allowed SMS hours in EAT (UTC+3)
        eat_tz = timezone(timedelta(hours=3))
        current_eat = datetime.now(timezone.utc).astimezone(eat_tz)
        if not (SMS_START_HOUR_EAT <= current_eat.hour < SMS_END_HOUR_EAT):
            raise ValueError(
                f"SMS outreach blocked outside allowed hours ({SMS_START_HOUR_EAT:02d}:00-{SMS_END_HOUR_EAT:02d}:00 EAT). "
                f"Current EAT: {current_eat.strftime('%H:%M')}"
            )

        if DRY_RUN:
            logger.info(f"[DRY RUN] SMS sent to {to}: {message}")
            return {
                "channel": "sms",
                "status": "sent",
                "delivery_status": "Success",
                "raw": {"dry_run": True},
            }

        if not self.api_key:
            raise RuntimeError("Africa's Talking API not configured")

        self._init_sdk()
        sms = africastalking.SMS
        phone = to if to.startswith("+") else f"+{to.lstrip('+')}"

        result = await asyncio.to_thread(
            sms.send, message, [phone], self.sender_id
        )

        logger.info(f"SMS sent to {phone}")
        recipients = result.get("SMSMessageData", {}).get("Recipients", [])
        status = recipients[0].get("status") if recipients else "Unknown"

        return {
            "channel": "sms",
            "status": "sent" if status in ("Success", "Sent") else "failed",
            "delivery_status": status,
            "raw": result,
        }
