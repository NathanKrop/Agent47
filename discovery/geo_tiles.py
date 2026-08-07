"""Kenya geo-tile search job generator."""

import random
from typing import Any

from config.categories import (
    GEO_TILES,
    KENYA_COUNTIES,
    PILOT_CATEGORIES,
    PILOT_COUNTIES,
    TARGET_CATEGORIES,
)


def generate_search_jobs(
    categories: list[str] | None = None,
    counties: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Cross-product of categories × counties → list of search jobs.
    Each job: {"category": "plumber", "location": "Nairobi", "county": "Nairobi"}
    Shuffled to distribute load evenly.
    """
    categories = categories or TARGET_CATEGORIES
    counties = counties or KENYA_COUNTIES

    jobs = [
        {"category": category, "location": county, "county": county}
        for category in categories
        for county in counties
    ]
    random.shuffle(jobs)
    return jobs


def get_priority_jobs() -> list[dict[str, Any]]:
    """High-priority pilot jobs: Nairobi + Mombasa, top 5 categories first."""
    return generate_search_jobs(categories=PILOT_CATEGORIES, counties=PILOT_COUNTIES)


def get_county_bounds(county: str) -> list[tuple[float, float, float, float]] | None:
    """Return bounding boxes for a county."""
    return GEO_TILES.get(county)


def county_count() -> int:
    """Return number of counties with geo tiles defined."""
    return len(GEO_TILES)
