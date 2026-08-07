"""Detect likely-closed or inactive businesses."""

from datetime import datetime, timedelta, timezone
from typing import Any


class ActivityChecker:
    """Heuristics to detect likely-closed or inactive businesses."""

    INACTIVE_KEYWORDS = [
        "permanently closed",
        "closed permanently",
        "temporarily closed",
        "out of business",
    ]

    def is_likely_closed(self, listing: dict[str, Any]) -> bool:
        text = " ".join(
            str(listing.get(k, "")) for k in ("name", "address", "description", "status")
        ).lower()
        return any(kw in text for kw in self.INACTIVE_KEYWORDS)

    def is_active_recently(self, listing: dict[str, Any]) -> bool:
        """
        Estimate recent activity from review count and rating presence.
        Full review-date parsing requires Maps detail scrape; use proxy signals.
        """
        if self.is_likely_closed(listing):
            return False

        review_count = listing.get("review_count") or 0
        rating = listing.get("rating")
        last_checked = listing.get("last_review_at")

        if last_checked:
            if isinstance(last_checked, str):
                try:
                    last_checked = datetime.fromisoformat(last_checked)
                except ValueError:
                    last_checked = None
            if last_checked and last_checked > datetime.now(timezone.utc) - timedelta(days=365):
                return True

        return review_count >= 1 and rating is not None

    def enrich_listing(self, listing: dict[str, Any]) -> dict[str, Any]:
        listing["likely_closed"] = self.is_likely_closed(listing)
        listing["active_recently"] = self.is_active_recently(listing)
        return listing
