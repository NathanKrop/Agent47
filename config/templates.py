"""Outreach message templates — all messages from Nathan Krop, English only."""

from config.settings import PORTFOLIO_URL, UTM_SOURCE


def portfolio_link(business_name: str = "") -> str:
    """Build portfolio URL with UTM tracking."""
    base = PORTFOLIO_URL.rstrip("/")
    return f"{base}?utm_source={UTM_SOURCE}&utm_medium=outreach"


WHATSAPP_TEMPLATES = {
    "no_website_primary": {
        "name": "nathan_no_website_v1",
        "body": (
            "Hello {business_name}! 👋 I'm Nathan, a web developer based in Kenya. "
            "I noticed {business_name} doesn't have a website yet — you're missing customers "
            "who search online every day. I build fast, affordable websites for local businesses. "
            "See my work here: {portfolio_link} — I'd love to give you a free 30-min consultation. "
            "Reply YES or call me anytime. To stop messages, reply STOP."
        ),
    },
    "broken_website_primary": {
        "name": "nathan_broken_website_v1",
        "body": (
            "Hi {business_name}! I'm Nathan, a Kenyan web developer. "
            "I came across your business online and noticed your website may need some attention — "
            "a slow or broken site can cost you customers. "
            "I specialise in fast, modern websites. Portfolio: {portfolio_link} "
            "Free review available. Reply YES or STOP to opt out."
        ),
    },
    "followup_3days": {
        "name": "nathan_followup_v1",
        "body": (
            "Hi {business_name}, Nathan here again 👋 Just checking in — "
            "a professional website could bring you more clients every week. "
            "Quick portfolio: {portfolio_link} — happy to chat at your convenience. Reply STOP to opt out."
        ),
    },
}

SMS_TEMPLATES = {
    "no_website_primary": (
        "Hi {business_name}, I'm Nathan (web dev). Your business needs a website to grow online. "
        "See my work: {portfolio_link} Free consult available. Reply STOP to opt out."
    ),
    "broken_website_primary": (
        "Hi {business_name}, Nathan here. Your website may need fixing — I can help. "
        "Portfolio: {portfolio_link} Reply YES for free review. Reply STOP to opt out."
    ),
}

EMAIL_TEMPLATES = {
    "no_website_primary": {
        "subject": "Quick question about {business_name}'s online presence",
        "body": """
Hi {contact_name},

My name is Nathan Krop — I'm a web developer based in Kenya.

I was searching for {category} services in {location} and came across {business_name}.
I noticed you don't have a website yet, which means potential customers searching online
can't find you easily.

I specialise in building fast, mobile-friendly websites for local Kenyan businesses —
affordable pricing, quick turnaround, and ongoing support.

You can see my portfolio here: {portfolio_link}

I'd love to offer you a free 30-minute consultation to discuss what a website could do
for {business_name}. No obligation.

Would you be open to a quick call this week?

Best regards,
Nathan Krop
Web Developer | Kenya
{portfolio_link}

---
To unsubscribe, reply with UNSUBSCRIBE.
        """,
    },
    "broken_website_primary": {
        "subject": "Free website review for {business_name}",
        "body": """
Hi {contact_name},

I'm Nathan Krop, a web developer based in Kenya.

I came across {business_name} while searching for {category} services in {location}.
Your current website could be working harder for you — slow load times and outdated design
often cost local businesses customers every day.

I help Kenyan businesses build fast, modern websites. See my portfolio: {portfolio_link}

I'd be happy to offer a free website review with no obligation.

Best regards,
Nathan Krop
Web Developer | Kenya

---
To unsubscribe, reply with UNSUBSCRIBE.
        """,
    },
}


def render_template(template_body: str, **kwargs) -> str:
    """Render a template with portfolio link and business variables."""
    kwargs.setdefault("portfolio_link", portfolio_link(kwargs.get("business_name", "")))
    kwargs.setdefault("contact_name", kwargs.get("contact_name") or "there")
    return template_body.format(**kwargs)


def select_whatsapp_template(website_status: str) -> str:
    """Pick WhatsApp template key based on website status."""
    if website_status in ("broken", "parked", "placeholder", "poor"):
        return "broken_website_primary"
    return "no_website_primary"


def select_sms_template(website_status: str) -> str:
    """Pick SMS template key based on website status."""
    if website_status in ("broken", "parked", "placeholder", "poor"):
        return "broken_website_primary"
    return "no_website_primary"


def select_email_template(website_status: str) -> str:
    """Pick email template key based on website status."""
    if website_status in ("broken", "parked", "placeholder", "poor"):
        return "broken_website_primary"
    return "no_website_primary"
