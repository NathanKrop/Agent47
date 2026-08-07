"""Google Places API fallback for discovery."""

from typing import Any

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import GOOGLE_PLACES_API_KEY


class PlacesAPIClient:
    """Fallback discovery via Google Places Text Search API."""

    BASE_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or GOOGLE_PLACES_API_KEY

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def search(self, category: str, location: str, max_results: int = 50) -> list[dict[str, Any]]:
        if not self.api_key:
            logger.warning("Google Places API key not configured")
            return []

        query = f"{category} in {location}, Kenya"
        params = {"query": query, "key": self.api_key}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("status") != "OK":
            logger.warning(f"Places API status: {data.get('status')} for {query}")
            return []

        results = []
        for place in data.get("results", [])[:max_results]:
            listing = await self._place_to_listing(place)
            if listing:
                results.append(listing)
        return results

    async def _place_to_listing(self, place: dict[str, Any]) -> dict[str, Any] | None:
        place_id = place.get("place_id")
        details = await self._get_details(place_id) if place_id else {}

        website = details.get("website") or place.get("website")
        return {
            "name": place.get("name", ""),
            "address": place.get("formatted_address", details.get("formatted_address", "")),
            "phone": details.get("formatted_phone_number", ""),
            "rating": place.get("rating"),
            "review_count": place.get("user_ratings_total", 0),
            "website_url": website,
            "has_website": bool(website),
            "google_maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
            "place_id": place_id,
            "source": "places_api",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def _get_details(self, place_id: str) -> dict[str, Any]:
        params = {
            "place_id": place_id,
            "fields": "formatted_phone_number,website,formatted_address",
            "key": self.api_key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.DETAILS_URL, params=params)
            response.raise_for_status()
            data = response.json()
        return data.get("result", {})
