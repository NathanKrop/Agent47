"""Outreach module tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from config.templates import render_template, select_whatsapp_template
from outreach.channel_router import ChannelRouter
from outreach.rate_limiter import RateLimiter


def test_templates_render_with_business_name():
    body = (
        "Hello {business_name}! See my work: {portfolio_link}"
    )
    rendered = render_template(body, business_name="Test Salon")
    assert "Test Salon" in rendered
    assert "nathan-krop-website2.vercel.app" in rendered


def test_select_whatsapp_template_broken():
    assert select_whatsapp_template("broken") == "broken_website_primary"
    assert select_whatsapp_template("no_website") == "no_website_primary"


@pytest.mark.asyncio
async def test_channel_router_selects_whatsapp():
    router = ChannelRouter()
    router.rate_limiter.can_send = AsyncMock(return_value=True)
    router.rate_limiter.record_send = AsyncMock()
    router.whatsapp.send_text = AsyncMock(return_value={"channel": "whatsapp", "status": "sent"})

    listing = {
        "id": "test123",
        "name": "Test Business",
        "phone": "+254712345678",
        "website_status": "no_website",
    }

    with patch("outreach.channel_router.is_do_not_contact", return_value=False):
        with patch("outreach.channel_router.log_outreach"):
            result = await router.route_and_send(listing)

    assert result["channel"] == "whatsapp"
    assert result["status"] == "sent"


@pytest.mark.asyncio
async def test_channel_router_respects_dnc():
    router = ChannelRouter()
    listing = {
        "id": "test456",
        "name": "DNC Business",
        "phone": "+254700000000",
        "website_status": "no_website",
    }

    with patch("outreach.channel_router.is_do_not_contact", return_value=True):
        result = await router.route_and_send(listing)

    assert result["status"] == "do_not_contact"


@pytest.mark.asyncio
async def test_rate_limiter_can_send_mock():
    limiter = RateLimiter(redis_url="redis://localhost:6379/15")
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.pipeline = MagicMock(return_value=AsyncMock())
    limiter._redis = mock_redis

    result = await limiter.can_send("+254712345678")
    assert result is True


def test_inbound_webhook_marks_reply():
    from dashboard.app import app

    client = TestClient(app)
    with patch("dashboard.app.mark_outreach_replied", return_value=True):
        response = client.post(
            "/api/inbound",
            json={"channel": "sms", "from_contact": "+254712345678", "message": "Yes please"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "replied"
    assert response.json()["recipient"] == "+254712345678"


def test_inbound_webhook_marks_opt_out():
    from dashboard.app import app

    client = TestClient(app)
    with patch("dashboard.app.mark_outreach_opted_out", return_value=True):
        response = client.post(
            "/api/inbound",
            json={"channel": "whatsapp", "from_contact": "+254712345678", "message": "STOP"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "opted_out"
    assert response.json()["recipient"] == "+254712345678"


def test_whatsapp_test_endpoint_uses_send_text():
    from dashboard.app import app

    client = TestClient(app)
    with patch("outreach.whatsapp_sender.WhatsAppSender.send_text", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.return_value = {"channel": "whatsapp", "status": "sent", "message_id": "test-id"}
        response = client.post(
            "/api/whatsapp_test",
            json={"phone_number": "+254712345678"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["result"]["status"] == "sent"
    mock_send_text.assert_awaited_once()
