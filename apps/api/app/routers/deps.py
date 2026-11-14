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
