from typing import Annotated

from fastapi import APIRouter, Query

from app.core.enums import Role
from app.deps import CurrentUser, SessionDep
from app.schemas.user import UserOut
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
