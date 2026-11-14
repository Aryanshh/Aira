import uuid
from datetime import timedelta
from typing import Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_random_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.time import utc_now, ensure_utc
from app.models.user import User, UserRefreshToken
from app.models.notification import Outbox


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        phone_e164: Optional[str] = None,
        preferred_language: str = "en",
        timezone: str = "Asia/Kolkata",
    ) -> Tuple[User, str]:
        """Register a new user and generate a 24h email verification token."""
        normalized_email = email.strip().lower()

        # Check existing user
        stmt = select(User).where(User.email == normalized_email)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ConflictError(
                detail="An account with this email address already exists.",
                code="EMAIL_ALREADY_EXISTS",
            )

        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            phone_e164=phone_e164,
            preferred_language=preferred_language,
            timezone=timezone,
            email_verified_at=None,
        )
        self.db.add(user)
        await self.db.flush()

        # In development and test mode, auto-verify
        verification_token = generate_random_token()
        if settings.APP_ENV in ("development", "test"):
            user.email_verified_at = utc_now()

        # Queue verification email in outbox
        outbox_entry = Outbox(
            channel="email",
            recipient=normalized_email,
            template_key="system.verify_email",
            language=preferred_language,
            params={
                "name": full_name,
                "verification_token": verification_token,
                "link": f"{settings.WEB_ORIGIN}/verify-email?token={verification_token}",
            },
            dedupe_key=f"verify:{user.id}:{verification_token[:8]}",
        )
        self.db.add(outbox_entry)

        return user, verification_token

    async def verify_email(self, token: str) -> User:
        """Verify user's email address."""
        # Find matching outbox entry with this token
        stmt = select(Outbox).where(
            Outbox.template_key == "system.verify_email",
            Outbox.created_at >= utc_now() - timedelta(hours=settings.VERIFY_TOKEN_EXPIRE_HOURS),
        )
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        matching_email = None
        for entry in entries:
            if entry.params.get("verification_token") == token:
                matching_email = entry.recipient
                break

        if not matching_email:
            raise UnauthorizedError(
                detail="Verification link is invalid or has expired.",
                code="INVALID_VERIFICATION_TOKEN",
            )

        user_stmt = select(User).where(User.email == matching_email)
        user_res = await self.db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if not user:
            raise NotFoundError(detail="User not found.")

        user.email_verified_at = utc_now()
        return user

    async def login(self, email: str, password: str) -> Tuple[User, str, str]:
        """Authenticate user and issue access token and refresh token family."""
        normalized_email = email.strip().lower()

        stmt = select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError(
                detail="Incorrect email or password.",
                code="INVALID_CREDENTIALS",
            )

        if not user.email_verified_at and settings.APP_ENV != "development":
            raise UnauthorizedError(
                detail="Please verify your email before logging in.",
                code="EMAIL_NOT_VERIFIED",
            )

        # Generate refresh token family
        family_id = uuid.uuid4()
        raw_refresh_token = generate_random_token(48)
        refresh_token_hash = hash_token(raw_refresh_token)

        refresh_record = UserRefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=refresh_token_hash,
            expires_at=utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(refresh_record)
        await self.db.flush()

        access_token = create_access_token(
            subject=str(user.id),
            claims={"role": "user", "email": user.email},
        )

        return user, access_token, raw_refresh_token

    async def refresh_tokens(self, raw_refresh_token: str) -> Tuple[User, str, str]:
        """Rotate refresh token. Revoke entire token family on reuse detection (AUTH-2)."""
        token_hash = hash_token(raw_refresh_token)

        stmt = select(UserRefreshToken).where(UserRefreshToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise UnauthorizedError(detail="Invalid refresh session.", code="INVALID_REFRESH_TOKEN")

        # Reuse detection: if token is already revoked, someone is attempting to reuse it!
        if record.revoked_at is not None:
            # Revoke entire token family immediately and persist revocation
            revoke_family_stmt = (
                update(UserRefreshToken)
                .where(UserRefreshToken.family_id == record.family_id)
                .values(revoked_at=utc_now())
            )
            await self.db.execute(revoke_family_stmt)
            await self.db.commit()
            raise UnauthorizedError(
                detail="Security alert: Token reuse detected. All sessions in this family have been revoked.",
                code="TOKEN_FAMILY_REVOKED",
            )

        # Check expiration
        if ensure_utc(record.expires_at) <= utc_now():
            record.revoked_at = utc_now()
            raise UnauthorizedError(detail="Session has expired. Please log in again.", code="REFRESH_TOKEN_EXPIRED")

        # Revoke current token as part of rotation
        record.revoked_at = utc_now()

        # Load user
        user_stmt = select(User).where(User.id == record.user_id, User.deleted_at.is_(None))
        user_res = await self.db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if not user:
            raise UnauthorizedError(detail="User account no longer active.", code="USER_INACTIVE")

        # Create new refresh token in same family
        new_raw_refresh_token = generate_random_token(48)
        new_token_hash = hash_token(new_raw_refresh_token)

        new_record = UserRefreshToken(
            user_id=user.id,
            family_id=record.family_id,
            token_hash=new_token_hash,
            expires_at=utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(new_record)
        await self.db.flush()

        access_token = create_access_token(
            subject=str(user.id),
            claims={"role": "user", "email": user.email},
        )

        return user, access_token, new_raw_refresh_token

    async def logout(self, raw_refresh_token: Optional[str]) -> None:
        """Revoke the current refresh token session."""
        if not raw_refresh_token:
            return
        token_hash = hash_token(raw_refresh_token)
        stmt = select(UserRefreshToken).where(UserRefreshToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if record and not record.revoked_at:
            record.revoked_at = utc_now()

    async def request_password_reset(self, email: str) -> None:
        """Create a single-use 1-hour password reset link and queue in outbox."""
        normalized_email = email.strip().lower()
        stmt = select(User).where(User.email == normalized_email, User.deleted_at.is_(None))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Never reveal if user exists
            return

        reset_token = generate_random_token(32)
        outbox_entry = Outbox(
            channel="email",
            recipient=normalized_email,
            template_key="system.password_reset",
            language=user.preferred_language,
            params={
                "name": user.full_name,
                "reset_token": reset_token,
                "link": f"{settings.WEB_ORIGIN}/reset-password?token={reset_token}",
            },
            dedupe_key=f"pwd_reset:{user.id}:{utc_now().strftime('%Y%m%d%H')}",
        )
        self.db.add(outbox_entry)

    async def reset_password(self, token: str, new_password: str) -> User:
        """Reset password using a valid reset token from outbox."""
        stmt = select(Outbox).where(
            Outbox.template_key == "system.password_reset",
            Outbox.created_at >= utc_now() - timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        )
        result = await self.db.execute(stmt)
        entries = result.scalars().all()

        matching_email = None
        target_entry = None
        for entry in entries:
            if entry.params.get("reset_token") == token:
                matching_email = entry.recipient
                target_entry = entry
                break

        if not matching_email or not target_entry:
            raise UnauthorizedError(
                detail="Password reset token is invalid or has expired.",
                code="INVALID_RESET_TOKEN",
            )

        user_stmt = select(User).where(User.email == matching_email)
        user_res = await self.db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if not user:
            raise NotFoundError(detail="User not found.")

        # Update password
        user.password_hash = hash_password(new_password)

        # Invalidate the used token by removing it from params
        target_entry.params = {**target_entry.params, "used": True, "reset_token": ""}

        # Revoke all existing sessions for security
        revoke_all_stmt = (
            update(UserRefreshToken)
            .where(UserRefreshToken.user_id == user.id)
            .values(revoked_at=utc_now())
        )
        await self.db.execute(revoke_all_stmt)

        return user
