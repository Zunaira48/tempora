"""
Phase 11: AI endpoint security tests.

Covers what Section 40 of the project brief specifically calls for:
authentication, malformed input rejection, and user data isolation for
every AI feature. The AI provider itself is mocked (see conftest.py) - these
tests verify OUR code's behavior, not Gemini's.
"""

import pytest


# ---------- Authentication: every AI endpoint must require login ----------

@pytest.mark.asyncio
async def test_copilot_requires_authentication(client):
    response = await client.post("/ai/copilot", json={"city": "Lahore", "message": "hi"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_explain_weather_requires_authentication(client):
    response = await client.post("/ai/explain-weather", json={"city": "Lahore"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_activity_advisor_requires_authentication(client):
    response = await client.post("/ai/activity-advisor", json={"city": "Lahore", "activity": "running"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_plan_my_day_requires_authentication(client):
    response = await client.post("/ai/plan-my-day", json={"city": "Lahore", "plan_text": "lunch at noon"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_compare_cities_requires_authentication(client):
    response = await client.post("/ai/compare-cities", json={"city_a": "Lahore", "city_b": "Karachi"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_favorite_cities_today_requires_authentication(client):
    response = await client.get("/ai/favorite-cities-today")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_travel_brief_requires_authentication(client):
    response = await client.post(
        "/ai/travel-brief",
        json={"city": "Lahore", "start_date": "2026-09-10", "end_date": "2026-09-12"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_rejected(client):
    response = await client.post(
        "/ai/copilot",
        json={"city": "Lahore", "message": "hi"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401


# ---------- Malformed input: bad requests must fail cleanly, not crash ----------

@pytest.mark.asyncio
async def test_copilot_rejects_empty_message(client, test_user, mock_ai_response):
    response = await client.post(
        "/ai/copilot",
        json={"city": "Lahore", "message": ""},
        headers=test_user["headers"],
    )
    assert response.status_code == 422  # Pydantic min_length violation


@pytest.mark.asyncio
async def test_activity_advisor_rejects_unknown_activity(client, test_user, mock_ai_response):
    response = await client.post(
        "/ai/activity-advisor",
        json={"city": "Lahore", "activity": "skydiving"},
        headers=test_user["headers"],
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_copilot_rejects_unknown_city(client, test_user, mock_ai_response):
    response = await client.post(
        "/ai/copilot",
        json={"city": "asdkjhaskjdhaskjd", "message": "hi"},
        headers=test_user["headers"],
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_travel_brief_rejects_invalid_date_format(client, test_user, mock_ai_response):
    response = await client.post(
        "/ai/travel-brief",
        json={"city": "Lahore", "start_date": "not-a-date", "end_date": "2026-09-12"},
        headers=test_user["headers"],
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_travel_brief_rejects_end_before_start(client, test_user, mock_ai_response):
    response = await client.post(
        "/ai/travel-brief",
        json={"city": "Lahore", "start_date": "2026-09-15", "end_date": "2026-09-10"},
        headers=test_user["headers"],
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_travel_brief_rejects_overly_long_range(client, test_user, mock_ai_response):
    response = await client.post(
        "/ai/travel-brief",
        json={"city": "Lahore", "start_date": "2026-09-05", "end_date": "2026-09-30"},
        headers=test_user["headers"],
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_copilot_rejects_overly_long_message(client, test_user, mock_ai_response):
    response = await client.post(
        "/ai/copilot",
        json={"city": "Lahore", "message": "x" * 1000},
        headers=test_user["headers"],
    )
    assert response.status_code == 422  # exceeds AI_MAX_INPUT_CHARS


# ---------- User isolation: AI must never leak one user's data to another ----------

@pytest.mark.asyncio
async def test_favorite_cities_today_isolated_between_users(client, test_user, second_test_user, mock_ai_response):
    # User A favorites Lahore
    add_response = await client.post(
        "/favorites",
        json={"city_name": "Lahore", "country": "Pakistan", "latitude": 31.55, "longitude": 74.34},
        headers=test_user["headers"],
    )
    assert add_response.status_code == 201

    # User B has no favorites at all - must get a 404, never User A's data
    response = await client.get("/ai/favorite-cities-today", headers=second_test_user["headers"])
    assert response.status_code == 404
    assert "Lahore" not in response.text


@pytest.mark.asyncio
async def test_favorite_cities_today_returns_only_own_favorites(client, test_user, second_test_user, mock_ai_response):
    # User A favorites Lahore
    await client.post(
        "/favorites",
        json={"city_name": "Lahore", "country": "Pakistan", "latitude": 31.55, "longitude": 74.34},
        headers=test_user["headers"],
    )
    # User B favorites Karachi
    await client.post(
        "/favorites",
        json={"city_name": "Karachi", "country": "Pakistan", "latitude": 24.86, "longitude": 67.01},
        headers=second_test_user["headers"],
    )

    response_a = await client.get("/ai/favorite-cities-today", headers=test_user["headers"])
    response_b = await client.get("/ai/favorite-cities-today", headers=second_test_user["headers"])

    cities_a = [c["city"] for c in response_a.json()["cities"]]
    cities_b = [c["city"] for c in response_b.json()["cities"]]

    assert "Lahore" in cities_a
    assert "Karachi" not in cities_a
    assert "Karachi" in cities_b
    assert "Lahore" not in cities_b