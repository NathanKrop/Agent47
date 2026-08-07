"""Extract email addresses from listings and websites."""

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

IGNORED_EMAILS = {
    "example.com",
    "email.com",
    "domain.com",
    "sentry.io",
    "wixpress.com",
    "wordpress.com",
}


class EmailExtractor:
    """
    Extracts emails from:
    1. Google listing description
    2. Business website contact/about pages
    3. Facebook page about section
    """

    CONTACT_PATHS = ["/contact", "/contact-us", "/about", "/about-us", ""]

    def extract_from_text(self, text: str) -> list[str]:
        if not text:
            return []
        emails = EMAIL_PATTERN.findall(text)
        return self._filter_valid(emails)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def extract_from_website(self, url: str) -> list[str]:
        if not url:
            return []

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        found: set[str] = set()
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for path in self.CONTACT_PATHS:
                page_url = urljoin(url.rstrip("/") + "/", path.lstrip("/"))
                try:
                    response = await client.get(
                        page_url,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; KenyaOutreachBot/1.0)"},
                    )
                    if response.status_code == 200:
                        found.update(self.extract_from_text(response.text))
                        soup = BeautifulSoup(response.text, "lxml")
                        for mailto in soup.select('a[href^="mailto:"]'):
                            href = mailto.get("href", "")
                            email = href.replace("mailto:", "").split("?")[0]
                            found.update(self.extract_from_text(email))
                except Exception as exc:
                    logger.debug(f"Email scrape failed for {page_url}: {exc}")

        return self._filter_valid(list(found))

    async def enrich_listing(self, listing: dict[str, Any]) -> dict[str, Any]:
        """Add email to listing from available sources."""
        emails: set[str] = set()

        for field in ("description", "address", "name"):
            emails.update(self.extract_from_text(listing.get(field, "") or ""))

        if listing.get("email"):
            emails.update(self.extract_from_text(listing["email"]))

        if listing.get("website_url"):
            emails.update(await self.extract_from_website(listing["website_url"]))

        if emails:
            listing["email"] = sorted(emails)[0]
            listing["all_emails"] = sorted(emails)
        return listing

    def _filter_valid(self, emails: list[str]) -> list[str]:
        valid = []
        for email in emails:
            email = email.lower().strip()
            domain = email.split("@")[-1] if "@" in email else ""
            if domain and domain not in IGNORED_EMAILS and not domain.endswith(".png"):
                valid.append(email)
        return sorted(set(valid))
