"""Route outreach to the best available channel per lead."""

from typing import Any

from loguru import logger

from config.settings import OUTREACH_CHANNELS
from config.agent_state import get_channels, require_verified_contact
from config.templates import (
    WHATSAPP_TEMPLATES,
    SMS_TEMPLATES,
    render_template,
    select_sms_template,
    select_whatsapp_template,
)
from database.repository import add_do_not_contact, is_do_not_contact, log_outreach
from outreach.email_sender import EmailSender
from outreach.rate_limiter import RateLimiter
from outreach.sms_sender import SmsSender
from outreach.whatsapp_sender import WhatsAppSender


class ChannelRouter:
    """
    Decides the best outreach channel for a lead:
    1. WhatsApp (preferred — if phone available)
    2. SMS (fallback — if phone available)
    3. Email (fallback — if email available)
    """

    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.whatsapp = WhatsAppSender()
        self.sms = SmsSender()
        self.email = EmailSender()
        self._tried_channels: dict[str, set[str]] = {}

    async def route_and_send(self, listing: dict[str, Any]) -> dict[str, Any]:
        listing_id = listing.get("id", "")
        phone = listing.get("phone")
        email = listing.get("email")
        tried = self._tried_channels.setdefault(listing_id, set())

        # Read live-tunable settings from the agent control panel state
        channels = get_channels() or OUTREACH_CHANNELS
        require_verified = require_verified_contact()

        for channel in channels:
            if channel in tried:
                continue

            recipient = phone if channel in ("whatsapp", "sms") else email
            if not recipient:
                continue

            # Enforce the "verified contact" gate toggled in the Control Panel
            if require_verified:
                if channel in ("whatsapp", "sms") and not listing.get("phone_verified"):
                    logger.debug(f"Skip {channel}: unverified phone for {listing_id}")
                    continue
                if channel in ("email",) and not listing.get("email_verified"):
                    logger.debug(f"Skip {channel}: unverified email for {listing_id}")
                    continue

            if is_do_not_contact(recipient):
                logger.info(f"Skipping DNC contact: {recipient}")
                return {"channel": channel, "status": "do_not_contact", "recipient": recipient}

            if not await self.rate_limiter.can_send(recipient):
                logger.debug(f"Rate limited: {recipient}")
                continue

            try:
                result = await self._send_via_channel(channel, listing, recipient)
                await self.rate_limiter.record_send(recipient)
                log_outreach(
                    listing_id,
                    channel,
                    result.get("template_name", ""),
                    recipient,
                    result.get("status", "sent"),
                    result.get("error_message"),
                )
                tried.add(channel)
                return result
            except Exception as exc:
                logger.error(f"Outreach failed via {channel}: {exc}")
                await self.rate_limiter.backoff()
                log_outreach(listing_id, channel, "", recipient, "failed", str(exc))
                tried.add(channel)

        return {"channel": None, "status": "failed", "error": "No channel available"}

    async def _send_via_channel(
        self, channel: str, listing: dict[str, Any], recipient: str
    ) -> dict[str, Any]:
        business_name = listing.get("name", "your business")
        website_status = listing.get("website_status", "no_website")

        if channel == "whatsapp":
            template_key = select_whatsapp_template(website_status)
            template = WHATSAPP_TEMPLATES[template_key]
            body = render_template(template["body"], business_name=business_name)
            try:
                return await self.whatsapp.send(
                    recipient,
                    template["name"],
                    {
                        "business_name": business_name,
                        "portfolio_link": (
                            body.split("here: ")[-1].split(" ")[0]
                            if "here: " in body
                            else ""
                        ),
                    },
                )
            except Exception:
                return await self.whatsapp.send_text(recipient, body)

        if channel == "sms":
            template_key = select_sms_template(website_status)
            message = render_template(SMS_TEMPLATES[template_key], business_name=business_name)
            result = await self.sms.send(recipient, message)
            result["template_name"] = template_key
            return result

        if channel == "email":
            return await self.email.send(recipient, listing)

        raise ValueError(f"Unknown channel: {channel}")

    def handle_opt_out(self, contact: str, reason: str = "user_reply") -> None:
        add_do_not_contact(contact, reason)

