"""
app/tests/conftest.py — Shared pytest fixtures.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.main import app

# ── In-memory SQLite engine for tests ─────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_twilio_send(monkeypatch):
    """Mock Twilio send — returns a fake SID."""
    mock = MagicMock(return_value="SM" + "x" * 32)
    monkeypatch.setattr("app.integrations.twilio.adapter.send_whatsapp_message", mock)
    return mock


@pytest.fixture
def mock_openai_response():
    """Factory for mocked OpenAI structured output."""
    def _make(intent="greeting", reply="Merhba bik! 😊", needs_human=False):
        from app.schemas.openai_output import AIStructuredOutput, BookingEntities
        return AIStructuredOutput(
            intent=intent,
            language="darija_arabic",
            confidence=0.95,
            customer_facing_reply=reply,
            needs_human=needs_human,
            proposed_actions=[],
            entities=BookingEntities(),
        )
    return _make


@pytest.fixture
def sample_twilio_payload():
    """Sample Twilio inbound webhook payload."""
    return {
        "MessageSid": "SM" + "a" * 32,
        "SmsSid": "SM" + "a" * 32,
        "AccountSid": "AC" + "b" * 32,
        "From": "whatsapp:+212612345678",
        "To": "whatsapp:+212522000000",
        "Body": "Salam, bghit narf lprix",
        "NumMedia": "0",
        "WaId": "212612345678",
        "ProfileName": "Hassan",
    }
