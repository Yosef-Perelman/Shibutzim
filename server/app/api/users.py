from typing import Annotated

from fastapi import APIRouter, Query

from app.core.enums import Role
from app.deps import CurrentUser, SessionDep
from app.schemas.user import UserCreate, UserOut, UserStatusUpdate
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(
    user: CurrentUser,
    session: SessionDep,
    role: Annotated[Role | None, Query(description="Only users with this role")] = None,
    is_active: Annotated[bool | None, Query(description="Only active or only inactive")] = None,
) -> list[UserOut]:
    users = user_service.list_users(session, user, role=role, is_active=is_active)
    return [UserOut.model_validate(item) for item in users]


@router.post("", status_code=201)
def create_user(body: UserCreate, user: CurrentUser, session: SessionDep) -> UserOut:
    created = user_service.create_user(session, user, **body.model_dump())
    return UserOut.model_validate(created)


@router.patch("/{user_id}")
def set_user_active(
    user_id: int, body: UserStatusUpdate, user: CurrentUser, session: SessionDep
) -> UserOut:
    changed = user_service.set_user_active(session, user, user_id, is_active=body.is_active)
    return UserOut.model_validate(changed)
