import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserRole
from app.schemas.user import UserUpdateRequest
from app.services.errors import (
    InvalidCurrentPasswordError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserPermissionDeniedError,
)
from app.services.user import UserService


async def test_create_user_hashes_password(db_session: AsyncSession) -> None:
    service = UserService(db_session)

    user = await service.create_user(display_name="alice", password="s3cret")

    assert user.display_name == "alice"
    assert user.credential.hashed_password != "s3cret"


async def test_create_user_rejects_duplicate_display_name(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    await service.create_user(display_name="bob", password="s3cret")

    with pytest.raises(UserAlreadyExistsError):
        await service.create_user(display_name="bob", password="other")


async def test_list_users_returns_all_users_sorted_by_display_name(
    db_session: AsyncSession,
) -> None:
    service = UserService(db_session)
    await service.create_user(display_name="zeta", password="s3cret")
    await service.create_user(display_name="alpha", password="s3cret")

    users = await service.list_users()

    assert [u.display_name for u in users] == ["alpha", "zeta"]


async def test_get_by_display_name_returns_none_when_missing(db_session: AsyncSession) -> None:
    service = UserService(db_session)

    user = await service.get_by_display_name("nobody")

    assert user is None


async def test_get_by_id_returns_created_user(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    created = await service.create_user(display_name="carol", password="s3cret")

    fetched = await service.get_by_id(created.id)

    assert fetched is not None
    assert fetched.display_name == "carol"


async def test_update_user_allows_self_to_change_display_name(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    user = await service.create_user(display_name="erin", password="s3cret")

    updated = await service.update_user(
        actor=user,
        target_user_id=user.id,
        data=UserUpdateRequest(display_name="erin2"),
    )

    assert updated.display_name == "erin2"


async def test_update_user_rejects_other_users_change(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    actor = await service.create_user(display_name="frank", password="s3cret")
    target = await service.create_user(display_name="george", password="s3cret")

    with pytest.raises(UserPermissionDeniedError):
        await service.update_user(
            actor=actor, target_user_id=target.id, data=UserUpdateRequest(display_name="hacked")
        )


async def test_update_user_allows_admin_to_change_other_user(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    admin = await service.create_user(display_name="admin1", password="s3cret")
    admin.credential.role = UserRole.ADMIN
    target = await service.create_user(display_name="harriet", password="s3cret")

    updated = await service.update_user(
        actor=admin, target_user_id=target.id, data=UserUpdateRequest(display_name="harriet2")
    )

    assert updated.display_name == "harriet2"


async def test_update_user_rejects_role_change_by_non_admin(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    user = await service.create_user(display_name="ian", password="s3cret")

    with pytest.raises(UserPermissionDeniedError):
        await service.update_user(
            actor=user, target_user_id=user.id, data=UserUpdateRequest(role=UserRole.ADMIN)
        )


async def test_update_user_allows_admin_to_change_role(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    admin = await service.create_user(display_name="admin2", password="s3cret")
    admin.credential.role = UserRole.ADMIN
    target = await service.create_user(display_name="jane", password="s3cret")

    updated = await service.update_user(
        actor=admin, target_user_id=target.id, data=UserUpdateRequest(role=UserRole.ADMIN)
    )

    assert updated.role == UserRole.ADMIN


async def test_update_user_self_password_change_requires_current_password(
    db_session: AsyncSession,
) -> None:
    service = UserService(db_session)
    user = await service.create_user(display_name="kevin", password="s3cret")

    with pytest.raises(InvalidCurrentPasswordError):
        await service.update_user(
            actor=user, target_user_id=user.id, data=UserUpdateRequest(password="newpass")
        )


async def test_update_user_self_password_change_succeeds_with_correct_current_password(
    db_session: AsyncSession,
) -> None:
    service = UserService(db_session)
    user = await service.create_user(display_name="laura", password="s3cret")
    original_hash = user.credential.hashed_password

    updated = await service.update_user(
        actor=user,
        target_user_id=user.id,
        data=UserUpdateRequest(password="newpass", current_password="s3cret"),
    )

    assert updated.credential.hashed_password != original_hash


async def test_update_user_admin_can_change_other_password_without_current_password(
    db_session: AsyncSession,
) -> None:
    service = UserService(db_session)
    admin = await service.create_user(display_name="admin3", password="s3cret")
    admin.credential.role = UserRole.ADMIN
    target = await service.create_user(display_name="mike", password="s3cret")
    original_hash = target.credential.hashed_password

    updated = await service.update_user(
        actor=admin, target_user_id=target.id, data=UserUpdateRequest(password="newpass")
    )

    assert updated.credential.hashed_password != original_hash


async def test_delete_user_allows_self_delete(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    user = await service.create_user(display_name="nancy", password="s3cret")

    await service.delete_user(actor=user, target_user_id=user.id)

    assert await service.get_by_id(user.id) is None


async def test_delete_user_rejects_other_users_delete(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    actor = await service.create_user(display_name="oscar", password="s3cret")
    target = await service.create_user(display_name="paula", password="s3cret")

    with pytest.raises(UserPermissionDeniedError):
        await service.delete_user(actor=actor, target_user_id=target.id)


async def test_delete_user_allows_admin_delete(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    admin = await service.create_user(display_name="admin4", password="s3cret")
    admin.credential.role = UserRole.ADMIN
    target = await service.create_user(display_name="quinn", password="s3cret")

    await service.delete_user(actor=admin, target_user_id=target.id)

    assert await service.get_by_id(target.id) is None


async def test_delete_user_raises_not_found_for_unknown_target(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    admin = await service.create_user(display_name="admin5", password="s3cret")
    admin.credential.role = UserRole.ADMIN

    with pytest.raises(UserNotFoundError):
        await service.delete_user(actor=admin, target_user_id=uuid.uuid4())


async def test_bulk_delete_users_removes_all_given_ids(db_session: AsyncSession) -> None:
    service = UserService(db_session)
    a = await service.create_user(display_name="rachel", password="s3cret")
    b = await service.create_user(display_name="sam", password="s3cret")

    await service.bulk_delete_users(user_ids=[a.id, b.id])

    assert await service.get_by_id(a.id) is None
    assert await service.get_by_id(b.id) is None
