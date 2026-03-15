from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """User base schema."""

    username: str = Field(min_length=3, max_length=100)
    email: EmailStr


class UserCreate(UserBase):
    """User create schema."""

    password: str = Field(min_length=8)


class UserRead(BaseModel):
    """User read schema."""

    id: int
    username: str
    email: str  # plain str — EmailStr is too strict for internal/local addresses
    is_admin: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: int
    exp: int
    iat: int
    admin: bool = False


class LoginRequest(BaseModel):
    """Login request schema."""

    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str
