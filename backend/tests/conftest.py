"""
Shared pytest fixtures. Two important design choices here:

1. The AI provider (generate_text) is mocked globally for all tests in this
   file's scope - tests must never call the real Gemini API (see Phase 11
   notes: cost, speed, determinism).

2. Tests run against the real Neon database via a real HTTP client, using
   throwaway accounts created and cleaned up per-test. This project is too
   small to justify a separate test database/mocking layer for SQLAlchemy -
   that would be real infrastructure overhead this portfolio project doesn't
   need (see project ground rules on avoiding overengineering).
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from main import app


@pytest.fixture
def mock_ai_response():
    """Patches services.ai.provider.generate_text so no test ever calls the
    real Gemini API. Import path matters: we patch it where it's *used*
    (routers.ai), not where it's *defined* (services.ai.provider) - this is
    a common Python mocking gotcha worth knowing."""
    with patch("routers.ai.generate_text", new_callable=AsyncMock) as mock:
        mock.return_value = "This is a mocked AI response for testing."
        yield mock


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(client):
    """Creates a throwaway user for a single test and returns (email, token,
    auth_headers). Uses a random email so repeated test runs never collide
    with a leftover account from a previous run."""
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPassword123"

    response = await client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, f"Test user setup failed: {response.text}"

    token = response.json()["access_token"]
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
async def second_test_user(client):
    """A second, independent throwaway user - needed specifically for
    isolation tests where two different users must not see each other's
    data."""
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPassword123"

    response = await client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, f"Second test user setup failed: {response.text}"

    token = response.json()["access_token"]
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}
