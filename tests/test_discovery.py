"""Discovery module tests."""

from unittest.mock import AsyncMock, patch

import pytest

from config.categories import GEO_TILES, KENYA_COUNTIES
from discovery.geo_tiles import county_count, generate_search_jobs, get_priority_jobs
from discovery.overpass_api import OSM_CATEGORY_MAP, OverpassClient
from discovery.website_checker import WebsiteChecker


def test_geo_tiles_covers_all_47_counties():
    assert len(KENYA_COUNTIES) == 47
    assert county_count() == 47
    for county in KENYA_COUNTIES:
        assert county in GEO_TILES
        assert len(GEO_TILES[county]) >= 1


def test_generate_search_jobs_cross_product():
    jobs = generate_search_jobs(["plumber"], ["Nairobi", "Mombasa"])
    assert len(jobs) == 2
    locations = {j["location"] for j in jobs}
    assert locations == {"Nairobi", "Mombasa"}


def test_priority_jobs_pilot_scope():
    jobs = get_priority_jobs()
    counties = {j["county"] for j in jobs}
    assert counties <= {"Nairobi", "Mombasa"}
    assert len(jobs) > 0


@pytest.mark.asyncio
async def test_website_checker_no_website():
    checker = WebsiteChecker()
    assert await checker.classify(None) == "NO_WEBSITE"
    assert await checker.classify("") == "NO_WEBSITE"


@pytest.mark.asyncio
async def test_website_checker_placeholder():
    checker = WebsiteChecker()
    assert checker._is_placeholder("https://sites.google.com/view/my-business") is True
    assert checker._is_placeholder("https://www.facebook.com/mybiz") is True


def test_website_checker_parked_detection():
    checker = WebsiteChecker()
    html = "<html><body>This domain is for sale. Buy this domain today.</body></html>"
    assert checker._is_poor_quality(html, 1.0) or checker._is_parked(html)


@pytest.mark.asyncio
async def test_website_checker_poor_quality():
    checker = WebsiteChecker()
    tiny_html = "<html><body>Hi</body></html>"
    assert checker._is_poor_quality(tiny_html, 1.0) is True


def test_overpass_category_map_covers_all_targets():
    from config.categories import TARGET_CATEGORIES
    for cat in TARGET_CATEGORIES:
        assert cat in OSM_CATEGORY_MAP, f"Missing OSM mapping for category: {cat}"


def test_overpass_builds_valid_query():
    client = OverpassClient()
    ql = client._build_query("clinic", (-1.3969, 36.6500, -1.1632, 37.1028))
    assert "amenity" in ql
    assert "-1.3969" in ql


def test_overpass_element_to_listing_missing_name_returns_none():
    client = OverpassClient()
    element = {"type": "node", "id": 1, "lat": -1.2, "lon": 36.8, "tags": {}}
    assert client._element_to_listing(element, "clinic", "Nairobi") is None


def test_overpass_element_to_listing_with_name():
    client = OverpassClient()
    element = {
        "type": "node", "id": 123, "lat": -1.28, "lon": 36.82,
        "tags": {
            "name": "Nairobi Clinic",
            "phone": "+254712345678",
            "website": "http://clinic.co.ke",
            "addr:street": "Tom Mboya St",
        },
    }
    listing = client._element_to_listing(element, "clinic", "Nairobi")
    assert listing["name"] == "Nairobi Clinic"
    assert listing["phone"] == "+254712345678"
    assert listing["has_website"] is True
    assert listing["source"] == "overpass"
    assert listing["county"] == "Nairobi"


@pytest.mark.asyncio
async def test_overpass_search_unknown_county_returns_empty():
    client = OverpassClient()
    results = await client.search("clinic", "UnknownPlace")
    assert results == []


@pytest.mark.asyncio
async def test_overpass_search_mocked():
    client = OverpassClient()
    mock_response = {
        "elements": [
            {
                "type": "node", "id": 1, "lat": -1.28, "lon": 36.82,
                "tags": {"name": "Test Clinic", "amenity": "clinic"},
            }
        ]
    }
    with patch.object(client, "_query", new=AsyncMock(return_value=mock_response)):
        results = await client.search("clinic", "Nairobi", max_results=10)
    assert len(results) == 1
    assert results[0]["name"] == "Test Clinic"
