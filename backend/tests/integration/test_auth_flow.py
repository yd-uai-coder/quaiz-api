import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_register_login_and_access_protected_route(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"display_name": "erin", "password": "s3cret-pass"},
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"display_name": "erin", "password": "s3cret-pass"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()

    me_response = await client.get(
        "/api/v1/users/profile",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["display_name"] == "erin"

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    refreshed_tokens = refresh_response.json()
    assert "access_token" in refreshed_tokens
    assert refreshed_tokens["refresh_token"] != tokens["refresh_token"]

    # ローテーション済みの旧refresh tokenはもう使えない
    reuse_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse_response.status_code == 401

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refreshed_tokens["refresh_token"]}
    )
    assert logout_response.status_code == 204


async def test_register_duplicate_display_name_returns_409(client: AsyncClient) -> None:
    payload = {"display_name": "dupe", "password": "s3cret-pass"}
    await client.post("/api/v1/auth/register", json=payload)

    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409


async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"display_name": "wrongpass-pat", "password": "s3cret-pass"},
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"display_name": "wrongpass-pat", "password": "not-the-right-password"},
    )

    assert response.status_code == 401


async def test_refresh_with_garbage_token_returns_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401
