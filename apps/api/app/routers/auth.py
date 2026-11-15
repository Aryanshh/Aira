from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.errors import UnauthorizedError
from app.models.user import User
from app.routers.deps import get_current_user
from app.schemas.auth import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateUserRequest,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService

from app.schemas.elder import ElderLoginRequest, ElderQrLoginRequest
from app.services.elder_service import ElderService

router = APIRouter(prefix="/api/v1", tags=["Authentication"])


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set secure httpOnly cookies for access and refresh tokens (AUTH-2)."""
    cookie_domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=cookie_domain,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        domain=cookie_domain,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear session cookies."""
    cookie_domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    response.delete_cookie(key="access_token", domain=cookie_domain, path="/")
    response.delete_cookie(key="refresh_token", domain=cookie_domain, path="/")


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new family or caregiver account (AUTH-1)."""
    service = AuthService(db)
    user, _ = await service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone_e164=payload.phone_e164,
        preferred_language=payload.preferred_language,
        timezone=payload.timezone,
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_e164=user.phone_e164,
        preferred_language=user.preferred_language,
        timezone=user.timezone,
        quiet_start=user.quiet_start,
        quiet_end=user.quiet_end,
        is_verified=user.email_verified_at is not None,
    )


@router.post("/auth/verify-email", response_model=UserResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Confirm user email address using single-use verification link (AUTH-1)."""
    service = AuthService(db)
    user = await service.verify_email(payload.token)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_e164=user.phone_e164,
        preferred_language=user.preferred_language,
        timezone=user.timezone,
        quiet_start=user.quiet_start,
        quiet_end=user.quiet_end,
        is_verified=True,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email and password, setting httpOnly cookies (AUTH-2)."""
    service = AuthService(db)
    user, access_token, refresh_token = await service.login(payload.email, payload.password)
    set_auth_cookies(response, access_token, refresh_token)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Rotate refresh tokens. Detects reuse and revokes token family (AUTH-2)."""
    if not refresh_token:
        raise UnauthorizedError(detail="Refresh token required.", code="MISSING_REFRESH_TOKEN")

    service = AuthService(db)
    user, new_access, new_refresh = await service.refresh_tokens(refresh_token)
    set_auth_cookies(response, new_access, new_refresh)
    return TokenResponse(
        access_token=new_access,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/auth/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke session and clear cookies."""
    service = AuthService(db)
    await service.logout(refresh_token)
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.post("/auth/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send 1-hour single-use password reset link (AUTH-3)."""
    service = AuthService(db)
    await service.request_password_reset(payload.email)
    return {"message": "If this email is registered, a password reset link has been sent."}


@router.post("/auth/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset account password using reset token (AUTH-3)."""
    service = AuthService(db)
    await service.reset_password(payload.token, payload.new_password)
    return {"message": "Password reset successfully. Please log in with your new password."}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone_e164=current_user.phone_e164,
        preferred_language=current_user.preferred_language,
        timezone=current_user.timezone,
        quiet_start=current_user.quiet_start,
        quiet_end=current_user.quiet_end,
        is_verified=current_user.email_verified_at is not None,
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    payload: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update profile settings (language, timezone, phone, quiet hours)."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.phone_e164 is not None:
        current_user.phone_e164 = payload.phone_e164
    if payload.preferred_language is not None:
        current_user.preferred_language = payload.preferred_language
    if payload.timezone is not None:
        current_user.timezone = payload.timezone
    if payload.quiet_start is not None:
        current_user.quiet_start = payload.quiet_start
    if payload.quiet_end is not None:
        current_user.quiet_end = payload.quiet_end

    await db.flush()
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone_e164=current_user.phone_e164,
        preferred_language=current_user.preferred_language,
        timezone=current_user.timezone,
        quiet_start=current_user.quiet_start,
        quiet_end=current_user.quiet_end,
        is_verified=current_user.email_verified_at is not None,
    )


@router.post("/auth/elder/login", response_model=TokenResponse)
async def elder_login(
    payload: ElderLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Elder sign-in with access code and 4-digit PIN (AUTH-4)."""
    service = ElderService(db)
    elder, token = await service.elder_login(payload.access_code, payload.pin, payload.device_label)
    cookie_domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=30 * 86400,
        domain=cookie_domain,
        path="/",
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=30 * 86400,
    )


@router.post("/auth/elder/qr", response_model=TokenResponse)
async def elder_qr_login(
    payload: ElderQrLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Elder sign-in using personal QR login link (AUTH-4)."""
    service = ElderService(db)
    elder, token = await service.elder_qr_login(payload.token, payload.device_label)
    cookie_domain = settings.COOKIE_DOMAIN if settings.COOKIE_DOMAIN else None
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=30 * 86400,
        domain=cookie_domain,
        path="/",
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=30 * 86400,
    )
