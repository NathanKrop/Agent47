"""Thread-safe shared runtime state for the agent.

This module is the single source of truth for live-controllable settings that
the dashboard and the scheduler both read/write, so toggling a control in the
Frontend Control Panel takes effect immediately without restarting services.
"""

import os
import threading

from config.settings import (
    OUTREACH_CHANNELS,
    OUTREACH_REQUIRE_VERIFIED_CONTACT,
    RATE_LIMITS,
    OPENAI_MODEL,
    OPENROUTER_MODEL,
)

_lock = threading.RLock()

# Pipeline lifecycle
_pipeline_running = True

# Outreach gates
_require_verified_contact = OUTREACH_REQUIRE_VERIFIED_CONTACT

# Rate limits (editable live)
_rate_limits = {
    "min_gap_seconds": RATE_LIMITS.get("min_gap_seconds", 30),
    "max_per_recipient_per_day": RATE_LIMITS.get("max_per_recipient_per_day", 1),
    "max_global_per_day": RATE_LIMITS.get("max_global_per_day", 500),
}

# Outreach channels (editable live)
_channels = list(OUTREACH_CHANNELS)

# Optional env keys for the AI chat (read once at import)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


# ---------------------------------------------------------------------------
# Pipeline lifecycle
# ---------------------------------------------------------------------------
def is_pipeline_running() -> bool:
    with _lock:
        return _pipeline_running


def set_pipeline_running(running: bool) -> bool:
    global _pipeline_running
    with _lock:
        _pipeline_running = bool(running)
        return _pipeline_running


# ---------------------------------------------------------------------------
# Verified-contact gate
# ---------------------------------------------------------------------------
def require_verified_contact() -> bool:
    with _lock:
        return _require_verified_contact


def set_require_verified_contact(value: bool) -> bool:
    global _require_verified_contact
    with _lock:
        _require_verified_contact = bool(value)
        return _require_verified_contact


# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------
def get_rate_limits() -> dict:
    with _lock:
        return dict(_rate_limits)


def set_rate_limit(key: str, value: int) -> dict:
    with _lock:
        _rate_limits[key] = int(value)
        return dict(_rate_limits)


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------
def get_channels() -> list:
    with _lock:
        return list(_channels)


def set_channels(values) -> list:
    global _channels
    with _lock:
        _channels = [str(v).strip() for v in values if str(v).strip()]
        return list(_channels)


# ---------------------------------------------------------------------------
# Snapshot for the dashboard
# ---------------------------------------------------------------------------
def agent_status() -> dict:
    with _lock:
        return {
            "pipeline_running": _pipeline_running,
            "require_verified_contact": _require_verified_contact,
            "rate_limits": dict(_rate_limits),
            "channels": list(_channels),
            "llm_available": bool(OPENAI_API_KEY or OPENROUTER_API_KEY),
            "llm_provider": "openai" if OPENAI_API_KEY else ("openrouter" if OPENROUTER_API_KEY else None),
        }
