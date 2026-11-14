import uuid
from typing import Optional
from fastapi import Cookie, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User


async def get_current_user(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract authenticated user from Authorization header or httpOnly cookie."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif access_token:
        token = access_token

    if not token:
        raise UnauthorizedError(detail="Authentication required.", code="NOT_AUTHENTICATED")

    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise UnauthorizedError(detail=str(e), code="INVALID_TOKEN")

    if payload.get("type") != "access" or payload.get("role") != "user":
        raise UnauthorizedError(detail="Invalid token type.", code="INVALID_TOKEN_TYPE")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError(detail="Token subject missing.", code="INVALID_TOKEN_SUBJECT")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedError(detail="Malformed user ID.", code="MALFORMED_ID")

    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError(detail="User no longer exists.", code="USER_NOT_FOUND")

    return user


class CurrentActor:
    def __init__(self, actor_type: str, user: Optional[User] = None, elder_id: Optional[uuid.UUID] = None):
        self.actor_type = actor_type  # "user" or "elder"
        self.user = user
        self.elder_id = elder_id

    @property
    def is_user(self) -> bool:
        return self.actor_type == "user"

    @property
    def is_elder(self) -> bool:
        return self.actor_type == "elder"


async def get_current_actor(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> CurrentActor:
    """Extract authenticated actor (user or elder) from token."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif access_token:
        token = access_token

    if not token:
        raise UnauthorizedError(detail="Authentication required.", code="NOT_AUTHENTICATED")

    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise UnauthorizedError(detail=str(e), code="INVALID_TOKEN")

    role = payload.get("role")
    sub_str = payload.get("sub")
    if not sub_str:
        raise UnauthorizedError(detail="Token subject missing.", code="INVALID_TOKEN_SUBJECT")

    try:
        sub_uuid = uuid.UUID(sub_str)
    except ValueError:
        raise UnauthorizedError(detail="Malformed subject ID.", code="MALFORMED_ID")

    if role == "elder":
        return CurrentActor(actor_type="elder", elder_id=sub_uuid)
    elif role == "user":
        stmt = select(User).where(User.id == sub_uuid, User.deleted_at.is_(None))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise UnauthorizedError(detail="User no longer exists.", code="USER_NOT_FOUND")
        return CurrentActor(actor_type="user", user=user)
    else:
        raise UnauthorizedError(detail="Unknown token role.", code="INVALID_TOKEN_ROLE")
