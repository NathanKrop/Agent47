"""Extract social media links from listings and websites."""

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from loguru import logger

SOCIAL_PATTERNS = {
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[\w.\-/]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[\w.\-/]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[\w.\-/]+", re.I),
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/[\w.\-/]+", re.I),
}


class SocialExtractor:
    """Extract Facebook/Instagram and other social links."""

    def extract_from_text(self, text: str) -> dict[str, str]:
        if not text:
            return {}
        found = {}
        for platform, pattern in SOCIAL_PATTERNS.items():
            match = pattern.search(text)
            if match:
                found[platform] = match.group(0).rstrip("/")
        return found

    async def extract_from_website(self, url: str) -> dict[str, str]:
        if not url:
            return {}
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; KenyaOutreachBot/1.0)"},
                )
                if response.status_code != 200:
                    return {}
                return self.extract_from_text(response.text)
        except Exception as exc:
            logger.debug(f"Social extract failed for {url}: {exc}")
            return {}

    async def enrich_listing(self, listing: dict[str, Any]) -> dict[str, Any]:
        social = self.extract_from_text(str(listing))
        if listing.get("website_url"):
            social.update(await self.extract_from_website(listing["website_url"]))
        listing["social_links"] = social
        return listing
