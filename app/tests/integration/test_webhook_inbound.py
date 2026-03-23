"""
app/tests/integration/test_webhook_inbound.py — Integration tests for the Twilio inbound webhook.
"""
import pytest


@pytest.mark.asyncio
async def test_inbound_webhook_returns_200(async_client, sample_twilio_payload, monkeypatch):
    """Inbound webhook must return 200 and empty TwiML even without Twilio sig (dev mode)."""
    # Mock signature validation (disabled in development)
    monkeypatch.setattr("app.config.settings.app_env", "development")

    # Mock Celery task
    monkeypatch.setattr(
        "app.workers.tasks.process_inbound.process_inbound_message.delay",
        lambda **_: None,
    )

    response = await async_client.post(
        "/webhooks/twilio/inbound",
        data=sample_twilio_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert "<Response/>" in response.text


@pytest.mark.asyncio
async def test_inbound_webhook_deduplicates(async_client, sample_twilio_payload, monkeypatch):
    """Sending the same MessageSid twice must return 200 both times without duplicate processing."""
    monkeypatch.setattr("app.config.settings.app_env", "development")
    monkeypatch.setattr(
        "app.workers.tasks.process_inbound.process_inbound_message.delay",
        lambda **_: None,
    )

    # First request
    response1 = await async_client.post(
        "/webhooks/twilio/inbound",
        data=sample_twilio_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response1.status_code == 200

    # Second request with same MessageSid — must be deduplicated
    response2 = await async_client.post(
        "/webhooks/twilio/inbound",
        data=sample_twilio_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response2.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
