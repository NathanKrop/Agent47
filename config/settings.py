import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/kenya_agent")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() in ("true", "1", "yes")

# Google
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

# WhatsApp BSP
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_SENDER_ID = os.getenv("WHATSAPP_SENDER_ID", "")

# SMS (Africa's Talking)
AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY = os.getenv("AT_API_KEY", "")
AT_SENDER_ID = os.getenv("AT_SENDER_ID", "NATHAN_WEB")

# Email (SendGrid)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "nathan@yourdomain.com")
FROM_NAME = os.getenv("FROM_NAME", "Nathan Krop")

# Portfolio
PORTFOLIO_URL = os.getenv("PORTFOLIO_URL", "https://nathan-krop-website2.vercel.app/")
UTM_SOURCE = os.getenv("UTM_SOURCE", "agent_outreach")

# Dashboard
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "")

# Playwright
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
PROXY_URL = os.getenv("PROXY_URL", "")

# Pipeline
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
DISCOVERY_CYCLE_SECONDS = int(os.getenv("DISCOVERY_CYCLE_SECONDS", "600"))
RESCAN_INTERVAL_HOURS = int(os.getenv("RESCAN_INTERVAL_HOURS", "24"))

# SMS Hours (East Africa Time)
SMS_START_HOUR_EAT = 7
SMS_END_HOUR_EAT = 19

SCORING_WEIGHTS = {
    "no_website": 3,
    "broken_website": 2,
    "confirmed_phone": 1,
    "confirmed_email": 1,
    "reviews_gt_3": 1,
    "high_value_category": 1,
    "active_recently": 1,
}

PRIORITY_THRESHOLDS = {
    "PRIORITY_1": 4,
    "PRIORITY_2": 2,
    "PRIORITY_3": 1,
}

# Dashboard access control (optional). If set, client must send header `X-API-KEY` with this value.
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "")

RATE_LIMITS = {
    "max_per_recipient_per_day": int(os.getenv("MAX_MESSAGES_PER_NUMBER_PER_DAY", "1")),
    "max_global_per_day": int(os.getenv("MAX_MESSAGES_PER_DAY_GLOBAL", "500")),
    "min_gap_seconds": int(os.getenv("MIN_GAP_BETWEEN_SENDS_SECONDS", "30")),
    "retry_backoff_seconds": int(os.getenv("RETRY_BACKOFF_SECONDS", "300")),
}

# Outreach order: WhatsApp first, then email.
# SMS is intentionally removed by default to avoid Africa's Talking prepayment requirements.
OUTREACH_CHANNELS = ["whatsapp", "email"]

# Only queue/send outreach to leads whose phone or email passed verification.
# Default True = safe live-sending: never message unverified contacts.
OUTREACH_REQUIRE_VERIFIED_CONTACT = (
    os.getenv("OUTREACH_REQUIRE_VERIFIED_CONTACT", "true").lower() in ("1", "true", "yes")
)

# AI chat provider keys (optional). If set, the dashboard chat uses the LLM to
# control the backend; otherwise it falls back to a rule-based command engine.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

HIGH_VALUE_CATEGORIES = {
    "clinic",
    "pharmacy",
    "school",
    "law firm",
    "real estate agent",
    "hotel",
    "e-commerce",
    "online shop",
}

BROKEN_WEBSITE_STATUSES = {"broken", "parked", "placeholder", "poor"}
