"""Auth endpoints (PRD §7.2)."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from sqlalchemy import func

from ..config import settings
from ..deps import CurrentUser, DbDep
from ..errors import APIError, forbidden
from ..models import User, UserRole, utcnow
from ..ratelimit import SlidingWindow, too_many
from ..schemas import (
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    RegisterRequest,
    TokenOut,
    UserOut,
)
from ..security import create_access_token, hash_password, verify_password
from ..services.serializers import user_out

router = APIRouter(prefix="/auth", tags=["auth"])

login_limiter = SlidingWindow(settings.login_attempts_per_minute, 60.0)


def _token_response(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role.value),
        expires_in=settings.access_token_expire_minutes * 60,
        user=user_out(user),
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbDep) -> TokenOut:
    """Bootstrap only: creates the very first account (owner). Enabled by ATLAS_ALLOW_REGISTRATION."""
    existing = db.query(func.count(User.id)).scalar() or 0
    if existing:
        raise forbidden("REGISTRATION_CLOSED", "registration is closed — ask an admin to add you")
    if not settings.allow_registration:  # pragma: no cover - production default
        raise forbidden("REGISTRATION_CLOSED", "registration is disabled")
    user = User(
        email=payload.email.lower(),
        username=payload.username,
        name=payload.name,
        password_hash=hash_password(payload.password),
        avatar_url=payload.avatar_url,
        color=payload.color,
        role=UserRole.owner,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: DbDep) -> TokenOut:
    email_key = payload.email.lower()
    if login_limiter.count(email_key) >= settings.login_attempts_per_minute:
        raise too_many(login_limiter.retry_after(email_key))
    login_limiter.hit(email_key)

    user = db.query(User).filter(func.lower(User.email) == email_key).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        # AC-01.2: one message for both cases, no account enumeration
        raise APIError(401, "INVALID_CREDENTIALS", "invalid email or password")
    if not user.is_active:
        raise APIError(403, "ACCOUNT_DISABLED", "account is disabled")
    login_limiter.reset(email_key)
    user.last_login_at = utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(payload: ProfileUpdate, user: CurrentUser, db: DbDep) -> UserOut:
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: PasswordChange, user: CurrentUser, db: DbDep) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise APIError(400, "INVALID_PASSWORD", "current password is wrong")
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: Request, user: CurrentUser) -> None:
    """v1: stateless JWT — the client discards the token (kept for API symmetry)."""
    return
