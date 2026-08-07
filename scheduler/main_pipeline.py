"""
Main orchestration loop. Runs endlessly.

Discovery source priority per job:
1. Overpass API (OpenStreetMap) — free, no key needed
2. Google Maps Playwright scraper — free, headless browser
3. Google Places API — fallback if API key is configured

Loop:
1. Generate search jobs (geo-tile × category combos)
2. For each job: discover → enrich → verify → score → save → queue outreach
3. Celery workers pick up tasks → ChannelRouter.route_and_send()
4. Sleep between batches, repeat indefinitely
5. Every RESCAN_INTERVAL_HOURS: re-check existing listings for changes
"""

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger

from config.categories import KENYA_COUNTIES, TARGET_CATEGORIES
from config.settings import CELERY_TASK_ALWAYS_EAGER, DISCOVERY_CYCLE_SECONDS, RESCAN_INTERVAL_HOURS
from config.agent_state import is_pipeline_running
from database.models import init_db
from database.repository import listing_id, upsert_listing
from discovery.geo_tiles import generate_search_jobs, get_priority_jobs
from discovery.google_maps_scraper import GoogleMapsScraper
from discovery.overpass_api import OverpassClient
from discovery.places_api import PlacesAPIClient
from discovery.website_checker import WebsiteChecker
from enrichment.email_extractor import EmailExtractor
from enrichment.phone_extractor import PhoneExtractor
from enrichment.social_extractor import SocialExtractor
from scoring.lead_scorer import LeadScorer
from scheduler.worker import send_outreach_async, send_outreach_task
from verification.activity_checker import ActivityChecker
from verification.email_verifier import EmailVerifier
from verification.phone_verifier import PhoneVerifier

_maps_backoff_seconds = 60
MAX_MAPS_BACKOFF = 1800
_last_rescan: datetime | None = None

# Manual "run now" triggers set by the dashboard control panel.
_trigger_cycle = False
_trigger_rescan = False


def request_cycle_now() -> None:
    global _trigger_cycle
    _trigger_cycle = True


def request_rescan_now() -> None:
    global _trigger_rescan
    _trigger_rescan = True


def _consume_cycle_trigger() -> bool:
    global _trigger_cycle
    if _trigger_cycle:
        _trigger_cycle = False
        return True
    return False


def _consume_rescan_trigger() -> bool:
    global _trigger_rescan
    if _trigger_rescan:
        _trigger_rescan = False
        return True
    return False


async def main() -> None:
    logger.info("Kenya Outreach Agent starting...")
    init_db()

    while True:
        try:
            if not is_pipeline_running():
                logger.info("Pipeline paused via control panel — waiting...")
                await asyncio.sleep(5)
                continue

            if _consume_cycle_trigger():
                logger.info("Manual cycle triggered from control panel.")
                await run_discovery_cycle()

            if _consume_rescan_trigger():
                logger.info("Manual rescan triggered from control panel.")
                _last_rescan = None
                await _maybe_rescan_existing(force=True)

            await run_discovery_cycle()
            await _maybe_rescan_existing()
            logger.info(f"Cycle complete. Sleeping {DISCOVERY_CYCLE_SECONDS}s...")
            await asyncio.sleep(DISCOVERY_CYCLE_SECONDS)
        except Exception as exc:
            logger.error(f"Pipeline error: {exc}")
            await asyncio.sleep(60)


async def run_discovery_cycle(use_pilot: bool = False) -> None:
    jobs = get_priority_jobs() if use_pilot else generate_search_jobs(TARGET_CATEGORIES, KENYA_COUNTIES)
    logger.info(f"Processing {len(jobs)} discovery jobs")

    for i, job in enumerate(jobs):
        try:
            await process_job(job)
        except Exception as exc:
            logger.error(f"Job failed {job}: {exc}")
            await _handle_maps_rate_limit(str(exc))

        if (i + 1) % 10 == 0:
            await asyncio.sleep(5)


async def process_job(job: dict) -> None:
    category = job["category"]
    location = job["location"]
    county = job["county"]

    overpass = OverpassClient()
    scraper = GoogleMapsScraper()
    places = PlacesAPIClient()
    website_checker = WebsiteChecker()
    phone_extractor = PhoneExtractor()
    email_extractor = EmailExtractor()
    social_extractor = SocialExtractor()
    phone_verifier = PhoneVerifier()
    email_verifier = EmailVerifier()
    activity_checker = ActivityChecker()
    scorer = LeadScorer()

    # --- Discovery: Overpass first (free), then scraper, then Places API ---
    listings: list[dict] = []
    try:
        listings = await overpass.search(category, county, max_results=50)
        logger.info(f"Overpass returned {len(listings)} for {category}/{county}")
    except Exception as exc:
        logger.warning(f"Overpass failed for {category}/{county}: {exc}")

    if not listings:
        try:
            listings = await scraper.search(category, location, max_results=50)
        except Exception as exc:
            logger.warning(f"Maps scraper failed, falling back to Places API: {exc}")
            await _handle_maps_rate_limit(str(exc))
            listings = await places.search(category, location, max_results=50)

    # --- Enrich, verify, score, save each listing ---
    for raw in listings:
        try:
            raw["category"] = category
            raw["county"] = county

            await website_checker.classify_listing(raw)

            phones = phone_extractor.extract_and_normalise(
                f"{raw.get('phone', '')} {raw.get('address', '')}"
            )
            if phones:
                raw["phone"] = phones[0]
                verify_result = await phone_verifier.verify(phones[0])
                raw["phone_verified"] = verify_result.valid

            raw = await email_extractor.enrich_listing(raw)
            if raw.get("email"):
                email_result = await email_verifier.verify(raw["email"])
                raw["email_verified"] = email_result.valid

            raw = await social_extractor.enrich_listing(raw)
            raw = activity_checker.enrich_listing(raw)
            raw = scorer.enrich_listing(raw)

            raw["id"] = listing_id(raw.get("name", ""), raw.get("address", ""))
            lid = upsert_listing(raw)

            priority = raw.get("priority", "SKIP")
            if priority in ("PRIORITY_1", "PRIORITY_2", "PRIORITY_3"):
                if CELERY_TASK_ALWAYS_EAGER:
                    await send_outreach_async(lid)
                else:
                    send_outreach_task.delay(lid)
                logger.info(f"Queued outreach: {raw.get('name')} [{priority}] via {raw.get('source', 'unknown')}")

        except Exception as exc:
            logger.error(f"Listing processing error: {exc}")


async def _maybe_rescan_existing(force: bool = False) -> None:
    """Re-score and re-queue existing listings not checked in RESCAN_INTERVAL_HOURS."""
    global _last_rescan
    now = datetime.now(timezone.utc)
    if not force and _last_rescan and (now - _last_rescan) < timedelta(hours=RESCAN_INTERVAL_HOURS):
        return

    logger.info("Running rescan of existing listings...")
    _last_rescan = now

    from database.models import Listing, SessionLocal
    from sqlalchemy import select

    cutoff = now - timedelta(hours=RESCAN_INTERVAL_HOURS)
    website_checker = WebsiteChecker()
    scorer = LeadScorer()
    activity_checker = ActivityChecker()

    with SessionLocal() as session:
        stale = session.execute(
            select(Listing).where(Listing.last_checked_at < cutoff).limit(200)
        ).scalars().all()

    for row in stale:
        try:
            listing = {
                "id": row.id, "name": row.name, "address": row.address,
                "county": row.county, "category": row.category,
                "phone": row.phone, "email": row.email,
                "website_url": row.website_url,
                "rating": row.rating, "review_count": row.review_count,
                "phone_verified": row.phone_verified, "email_verified": row.email_verified,
            }
            await website_checker.classify_listing(listing)
            listing = activity_checker.enrich_listing(listing)
            listing = scorer.enrich_listing(listing)
            upsert_listing(listing)

            if listing.get("priority") in ("PRIORITY_1", "PRIORITY_2", "PRIORITY_3"):
                send_outreach_task.delay(row.id)
        except Exception as exc:
            logger.error(f"Rescan failed for {row.id}: {exc}")

    logger.info(f"Rescan complete — processed {len(stale)} stale listings")


async def _handle_maps_rate_limit(error_msg: str) -> None:
    global _maps_backoff_seconds
    if "rate" in error_msg.lower() or "429" in error_msg or "captcha" in error_msg.lower():
        logger.warning(f"Google rate limit detected. Backing off {_maps_backoff_seconds}s")
        await asyncio.sleep(_maps_backoff_seconds)
        _maps_backoff_seconds = min(_maps_backoff_seconds * 2, MAX_MAPS_BACKOFF)
    else:
        _maps_backoff_seconds = 60


if __name__ == "__main__":
    asyncio.run(main())
