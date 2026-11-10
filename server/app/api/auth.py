from fastapi import APIRouter

from app.deps import CurrentUser, NowDep, SessionDep
from app.schemas.auth import LoginRequest, TokenOut
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, session: SessionDep, now: NowDep) -> TokenOut:
    token, user = auth_service.login(session, body.email, body.password, now=now)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
