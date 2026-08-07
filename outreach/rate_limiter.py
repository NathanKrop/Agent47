"""Redis-backed rate limiter for outreach sends."""

import time
from datetime import datetime, timezone

import redis.asyncio as aioredis
from loguru import logger

from config.settings import RATE_LIMITS, REDIS_URL


class RateLimiter:
    """
    Enforces:
    - Max 1 message per phone/email per day
    - Max 500 messages per day globally
    - Minimum 30-second gap between any two sends
    - 5-minute backoff after any API error
    """

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or REDIS_URL
        self._redis: aioredis.Redis | None = None
        self.limits = RATE_LIMITS

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def _day_key(self, prefix: str, identifier: str = "") -> str:
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        if identifier:
            return f"rate:{prefix}:{identifier}:{day}"
        return f"rate:{prefix}:global:{day}"

    async def can_send(self, recipient: str) -> bool:
        try:
            r = await self._get_redis()

            global_key = self._day_key("global")
            global_count = int(await r.get(global_key) or 0)
            if global_count >= self.limits["max_global_per_day"]:
                logger.warning("Global daily message cap reached")
                return False

            recipient_key = self._day_key("recipient", recipient)
            recipient_count = int(await r.get(recipient_key) or 0)
            if recipient_count >= self.limits["max_per_recipient_per_day"]:
                logger.debug(f"Daily cap reached for {recipient}")
                return False

            last_send = await r.get("rate:last_send_ts")
            if last_send:
                elapsed = time.time() - float(last_send)
                if elapsed < self.limits["min_gap_seconds"]:
                    return False

            backoff_until = await r.get("rate:backoff_until")
            if backoff_until and time.time() < float(backoff_until):
                return False

            return True
        except Exception as exc:
            logger.error(f"Rate limiter error: {exc}")
            return True

    async def record_send(self, recipient: str) -> None:
        try:
            r = await self._get_redis()
            pipe = r.pipeline()
            pipe.incr(self._day_key("global"))
            pipe.expire(self._day_key("global"), 86400)
            pipe.incr(self._day_key("recipient", recipient))
            pipe.expire(self._day_key("recipient", recipient), 86400)
            pipe.set("rate:last_send_ts", str(time.time()))
            await pipe.execute()
        except Exception as exc:
            logger.error(f"Failed to record send: {exc}")

    async def backoff(self, seconds: int | None = None) -> None:
        seconds = seconds or self.limits["retry_backoff_seconds"]
        try:
            r = await self._get_redis()
            await r.set("rate:backoff_until", str(time.time() + seconds), ex=seconds)
            logger.info(f"Rate limiter backoff for {seconds}s")
        except Exception as exc:
            logger.error(f"Failed to set backoff: {exc}")
