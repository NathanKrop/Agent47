"""Lead scoring and priority tier assignment."""

from typing import Any

from config.settings import (
    BROKEN_WEBSITE_STATUSES,
    HIGH_VALUE_CATEGORIES,
    PRIORITY_THRESHOLDS,
    SCORING_WEIGHTS,
)


class LeadScorer:
    """
    Scores each enriched listing and assigns a priority tier.

    Priority tiers:
    - PRIORITY_1: score >= 4  → Fast outreach queue
    - PRIORITY_2: score >= 2  → Standard queue
    - PRIORITY_3: score >= 1  → Slow queue
    - SKIP: score == 0 or has GOOD website
    """

    def score(self, listing: dict[str, Any]) -> tuple[int, str]:
        website_status = (listing.get("website_status") or "no_website").lower()

        if website_status == "good":
            return 0, "SKIP"

        total = 0

        if website_status == "no_website":
            total += SCORING_WEIGHTS["no_website"]
        elif website_status in BROKEN_WEBSITE_STATUSES:
            total += SCORING_WEIGHTS["broken_website"]

        if listing.get("phone_verified") or listing.get("phone"):
            if listing.get("phone_verified", True):
                total += SCORING_WEIGHTS["confirmed_phone"]

        if listing.get("email_verified") or listing.get("email"):
            if listing.get("email_verified", False) or listing.get("email"):
                total += SCORING_WEIGHTS["confirmed_email"]

        review_count = listing.get("review_count") or 0
        if review_count > 3:
            total += SCORING_WEIGHTS["reviews_gt_3"]

        category = (listing.get("category") or "").lower()
        if self._is_high_value(category):
            total += SCORING_WEIGHTS["high_value_category"]

        if listing.get("active_recently"):
            total += SCORING_WEIGHTS["active_recently"]

        if listing.get("likely_closed"):
            return 0, "SKIP"

        tier = self._tier_for_score(total)
        return total, tier

    def _tier_for_score(self, score: int) -> str:
        if score >= PRIORITY_THRESHOLDS["PRIORITY_1"]:
            return "PRIORITY_1"
        if score >= PRIORITY_THRESHOLDS["PRIORITY_2"]:
            return "PRIORITY_2"
        if score >= PRIORITY_THRESHOLDS["PRIORITY_3"]:
            return "PRIORITY_3"
        return "SKIP"

    def _is_high_value(self, category: str) -> bool:
        category = category.lower().strip()
        return category in HIGH_VALUE_CATEGORIES or any(
            hv in category for hv in HIGH_VALUE_CATEGORIES
        )

    def enrich_listing(self, listing: dict[str, Any]) -> dict[str, Any]:
        score, tier = self.score(listing)
        listing["score"] = score
        listing["priority"] = tier
        return listing
