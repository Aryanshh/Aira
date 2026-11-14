import uuid
from datetime import time
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, description="Minimum 10 characters")
    full_name: str = Field(min_length=1, max_length=255)
    phone_e164: Optional[str] = None
    preferred_language: str = Field(default="en", pattern="^(en|hi)$")
    timezone: str = Field(default="Asia/Kolkata")


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10, description="Minimum 10 characters")


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone_e164: Optional[str] = None
    preferred_language: str
    timezone: str
    quiet_start: Optional[time] = None
    quiet_end: Optional[time] = None
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_e164: Optional[str] = None
    preferred_language: Optional[str] = Field(None, pattern="^(en|hi)$")
    timezone: Optional[str] = None
    quiet_start: Optional[time] = None
    quiet_end: Optional[time] = None
