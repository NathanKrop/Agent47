"""Website quality classifier for business listings."""

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

PARKED_KEYWORDS = [
    "domain is for sale",
    "buy this domain",
    "parked free",
    "godaddy",
    "sedo parking",
    "this domain may be for sale",
    "domain parking",
    "hugedomains",
    "namecheap",
    "coming soon",
    "under construction",
]

PLACEHOLDER_PATTERNS = [
    r"sites\.google\.com/view/",
    r"business\.site",
    r"wixsite\.com",
    r"facebook\.com",
    r"instagram\.com",
    r"linktr\.ee",
]


class WebsiteChecker:
    """
    Classifies a website URL into one of:
    - NO_WEBSITE: no URL found
    - PLACEHOLDER: Google Business placeholder / default page
    - BROKEN: 4xx/5xx response or DNS failure
    - PARKED: domain parked
    - POOR: loads but heuristics show it's bad
    - GOOD: functional website
    """

    async def classify(self, url: str | None) -> str:
        if not url or not url.strip():
            return "NO_WEBSITE"

        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        if self._is_placeholder(url):
            return "PLACEHOLDER"

        try:
            html, status_code, load_time = await self._fetch(url)
        except Exception as exc:
            logger.debug(f"Website fetch failed for {url}: {exc}")
            return "BROKEN"

        if status_code >= 400:
            return "BROKEN"

        if self._is_parked(html):
            return "PARKED"

        if self._is_poor_quality(html, load_time):
            return "POOR"

        return "GOOD"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def _fetch(self, url: str) -> tuple[str, int, float]:
        import time

        start = time.monotonic()
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; KenyaOutreachBot/1.0)"},
        ) as client:
            response = await client.get(url)
            load_time = time.monotonic() - start
            return response.text[:50000], response.status_code, load_time

    def _is_parked(self, html: str) -> bool:
        lower = html.lower()
        return any(keyword in lower for keyword in PARKED_KEYWORDS)

    def _is_placeholder(self, url: str) -> bool:
        lower = url.lower()
        return any(re.search(pattern, lower) for pattern in PLACEHOLDER_PATTERNS)

    def _is_poor_quality(self, html: str, load_time: float) -> bool:
        lower = html.lower()
        has_viewport = 'name="viewport"' in lower or "viewport" in lower
        is_slow = load_time > 5.0
        is_tiny = len(html) < 500
        no_mobile = not has_viewport
        old_tech = "<frameset" in lower or "marquee" in lower
        return is_slow or is_tiny or no_mobile or old_tech

    async def classify_listing(self, listing: dict[str, Any]) -> dict[str, Any]:
        """Classify website for a listing dict and attach status."""
        url = listing.get("website_url")
        if not listing.get("has_website") and not url:
            status = "NO_WEBSITE"
        else:
            status = await self.classify(url)
        listing["website_status"] = status.lower() if isinstance(status, str) else status
        return listing
