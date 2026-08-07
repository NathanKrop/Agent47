"""Email sender via SendGrid."""

import asyncio
from typing import Any

from loguru import logger
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import FROM_EMAIL, FROM_NAME, SENDGRID_API_KEY, DRY_RUN
from config.templates import EMAIL_TEMPLATES, render_template, select_email_template


class EmailSender:
    """
    Sends personalised emails via SendGrid.
    Uses EMAIL_TEMPLATES with variable substitution.
    """

    def __init__(
        self,
        api_key: str | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
    ):
        self.api_key = api_key or SENDGRID_API_KEY
        self.from_email = from_email or FROM_EMAIL
        self.from_name = from_name or FROM_NAME

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=120))
    async def send(self, to: str, listing: dict[str, Any]) -> dict[str, Any]:
        template_key = select_email_template(listing.get("website_status", "no_website"))
        template = EMAIL_TEMPLATES[template_key]

        body = render_template(
            template["body"],
            business_name=listing.get("name", ""),
            contact_name=listing.get("contact_name") or listing.get("name", ""),
            category=listing.get("category", "business"),
            location=listing.get("county") or listing.get("address", "Kenya"),
        )
        subject = render_template(
            template["subject"],
            business_name=listing.get("name", ""),
            category=listing.get("category", "business"),
            location=listing.get("county") or "Kenya",
        )

        if DRY_RUN:
            logger.info(f"[DRY RUN] Email sent to {to} for {listing.get('name')}: Subject: {subject.strip()}")
            return {
                "channel": "email",
                "status": "sent",
                "status_code": 202,
                "template_name": template_key,
            }

        if not self.api_key:
            raise RuntimeError("SendGrid API not configured")

        message = Mail(
            from_email=(self.from_email, self.from_name),
            to_emails=to,
            subject=subject.strip(),
            plain_text_content=body.strip(),
        )
        message.reply_to = self.from_email

        client = SendGridAPIClient(self.api_key)
        response = await asyncio.to_thread(client.send, message)

        logger.info(f"Email sent to {to} for {listing.get('name')}")
        return {
            "channel": "email",
            "status": "sent" if response.status_code in (200, 202) else "failed",
            "status_code": response.status_code,
            "template_name": template_key,
        }
