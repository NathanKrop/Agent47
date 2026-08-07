"""Backend control + AI chat handlers for the dashboard.

Provides:
- get_agent_status()        -> live runtime snapshot for the Control Panel
- execute_control(action)   -> applies a control action (toggle gates, caps, run now)
- handle_chat(message)      -> answers questions and/or acts on backend via LLM if
                               a key is configured, else a rule-based command engine.
"""

import json
import re

import httpx

from config.agent_state import (
    agent_status,
    is_pipeline_running,
    set_pipeline_running,
    require_verified_contact,
    set_require_verified_contact,
    get_rate_limits,
    set_rate_limit,
    get_channels,
    set_channels,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    OPENAI_MODEL,
    OPENROUTER_MODEL,
)
from config.settings import DRY_RUN, SENDGRID_API_KEY, WHATSAPP_API_TOKEN, AT_API_KEY
from database.repository import get_dashboard_stats, get_recent_logs
from scheduler.main_pipeline import request_cycle_now, request_rescan_now

# Quick-reference lines the LLM / rule engine can draw from.
HELP_TEXT = (
    "I can control the Kenya Outreach Agent from here. You can ask me things like:\n"
    "- \"how many leads do we have?\"\n"
    "- \"what is the delivery rate?\"\n"
    "- \"pause the pipeline\" / \"resume the pipeline\"\n"
    "- \"turn verified-only outreach on/off\"\n"
    "- \"set the daily cap to 200\"\n"
    "- \"set channels to whatsapp,email\"\n"
    "- \"run a discovery cycle now\" / \"run a rescan now\"\n"
    "- \"send a test batch of 10 emails\""
)


def get_agent_status():
    """Full status snapshot including provider availability + health."""
    stats = get_dashboard_stats()
    state = agent_status()
    try:
        logs = get_recent_logs(limit=5)
    except Exception:
        logs = []
    return {
        **state,
        "dry_run": DRY_RUN,
        "sendgrid_key": bool(SENDGRID_API_KEY),
        "whatsapp_key": bool(WHATSAPP_API_TOKEN),
        "at_key": bool(AT_API_KEY),
        "stats": stats,
        "recent_log_count": len(logs),
    }


def _detect_command(text: str):
    """Rule-based intent detection -> (action, params dict) or None."""
    t = text.lower().strip()

    # pipeline pause/resume
    if re.search(r"\bpause\b", t) and re.search(r"\bpipeline\b|agent|discovery", t):
        return ("set_pipeline", {"running": False})
    if re.search(r"\bresume\b|start\b|unpause", t) and re.search(r"\bpipeline\b|agent|discovery", t):
        return ("set_pipeline", {"running": True})

    # verified-only gate
    if re.search(r"\bverified", t) and re.search(r"\bon\b|enable|true", t):
        return ("set_verified", {"value": True})
    if re.search(r"\bverified", t) and re.search(r"\boff\b|disable|false", t):
        return ("set_verified", {"value": False})

    # daily cap
    m = re.search(r"\b(?:cap|limit|daily)\s*(?:to|=|of|:)?\s*(\d+)", t)
    if m:
        return ("set_cap", {"value": int(m.group(1))})

    # channels
    m = re.search(r"\bchannels?\s*(?:to|=|:)?\s*([\w\s,]+)", t)
    if m:
        vals = [x.strip().lower() for x in re.split(r"[\s,]+", m.group(1)) if x.strip()]
        if all(v in ("whatsapp", "email", "sms") for v in vals):
            return ("set_channels", {"channels": vals})

    # run now
    if re.search(r"\b(?:run|trigger|do)\b", t) and re.search(r"\b(?:discovery|cycle|scrape)\b", t):
        return ("run_cycle", {})
    if re.search(r"\b(?:rescan|re[- ]?check|refresh existing)\b", t):
        return ("run_rescan", {})

    # status questions
    if re.search(r"\b(?:status|state|running|health)\b", t):
        return ("status", {})
    if re.search(r"\bleads?\b|businesses?|companies", t):
        return ("leads_summary", {})
    if re.search(r"\bdelivery\b|response\b|rate\b", t):
        return ("stats_summary", {})
    if re.search(r"\bhelp\b|what can you do\b", t):
        return ("help", {})

    return None


def _execute(action: str, params: dict) -> dict:
    if action == "set_pipeline":
        val = set_pipeline_running(bool(params.get("running", False)))
        return {"ok": True, "message": "Agent pipeline " + ("resumed. Discovery is running 24/7." if val else "paused. Discovery is now idle.")}
    if action == "set_verified":
        val = set_require_verified_contact(bool(params.get("value", True)))
        return {"ok": True, "message": "Verified-only outreach is now " + ("ON (only verified contacts will be messaged)." if val else "OFF (all contacts may be messaged).")}
    if action == "set_cap":
        val = set_rate_limit("max_global_per_day", int(params["value"]))
        return {"ok": True, "message": f"Daily global cap set to {val['max_global_per_day']} messages."}
    if action == "set_channels":
        vals = set_channels(params["channels"])
        return {"ok": True, "message": "Outreach channels set to: " + ", ".join(vals) + "."}
    if action == "run_cycle":
        request_cycle_now()
        return {"ok": True, "message": "Discovery cycle queued. It will run on the next loop tick (pickup within ~30s)."}
    if action == "run_rescan":
        request_rescan_now()
        return {"ok": True, "message": "Rescan of existing listings queued. It will run on the next loop tick."}
    if action == "status":
        s = get_agent_status()
        return {"ok": True, "answer": _format_status(s), "status": s}
    if action == "leads_summary":
        s = get_dashboard_stats()
        return {"ok": True, "answer": f"We have **{s['total_listings']:,} leads** total. {s['no_website']:,} ({s['no_website_pct']}%) have no website, {s['broken_website']:,} ({s['broken_website_pct']}%) are broken/poor."}
    if action == "stats_summary":
        s = get_dashboard_stats()
        return {"ok": True, "answer": f"Delivery rate: **{s['delivery_rate']}%**, Response rate: **{s['response_rate']}%**, Sent today: **{s['messages_sent_today']:,}**, Opt-outs: **{s['opt_outs']}**."}
    if action == "help":
        return {"ok": True, "answer": HELP_TEXT}
    return {"ok": False, "message": "Unsupported action."}


def _format_status(s: dict) -> str:
    stats = s.get("stats", {})
    provider = s.get("llm_provider") or "none (rule-based mode)"
    return (
        f"**Agent status:**\n"
        f"- Pipeline: {'RUNNING (24/7)' if s.get('pipeline_running') else 'PAUSED'}\n"
        f"- Verified-only outreach: {'ON' if s.get('require_verified_contact') else 'OFF'}\n"
        f"- Daily cap: {s.get('rate_limits', {}).get('max_global_per_day', '?')}\n"
        f"- Channels: {', '.join(s.get('channels', [])) or 'none'}\n"
        f"- DRY_RUN: {'true' if s.get('dry_run') else 'false'}\n"
        f"- Lead count: {stats.get('total_listings', 0):,}\n"
        f"- AI mode: {provider}"
    )


async def _call_llm(system: str, user: str, fallback) -> dict:
    """Call OpenAI (or OpenRouter) chat completions. On any failure, run fallback."""
    try:
        if OPENAI_API_KEY:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            model = OPENAI_MODEL
        elif OPENROUTER_API_KEY:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "HTTP-Referer": ""}
            model = OPENROUTER_MODEL
        else:
            return fallback

        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post(
                url,
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.4,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return {"ok": True, "answer": content}
    except Exception as exc:
        return fallback | {"llm_error": str(exc)}


async def handle_chat(message: str) -> dict:
    """Public entry: answer a user message, optionally acting on the backend.

    Uses the LLM when a key is configured; otherwise the rule-based engine.
    """
    if not message or not message.strip():
        return {"ok": True, "answer": HELP_TEXT}

    # Always run the rule engine for guaranteed, deterministic control actions first.
    cmd = _detect_command(message)
    if cmd:
        action, params = cmd
        # Deterministic command actions execute independently of LLM mode.
        if action not in ("status", "leads_summary", "stats_summary", "help"):
            result = _execute(action, params)
            return {"ok": True, "answer": result["message"]}

    # Build the control system prompt for the LLM (if available).
    sys_prompt = """You are the control assistant for the 'Kenya Outreach Agent' dashboard.
You can READ the current agent state and answer questions about the dashboard and the
lead data. You have access to these facts (memory) about the live system; use them to
answer accurately and concisely (max ~120 words), formatted with light Markdown.

Current live state (from the backend):
{tools}

You may also interpret intent and return EXACTLY valid JSON for tool calls. If the user
asks to change something, map it to ONE of these JSON tool actions:
- {{"tool":"set_pipeline","params":{{"running":true}}}}  (or false)
- {{"tool":"set_verified","params":{{"value":true}}}}     (or false)
- {{"tool":"set_cap","params":{{"value":<int>}}}}
- {{"tool":"set_channels","params":{{"channels":["whatsapp","email",...]}}}}
- {{"tool":"run_cycle","params":{{}}}}
- {{"tool":"run_rescan","params":{{}}}}
If the user is asking a question (not a change), reply in plain text using the state.
If you decide to call a tool, reply with ONLY the JSON object, nothing else.
""".format(tools=json.dumps(get_agent_status(), default=str))

    llm_result = await _call_llm(sys_prompt, message, {"ok": False})
    if llm_result.get("ok") and llm_result.get("answer"):
        answer = llm_result["answer"].strip()
        # Try to interpret an LLM tool call as JSON
        try:
            parsed = json.loads(answer)
            if isinstance(parsed, dict) and "tool" in parsed:
                tool = parsed["tool"]
                if tool in {
                    "set_pipeline", "set_verified", "set_cap",
                    "set_channels", "run_cycle", "run_rescan",
                }:
                    act_map = {
                        "set_pipeline": "set_pipeline",
                        "set_verified": "set_verified",
                        "set_cap": "set_cap",
                        "set_channels": "set_channels",
                        "run_cycle": "run_cycle",
                        "run_rescan": "run_rescan",
                    }
                    result = _execute(act_map[tool], parsed.get("params", {}))
                    return {"ok": True, "answer": result["message"], "tool": tool}
                return {"ok": True, "answer": "I understood that as a question, not an action."}
            return {"ok": True, "answer": answer, "tool": None}
        except (json.JSONDecodeError, TypeError):
            return {"ok": True, "answer": answer, "tool": None}

    # No LLM key and not a recognized control -> fall back to rule engine answers.
    cmd = _detect_command(message)
    if cmd:
        action, params = cmd
        if action in ("status", "leads_summary", "stats_summary", "help"):
            result = _execute(action, params)
            return {"ok": True, "answer": result["answer"]}

    return {
        "ok": True,
        "answer": (
            "I couldn't map that to a control action, and no AI provider key is loaded, "
            "so I can't answer open-ended questions yet. Add OPENAI_API_KEY (or "
            "OPENROUTER_API_KEY) to `.env`, then restart the dashboard for full AI "
            "assistant mode.\n\n" + HELP_TEXT
        ),
    }


def execute_control(action: str, params: dict) -> dict:
    """Direct control executed from the Control Panel buttons/sliders (no LLM)."""
    return _execute(action, params)
