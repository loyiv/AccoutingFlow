from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose.exceptions import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.infra.db.models import User
from app.infra.db.session import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def db_session() -> Generator[Session, None, None]:
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def auth_db_session() -> Generator[Session, None, None]:
    """
    重要：鉴权依赖会查询 users 表，这会在 SQLAlchemy 2 里触发隐式事务（autobegin）。
    若与业务接口共用同一个 Session，则业务侧再调用 `with db.begin():` 会报
    `InvalidRequestError: A transaction is already begun on this Session.`

    因此鉴权使用独立 Session，避免污染业务请求的事务边界。
    """
    db = get_session()
    try:
        yield db
    finally:
        db.close()


@dataclass(frozen=True)
class CurrentUser:
    id: str
    username: str
    role: str


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(auth_db_session)) -> CurrentUser:
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的 token")

    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 缺少必要字段")

    user = db.query(User).filter(User.username == username).one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    return CurrentUser(id=str(user.id), username=user.username, role=user.role)


def require_roles(roles: Iterable[str]):
    roles_set = set(roles)

    def _dep(u: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if u.role not in roles_set:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return u

    return _dep


