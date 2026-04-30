from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserRead, UserUpdate
from app.services.auth import create_access_token, hash_password, verify_password, verify_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Extracts the Bearer token from the Authorization header
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_accessible_library_ids(db: AsyncSession, user: User) -> set[int] | None:
    """Return the set of library IDs accessible to a user, or None for admins (no filter).

    A library is accessible if it has NO rows in library_access (world-readable)
    OR it has a row explicitly granting access to this user.
    """
    if user.is_admin:
        return None  # admins see everything

    from app.models.library import Library, LibraryAccess

    # Library IDs that have at least one access grant (restricted)
    restricted_ids_q = select(LibraryAccess.library_id).distinct()

    # Library IDs explicitly granted to this user
    granted_result = await db.execute(
        select(LibraryAccess.library_id).where(LibraryAccess.user_id == user.id)
    )
    granted_ids = set(granted_result.scalars().all())

    # World-readable library IDs (no grants at all for that library)
    world_result = await db.execute(
        select(Library.id).where(Library.id.notin_(restricted_ids_q))
    )
    world_ids = set(world_result.scalars().all())

    return world_ids | granted_ids


async def assert_library_access(
    db: AsyncSession, user: User, library_id: int
) -> None:
    """Raise 404 unless the user can access the given library.

    Returns 404 (not 403) so callers do not leak the existence of objects in
    libraries the user cannot see.
    """
    accessible_ids = await get_accessible_library_ids(db, user)
    if accessible_ids is not None and library_id not in accessible_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def assert_edition_access(
    db: AsyncSession, user: User, edition_id: int
) -> "Edition":
    """Load an Edition by id and enforce per-user library access.

    Returns the Edition. Raises 404 if the edition does not exist or the user
    cannot access its library.
    """
    from app.models.edition import Edition

    edition = await db.get(Edition, edition_id)
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await assert_library_access(db, user, edition.library_id)
    return edition


# Path allowlist for query-string ``?token=`` auth. Browsers can't attach
# Authorization headers to ``<img src>`` or ``<a download href>``, so we
# accept the token in the URL for these endpoints only — and explicitly
# reject it for everything else, so a leaked URL is constrained to a
# media path rather than the full API surface.
import re as _re

_QUERY_TOKEN_ALLOWED_PATHS = _re.compile(
    r"^/api/v\d+/("
    r"books/\d+/cover"
    r"|editions/\d+/cover"
    r"|books/\d+/download/\d+"
    r"|editions/\d+/download/\d+"
    r"|books/\d+/files/\d+/manifest\.json"
    r"|books/\d+/files/\d+/pages(/\d+)?"
    r"|books/\d+/esoteric/export\.epub"
    r"|admin/backup"
    r"|admin/kobo-fonts/bundle"
    r"|events/ws"
    r")/?$"
)


async def get_current_user(
    request: Request,
    header_token: Optional[str] = Depends(_oauth2_scheme),
    query_token: Optional[str] = Query(default=None, alias="token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token or API key.

    Accepts the token from:
    - ``Authorization: Bearer <token>`` (JWT or ``sk_...`` API key) — preferred.
    - ``?token=<token>`` query parameter, **only** on the small allowlist
      of media / streaming paths (covers, downloads, comic pages, the
      esoteric EPUB export, admin backup, WS event upgrade). Any other
      path with a query token is rejected so a JWT pasted into a
      generic API URL doesn't auth past 401. Browsers can't attach
      ``Authorization`` headers to ``<img src>`` or ``<a download>``,
      which is why the allowlisted endpoints get this exception.
    """
    import hashlib
    from datetime import datetime, timezone

    if query_token and not _QUERY_TOKEN_ALLOWED_PATHS.match(request.url.path):
        # A query token on a non-media endpoint is most likely a leaked
        # URL or a misconfigured client. Refuse to honor it. A header
        # token on the same request would still authenticate normally.
        query_token = None

    token = header_token or query_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # API key path (prefix sk_)
    if token.startswith("sk_"):
        from app.models.api_key import ApiKey
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            api_key.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()
        except Exception:
            await db.rollback()
        result = await db.execute(select(User).where(User.id == api_key.user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # JWT path
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload.get("sub"))
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user. First registered user becomes admin."""
    # Check if user already exists
    stmt = select(User).where(User.username == user_data.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Check if this is the first user (make admin)
    stmt = select(func.count()).select_from(User)
    result = await db.execute(stmt)
    is_first_user = result.scalar() == 0

    # Create new user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_admin=is_first_user,
        is_active=True,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id, is_admin=user.is_admin)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=60 * 24,
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username and password."""
    stmt = select(User).where(User.username == credentials.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Create access token
    access_token = create_access_token(user.id, is_admin=user.is_admin)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=60 * 24,  # 24 hours in minutes
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user's profile (display name, email)."""
    if data.display_name is not None:
        current_user.display_name = data.display_name
    if data.email is not None:
        current_user.email = data.email
    await db.commit()
    await db.refresh(current_user)
    return current_user


# ── OIDC / SSO ────────────────────────────────────────────────────────────────

import hashlib
import hmac
import secrets
import urllib.parse

import httpx
from fastapi.responses import RedirectResponse

from app.config import get_settings


def _sign_state(nonce: str, secret: str) -> str:
    """Create an HMAC-SHA256 signed state token for CSRF protection."""
    sig = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{sig}"


def _verify_state(state: str, secret: str) -> bool:
    """Verify a state token returned from the OIDC provider."""
    try:
        nonce, sig = state.rsplit(".", 1)
        expected = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


async def _get_oidc_config(discovery_url: str) -> dict:
    """Fetch the OpenID Connect discovery document."""
    url = discovery_url.rstrip("/") + "/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


@router.get("/oidc/config")
async def oidc_config():
    """Return whether OIDC is enabled (used by login page to show SSO button)."""
    settings = get_settings()
    return {
        "enabled": settings.OIDC_ENABLED and bool(settings.OIDC_CLIENT_ID),
    }


@router.get("/oidc/login")
async def oidc_login():
    """Redirect the browser to the OIDC provider's authorization endpoint."""
    settings = get_settings()
    if not settings.OIDC_ENABLED or not settings.OIDC_DISCOVERY_URL:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="OIDC not configured")

    try:
        oidc = await _get_oidc_config(settings.OIDC_DISCOVERY_URL)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OIDC discovery failed: {exc}")

    nonce = secrets.token_urlsafe(32)
    state = _sign_state(nonce, settings.SECRET_KEY)

    params = {
        "response_type": "code",
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "scope": settings.OIDC_SCOPES,
        "state": state,
        "nonce": nonce,
    }
    auth_url = oidc["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(auth_url)


@router.get("/oidc/callback")
async def oidc_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle the OIDC authorization code callback.

    Exchanges the code for tokens, fetches user info, and either signs in
    an existing account or provisions a new one linked to this OIDC subject.
    On success, redirects to the frontend root with ?token=<jwt>.
    """
    settings = get_settings()
    if not settings.OIDC_ENABLED or not settings.OIDC_DISCOVERY_URL:
        raise HTTPException(status_code=501, detail="OIDC not configured")

    if not _verify_state(state, settings.SECRET_KEY):
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF")

    try:
        oidc = await _get_oidc_config(settings.OIDC_DISCOVERY_URL)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OIDC discovery failed: {exc}")

    # Exchange authorization code for tokens
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            oidc["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.OIDC_REDIRECT_URI,
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Token exchange failed")
        token_data = token_resp.json()

        # Fetch user info
        userinfo_resp = await client.get(
            oidc["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Userinfo fetch failed")
        userinfo = userinfo_resp.json()

    sub: str = userinfo.get("sub", "")
    email: str = userinfo.get("email", "")
    name: str = userinfo.get("name", "") or userinfo.get("preferred_username", "") or email.split("@")[0]

    if not sub:
        raise HTTPException(status_code=502, detail="OIDC provider returned no subject claim")

    # Look up by OIDC subject first, then fall back to email
    result = await db.execute(select(User).where(User.oidc_subject == sub))
    user = result.scalar_one_or_none()

    if not user and email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            # Link existing account to this OIDC subject
            user.oidc_subject = sub
            user.oidc_provider = settings.OIDC_DISCOVERY_URL

    if not user:
        # Provision new user — first OIDC user is admin if no users exist yet
        count_result = await db.execute(select(User))
        is_first = count_result.scalar_one_or_none() is None

        # Derive a unique username from the name/email
        base_username = name.lower().replace(" ", "_")[:30] or "user"
        username = base_username
        suffix = 1
        while True:
            exists = await db.scalar(select(User).where(User.username == username))
            if not exists:
                break
            username = f"{base_username}_{suffix}"
            suffix += 1

        user = User(
            username=username,
            email=email or f"{sub}@oidc.local",
            hashed_password="",  # OIDC accounts have no local password
            oidc_subject=sub,
            oidc_provider=settings.OIDC_DISCOVERY_URL,
            is_admin=is_first,
            is_active=True,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    access_token = create_access_token(user.id, is_admin=user.is_admin)

    # Redirect to frontend — it reads ?token= and calls setAuthToken()
    frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:5173"
    return RedirectResponse(f"{frontend_url}/auth/oidc?token={urllib.parse.quote(access_token)}")
