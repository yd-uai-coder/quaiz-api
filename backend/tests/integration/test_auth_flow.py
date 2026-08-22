import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_register_login_and_access_protected_route(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "erin@example.com", "password": "s3cret-pass", "display_name": "Erin"},
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "erin@example.com", "password": "s3cret-pass"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()

    me_response = await client.get(
        "/api/v1/users/profile",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "erin@example.com"

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    assert "access_token" in refresh_response.json()

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout_response.status_code == 204


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    payload = {"email": "dupe@example.com", "password": "s3cret-pass", "display_name": "Dupe"}
    await client.post("/api/v1/auth/register", json=payload)

    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409


async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpass@example.com", "password": "s3cret-pass", "display_name": "Pat"},
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "not-the-right-password"},
    )

    assert response.status_code == 401


async def test_refresh_with_garbage_token_returns_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401
