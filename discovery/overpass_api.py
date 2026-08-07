"""
Free business discovery via OpenStreetMap Overpass API.
No API key. No credit card. No rate-limit beyond fair-use.
Covers all 47 Kenyan counties with real business data.
"""

from typing import Any

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.categories import GEO_TILES

# Map our category names → OSM tags
OSM_CATEGORY_MAP: dict[str, list[dict[str, str]]] = {
    "plumber":          [{"craft": "plumber"}],
    "electrician":      [{"craft": "electrician"}],
    "clinic":           [{"amenity": "clinic"}, {"amenity": "doctors"}],
    "pharmacy":         [{"amenity": "pharmacy"}],
    "salon":            [{"shop": "hairdresser"}, {"shop": "beauty"}],
    "restaurant":       [{"amenity": "restaurant"}, {"amenity": "fast_food"}],
    "hardware store":   [{"shop": "hardware"}, {"shop": "doityourself"}],
    "school":           [{"amenity": "school"}],
    "church":           [{"amenity": "place_of_worship", "religion": "christian"}],
    "mechanic":         [{"shop": "car_repair"}, {"craft": "car_repair"}],
    "real estate agent":[{"office": "estate_agent"}],
    "hotel":            [{"tourism": "hotel"}, {"tourism": "guest_house"}],
    "supermarket":      [{"shop": "supermarket"}],
    "law firm":         [{"office": "lawyer"}],
    "accounting firm":  [{"office": "accountant"}],
    "cleaning service": [{"craft": "cleaning"}],
    "catering":         [{"craft": "caterer"}],
    "gym":              [{"leisure": "fitness_centre"}, {"leisure": "sports_centre"}],
    "event planner":    [{"office": "event_management"}],
    "printing shop":    [{"shop": "copyshop"}, {"craft": "printer"}],
    "photographer":     [{"shop": "photo"}],
    "tailor":           [{"craft": "tailor"}, {"shop": "clothes"}],
}

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


class OverpassClient:
    """
    Queries OpenStreetMap Overpass API for businesses in a Kenyan county.
    Completely free — no API key required.
    Falls back across multiple public Overpass mirrors automatically.
    """

    def __init__(self):
        self._endpoint_index = 0

    @property
    def _endpoint(self) -> str:
        return OVERPASS_ENDPOINTS[self._endpoint_index % len(OVERPASS_ENDPOINTS)]

    def _rotate_endpoint(self) -> None:
        self._endpoint_index += 1

    def _build_query(self, category: str, bbox: tuple[float, float, float, float]) -> str:
        """Build an Overpass QL query for a category inside a bounding box."""
        south, west, north, east = bbox
        bbox_str = f"{south},{west},{north},{east}"

        tag_filters = OSM_CATEGORY_MAP.get(category, [])
        if not tag_filters:
            # Generic fallback: search by name keyword
            return f"""
[out:json][timeout:30];
(
  node["name"~"{category}",i]({bbox_str});
  way["name"~"{category}",i]({bbox_str});
);
out center tags 50;
"""
        parts = []
        for tags in tag_filters:
            tag_str = "".join(f'["{k}"="{v}"]' for k, v in tags.items())
            parts.append(f'  node{tag_str}({bbox_str});')
            parts.append(f'  way{tag_str}({bbox_str});')

        return f"""
[out:json][timeout:30];
(
{"".join(parts)}
);
out center tags 50;
"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=3, max=30))
    async def _query(self, ql: str) -> dict[str, Any]:
        headers = {"User-Agent": "KenyaOutreachAgent/1.0 (contact: nathan@yourdomain.com)"}
        async with httpx.AsyncClient(timeout=40.0, headers=headers) as client:
            response = await client.post(self._endpoint, data={"data": ql})
            response.raise_for_status()
            return response.json()

    async def search(
        self,
        category: str,
        county: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Return normalised listing dicts for a category + county."""
        bboxes = GEO_TILES.get(county)
        if not bboxes:
            logger.warning(f"No bounding box for county: {county}")
            return []

        results: list[dict[str, Any]] = []

        for bbox in bboxes:
            if len(results) >= max_results:
                break
            try:
                ql = self._build_query(category, bbox)
                data = await self._query(ql)
                for element in data.get("elements", []):
                    listing = self._element_to_listing(element, category, county)
                    if listing:
                        results.append(listing)
                    if len(results) >= max_results:
                        break
            except Exception as exc:
                logger.warning(f"Overpass query failed for {category}/{county}: {exc}")
                self._rotate_endpoint()

        logger.info(f"Overpass: {len(results)} results for {category} in {county}")
        return results

    def _element_to_listing(
        self, element: dict[str, Any], category: str, county: str
    ) -> dict[str, Any] | None:
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("brand")
        if not name:
            return None

        # Coordinates: nodes have lat/lon directly; ways have a center
        if element["type"] == "node":
            lat = element.get("lat")
            lon = element.get("lon")
        else:
            center = element.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

        osm_id = element.get("id")
        osm_type = element.get("type", "node")
        maps_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"

        phone = (
            tags.get("phone")
            or tags.get("contact:phone")
            or tags.get("contact:mobile")
            or ""
        )
        email = tags.get("email") or tags.get("contact:email") or ""
        website = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
        address_parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:city", "") or tags.get("addr:town", "") or county,
        ]
        address = ", ".join(p for p in address_parts if p) or county

        return {
            "name": name.strip(),
            "address": address,
            "county": county,
            "category": category,
            "phone": phone.strip(),
            "email": email.strip(),
            "website_url": website.strip() or None,
            "has_website": bool(website.strip()),
            "rating": None,
            "review_count": 0,
            "google_maps_url": maps_url,
            "lat": lat,
            "lon": lon,
            "source": "overpass",
        }
