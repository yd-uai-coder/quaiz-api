import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User, UserCredential, UserRole

pytestmark = pytest.mark.integration


async def _register_and_login(client: AsyncClient, display_name: str) -> tuple[str, str]:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"display_name": display_name, "password": "s3cret-pass"},
    )
    user_id = register_response.json()["id"]
    login_response = await client.post(
        "/api/v1/auth/login", json={"display_name": display_name, "password": "s3cret-pass"}
    )
    return user_id, login_response.json()["access_token"]


async def _promote_to_admin(display_name: str) -> None:
    async with AsyncSessionLocal() as session:
        credential = (
            await session.execute(
                select(UserCredential)
                .join(User, User.id == UserCredential.user_id)
                .where(User.display_name == display_name)
            )
        ).scalar_one()
        credential.role = UserRole.ADMIN
        await session.commit()


async def test_list_users_requires_admin(client: AsyncClient) -> None:
    _, token = await _register_and_login(client, "member1")

    response = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


async def test_list_users_returns_all_users_for_admin(client: AsyncClient) -> None:
    await _register_and_login(client, "member2")
    admin_id, admin_token = await _register_and_login(client, "admin-lister")
    await _promote_to_admin("admin-lister")
    # ロール変更後は新しいトークンを取り直す必要はない(roleはDBから毎回引くため)

    response = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})

    assert response.status_code == 200
    display_names = {u["display_name"] for u in response.json()}
    assert {"member2", "admin-lister"} <= display_names
    assert admin_id in {u["id"] for u in response.json()}


async def test_update_user_self_change_display_name(client: AsyncClient) -> None:
    user_id, token = await _register_and_login(client, "renamer")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        f"/api/v1/users/{user_id}",
        json={"display_name": "renamer2"},
        headers=headers,
    )

    assert response.status_code == 204
    profile = await client.get("/api/v1/users/profile", headers=headers)
    assert profile.json()["display_name"] == "renamer2"


async def test_update_user_rejects_other_user(client: AsyncClient) -> None:
    target_id, _ = await _register_and_login(client, "target-user")
    _, actor_token = await _register_and_login(client, "actor-user")

    response = await client.patch(
        f"/api/v1/users/{target_id}",
        json={"display_name": "hacked"},
        headers={"Authorization": f"Bearer {actor_token}"},
    )

    assert response.status_code == 403


async def test_update_user_self_password_requires_current_password(client: AsyncClient) -> None:
    user_id, token = await _register_and_login(client, "pwchanger")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        f"/api/v1/users/{user_id}", json={"password": "newpass123"}, headers=headers
    )

    assert response.status_code == 400


async def test_delete_user_self(client: AsyncClient) -> None:
    user_id, token = await _register_and_login(client, "self-deleter")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete(f"/api/v1/users/{user_id}", headers=headers)

    assert response.status_code == 204


async def test_bulk_delete_users_requires_admin(client: AsyncClient) -> None:
    target_id, _ = await _register_and_login(client, "bulk-target")
    _, actor_token = await _register_and_login(client, "bulk-actor")

    response = await client.post(
        "/api/v1/users/bulk-delete",
        json={"user_ids": [target_id]},
        headers={"Authorization": f"Bearer {actor_token}"},
    )

    assert response.status_code == 403


async def test_bulk_delete_users_removes_targets_for_admin(client: AsyncClient) -> None:
    target_id, _ = await _register_and_login(client, "bulk-target-2")
    admin_id, admin_token = await _register_and_login(client, "bulk-admin")
    await _promote_to_admin("bulk-admin")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    response = await client.post(
        "/api/v1/users/bulk-delete",
        json={"user_ids": [target_id]},
        headers=admin_headers,
    )

    assert response.status_code == 204
    remaining_ids = {
        u["id"] for u in (await client.get("/api/v1/users", headers=admin_headers)).json()
    }
    assert target_id not in remaining_ids
    assert admin_id in remaining_ids
