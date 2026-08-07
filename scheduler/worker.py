"""Celery worker for async outreach tasks."""

import asyncio

from celery import Celery
from loguru import logger

from config.settings import REDIS_URL, CELERY_TASK_ALWAYS_EAGER

app = Celery("outreach_agent", broker=REDIS_URL, backend=REDIS_URL)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Nairobi",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=CELERY_TASK_ALWAYS_EAGER,
)


async def send_outreach_async(listing_id: str) -> dict[str, str]:
    """Async outreach helper that can be awaited from an event loop."""
    from database.repository import get_listing
    from outreach.channel_router import ChannelRouter

    listing = get_listing(listing_id)
    if not listing:
        logger.warning(f"Listing not found: {listing_id}")
        return {"status": "not_found"}

    router = ChannelRouter()
    return await router.route_and_send(listing)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def send_outreach_task(self, listing_id: str):
    """
    Celery task: fetch listing from DB, route and send outreach.
    Retries up to 3× on failure with 5min delay.
    """
    try:
        return asyncio.run(send_outreach_async(listing_id))
    except Exception as exc:
        logger.error(f"Outreach task failed for {listing_id}: {exc}")
        raise self.retry(exc=exc)
