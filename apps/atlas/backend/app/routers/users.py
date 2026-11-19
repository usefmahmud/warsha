"""Users, deactivation and per-user API keys (PRD §7.3)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_

from ..deps import AdminUser, CurrentUser, DbDep, Pagination
from ..errors import conflict, forbidden, not_found
from ..models import ApiKey, ProjectMember, User, UserRole, utcnow
from ..schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    Page,
    UserCreate,
    UserOut,
    UserUpdate,
)
from ..security import generate_api_key, hash_password
from ..services.serializers import user_out

router = APIRouter(tags=["users"])


def _user_or_404(db, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("USER_NOT_FOUND", "user not found")
    return user


@router.get("/users", response_model=Page[UserOut])
def list_users(
    db: DbDep,
    admin: AdminUser,
    page: Pagination,
    q: str | None = Query(default=None, max_length=120),
    active: bool | None = None,
) -> Page[UserOut]:
    limit, offset = page
    query = db.query(User)
    if active is not None:
        query = query.filter(User.is_active.is_(active))
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(User.username).like(like),
                func.lower(User.email).like(like),
                func.lower(User.name).like(like),
            )
        )
    total = query.count()
    rows = query.order_by(User.created_at).offset(offset).limit(limit).all()
    return Page[UserOut](
        items=[user_out(u) for u in rows], total=total, limit=limit, offset=offset
    )


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: DbDep, _: CurrentUser) -> UserOut:
    return user_out(_user_or_404(db, user_id))


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbDep, admin: AdminUser) -> UserOut:
    if payload.role == UserRole.owner and admin.role != UserRole.owner:
        raise forbidden("FORBIDDEN", "only the owner can create an owner")
    if db.query(User).filter(func.lower(User.email) == payload.email.lower()).first():
        raise conflict("EMAIL_EXISTS", "email already registered")
    if db.query(User).filter(func.lower(User.username) == payload.username).first():
        raise conflict("USERNAME_EXISTS", "username already taken")
    user = User(
        email=payload.email.lower(),
        username=payload.username,
        name=payload.name,
        password_hash=hash_password(payload.password),
        avatar_url=payload.avatar_url,
        color=payload.color,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdate, db: DbDep, admin: AdminUser) -> UserOut:
    target = _user_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    if target.role == UserRole.owner and admin.role != UserRole.owner:
        raise forbidden("FORBIDDEN", "admins cannot modify the owner account")
    if data.get("role") == UserRole.owner and admin.role != UserRole.owner:
        raise forbidden("FORBIDDEN", "only the owner can promote to owner")
    if target.role == UserRole.owner and data.get("role") not in (None, UserRole.owner):
        owners = db.query(func.count(User.id)).filter(User.role == UserRole.owner).scalar() or 0
        if owners <= 1:
            raise forbidden("LAST_OWNER", "cannot demote the last owner")
    if data.pop("is_active", None) is False and target.is_active:
        _deactivate(db, target, admin)
        db.flush()
    password = data.pop("password", None)
    if password:
        target.password_hash = hash_password(password)
    for field, value in data.items():
        if value is not None:
            setattr(target, field, value)
    db.add(target)
    db.commit()
    db.refresh(target)
    return user_out(target)


def _deactivate(db, target: User, admin: User) -> None:
    if target.id == admin.id:
        raise forbidden("FORBIDDEN", "you cannot deactivate yourself")
    if target.role == UserRole.owner:
        owners = db.query(func.count(User.id)).filter(User.role == UserRole.owner).scalar() or 0
        if owners <= 1:
            raise forbidden("LAST_OWNER", "cannot deactivate the last owner")
    target.is_active = False
    # kill live agent keys too
    db.query(ApiKey).filter(ApiKey.user_id == target.id, ApiKey.revoked_at.is_(None)).update(
        {ApiKey.revoked_at: utcnow()}, synchronize_session=False
    )
    db.add(target)


@router.post("/users/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(user_id: str, db: DbDep, admin: AdminUser) -> None:
    target = _user_or_404(db, user_id)
    _deactivate(db, target, admin)
    db.commit()


# --- API keys --------------------------------------------------------------
def _key_out(row: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=row.id,
        name=row.name,
        prefix=row.prefix,
        user_id=row.user_id,
        revoked_at=row.revoked_at,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
    )


@router.get("/users/{user_id}/keys", response_model=list[ApiKeyOut])
def list_keys(user_id: str, db: DbDep, current: CurrentUser) -> list[ApiKeyOut]:
    if user_id != current.id and current.role not in (UserRole.owner, UserRole.admin):
        raise forbidden("FORBIDDEN", "you can only see your own keys")
    _user_or_404(db, user_id)
    rows = db.query(ApiKey).filter(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    return [_key_out(r) for r in rows]


@router.post(
    "/users/{user_id}/keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_key(
    user_id: str, payload: ApiKeyCreate, db: DbDep, current: CurrentUser
) -> ApiKeyCreated:
    if user_id != current.id and current.role != UserRole.owner:
        raise forbidden("FORBIDDEN", "only the owner can mint keys for others")
    target = _user_or_404(db, user_id)
    if not target.is_active:
        raise forbidden("ACCOUNT_DISABLED", "cannot mint a key for a disabled account")
    plaintext, prefix, key_hash = generate_api_key()
    row = ApiKey(user_id=target.id, name=payload.name, prefix=prefix, key_hash=key_hash)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiKeyCreated(**_key_out(row).model_dump(), key=plaintext)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(key_id: str, db: DbDep, current: CurrentUser) -> None:
    row = db.get(ApiKey, key_id)
    if row is None:
        raise not_found("NOT_FOUND", "api key not found")
    if row.user_id != current.id and current.role != UserRole.owner:
        raise forbidden("FORBIDDEN", "not your key")
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        db.add(row)
        db.commit()


@router.get("/me/projects", response_model=list[dict])
def my_projects(db: DbDep, user: CurrentUser) -> list[dict]:
    query = db.query(ProjectMember).filter(ProjectMember.user_id == user.id)
    return [
        {"key": m.project.key, "name": m.project.name, "role_in_project": m.role_in_project.value}
        for m in query.all()
        if m.project is not None
    ]
