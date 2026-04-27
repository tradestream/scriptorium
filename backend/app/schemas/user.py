from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _validate_email(value: str) -> str:
    """Lightweight email check that accepts internal / .local addresses.

    Pydantic's ``EmailStr`` rejects valid TLDs like ``.local`` and ``.lan``
    that self-hosted deployments use; ``UserRead.email`` is already a
    plain ``str`` for the same reason. We enforce the minimum invariant
    instead: one ``@``, non-empty local + domain parts, no whitespace,
    bounded length. Lowercase + strip on the way in for consistent
    storage.
    """
    if not isinstance(value, str):
        raise ValueError("email must be a string")
    cleaned = value.strip().lower()
    if len(cleaned) < 3 or len(cleaned) > 255:
        raise ValueError("email length must be 3-255")
    if any(ch.isspace() for ch in cleaned):
        raise ValueError("email must not contain whitespace")
    if cleaned.count("@") != 1:
        raise ValueError("email must contain exactly one '@'")
    local, _, domain = cleaned.partition("@")
    if not local or not domain or "." not in domain[1:]:
        # require at least one '.' in the domain past the first char so
        # something like "a@b" is rejected but "x@host.local" passes
        raise ValueError("email must have a local part and a dotted domain")
    return cleaned


class UserBase(BaseModel):
    """User base schema."""

    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=3, max_length=255)

    _email_validator = field_validator("email")(_validate_email)


class UserCreate(UserBase):
    """User create schema."""

    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    """User update schema (self-service profile edit)."""
    display_name: Optional[str] = None
    email: Optional[str] = None


class UserRead(BaseModel):
    """User read schema."""

    id: int
    username: str
    display_name: Optional[str] = None
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
