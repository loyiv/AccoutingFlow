from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, db_session, get_current_user
from app.api.schemas.auth import LoginRequest, MeResponse, TokenResponse
from app.core.security import create_access_token, verify_password
from app.infra.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(db_session)) -> TokenResponse:
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token(subject=user.username, role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(u: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(id=u.id, username=u.username, role=u.role)


