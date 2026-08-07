"""Headless Playwright scraper for Google Maps listings."""

import asyncio
import random
import re
from typing import Any
from urllib.parse import quote_plus

from fake_useragent import UserAgent
from loguru import logger
from playwright.async_api import Browser, Page, async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import HEADLESS, PROXY_URL
from discovery.website_checker import WebsiteChecker


class GoogleMapsScraper:
    """
    Scrapes Google Maps search results for a given query + location.
    Detects whether a listing has a website by checking website button presence.
    Returns list of RawListing dicts.
    """

    def __init__(self):
        self._ua = UserAgent()
        self._website_checker = WebsiteChecker()

    @retry(stop=stop_after_attempt(1))
    async def search(self, category: str, location: str, max_results: int = 50) -> list[dict[str, Any]]:
        query = f"{category} in {location}, Kenya"
        url = f"https://www.google.com/maps/search/{quote_plus(query)}"
        logger.info(f"Scraping Maps: {query}")

        listings: list[dict[str, Any]] = []
        async with async_playwright() as pw:
            browser = await self._launch_browser(pw)
            try:
                page = await browser.new_page(user_agent=self._ua.random)
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await self._random_delay()

                await self._scroll_results(page, max_results)
                cards = await page.locator('div[role="feed"] > div > div > a[href*="/maps/place"]').all()

                seen_names: set[str] = set()
                for card in cards[:max_results]:
                    try:
                        listing = await self._extract_listing_data(page, card)
                        if listing and listing.get("name") and listing["name"] not in seen_names:
                            seen_names.add(listing["name"])
                            listings.append(listing)
                    except Exception as exc:
                        logger.debug(f"Failed to extract listing: {exc}")
                    await self._random_delay(1, 3)

            finally:
                await browser.close()

        logger.info(f"Found {len(listings)} listings for {query}")
        return listings

    async def _launch_browser(self, pw) -> Browser:
        launch_args: dict[str, Any] = {"headless": HEADLESS}
        if PROXY_URL:
            launch_args["proxy"] = {"server": PROXY_URL}
        return await pw.chromium.launch(**launch_args)

    async def _scroll_results(self, page: Page, max_results: int) -> None:
        feed = page.locator('div[role="feed"]')
        prev_count = 0
        for _ in range(15):
            await feed.evaluate("el => el.scrollTop = el.scrollHeight")
            await asyncio.sleep(random.uniform(1.5, 3.0))
            cards = await page.locator('div[role="feed"] > div > div > a[href*="/maps/place"]').count()
            if cards >= max_results or cards == prev_count:
                break
            prev_count = cards

    async def _extract_listing_data(self, page: Page, card) -> dict[str, Any]:
        name = await self._safe_text(card, 'div[class*="fontHeadline"]')
        if not name:
            name = await card.inner_text()
            name = name.split("\n")[0].strip() if name else ""

        href = await card.get_attribute("href") or ""
        has_website = await self._has_website_button(card)

        listing: dict[str, Any] = {
            "name": name,
            "address": "",
            "phone": "",
            "rating": None,
            "review_count": 0,
            "website_url": None,
            "has_website": has_website,
            "google_maps_url": href if href.startswith("http") else f"https://www.google.com{href}",
        }

        await card.click()
        await self._random_delay(1, 2)

        panel = page.locator('div[role="main"]')
        listing["address"] = await self._safe_text(panel, 'button[data-item-id="address"]')
        listing["phone"] = await self._safe_text(panel, 'button[data-item-id*="phone"]')

        rating_text = await self._safe_text(panel, 'div[class*="fontDisplayLarge"]')
        if rating_text:
            try:
                listing["rating"] = float(rating_text.replace(",", "."))
            except ValueError:
                pass

        reviews_text = await self._safe_text(panel, 'div[class*="fontBodyMedium"]')
        review_match = re.search(r"([\d,]+)\s*review", reviews_text or "", re.I)
        if review_match:
            listing["review_count"] = int(review_match.group(1).replace(",", ""))

        if has_website:
            website_link = panel.locator('a[data-item-id="authority"]')
            if await website_link.count() > 0:
                listing["website_url"] = await website_link.first.get_attribute("href")

        return listing

    async def _has_website_button(self, card) -> bool:
        text = (await card.inner_text()).lower()
        if "website" in text:
            return True
        globe = card.locator('[data-item-id="authority"], a[aria-label*="Website"]')
        return await globe.count() > 0

    async def _safe_text(self, locator, selector: str) -> str:
        try:
            el = locator.locator(selector).first
            if await el.count() > 0:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return ""

    async def _random_delay(self, low: float = 2.0, high: float = 5.0) -> None:
        await asyncio.sleep(random.uniform(low, high))
