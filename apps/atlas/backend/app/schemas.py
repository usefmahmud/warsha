"""Pydantic request/response schemas — mirrors PRD §7 wire format."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Annotated, Generic, TypeVar

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    field_validator,
)

from .models import (
    ProjectRole,
    TicketPriority,
    TicketStatus,
    TicketType,
    UserRole,
)

T = TypeVar("T")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


UTCDT = Annotated[datetime, PlainSerializer(_iso, return_type=str)]
UTCDTOpt = Annotated[datetime | None, PlainSerializer(_iso, return_type=str | None)]

# Internal domains (@atlas.local) are legit self-hosted; EmailStr rejects them.
EMAIL_PATTERN = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)+$"
EmailAddress = Annotated[
    str, StringConstraints(pattern=EMAIL_PATTERN, max_length=255, strip_whitespace=True)
]
HEX_COLOR = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
USERNAME = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{3,32}$")]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# --- auth / users ----------------------------------------------------------
class UserBrief(ORMModel):
    id: str
    username: str
    name: str
    avatar_url: str | None = None
    color: str


class UserOut(UserBrief):
    email: str
    role: UserRole
    is_active: bool
    created_at: UTCDT
    last_login_at: UTCDTOpt = None


class UserCreate(BaseModel):
    email: EmailAddress
    name: str = Field(min_length=1, max_length=120)
    username: USERNAME
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.member
    avatar_url: str | None = Field(default=None, max_length=500)
    color: HEX_COLOR = "#2563EB"

    @field_validator("username")
    @classmethod
    def _lower_username(cls, v: str) -> str:
        return v.lower()


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None
    avatar_url: str | None = Field(default=None, max_length=500)
    color: HEX_COLOR | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=500)
    color: HEX_COLOR | None = None


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=128)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class RegisterRequest(UserCreate):
    pass


# --- projects --------------------------------------------------------------
PROJECT_KEY_PATTERN = r"^[A-Z][A-Z0-9]{1,5}$"


class ProjectCreate(BaseModel):
    key: str = Field(pattern=PROJECT_KEY_PATTERN)
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    color: HEX_COLOR = "#2563EB"
    member_ids: list[str] = []


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    color: HEX_COLOR | None = None


class MemberAdd(BaseModel):
    user_id: str
    role_in_project: ProjectRole = ProjectRole.member


class MemberOut(BaseModel):
    user: UserBrief
    role_in_project: ProjectRole
    added_at: UTCDT


class ProjectOut(BaseModel):
    id: str
    key: str
    name: str
    description: str
    color: str
    ticket_count: int = 0
    open_count: int = 0
    members_count: int = 0
    archived_at: UTCDTOpt = None
    created_at: UTCDT
    updated_at: UTCDT
    my_role: ProjectRole | None = None


class ProjectDetail(ProjectOut):
    members: list[MemberOut] = []
    labels: list[LabelOut] = []


# --- labels / attachments --------------------------------------------------
class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: HEX_COLOR = "#94A3B8"

    @field_validator("name")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class LabelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: HEX_COLOR | None = None


class LabelOut(ORMModel):
    id: str
    name: str
    color: str
    project_id: str
    ticket_count: int = 0


class LabelLink(BaseModel):
    label_id: str


class AttachmentCreate(BaseModel):
    kind: str = "link"
    url: str = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=200)


class AttachmentOut(ORMModel):
    id: str
    kind: str
    url: str
    title: str | None = None
    created_at: UTCDT


# --- tickets ---------------------------------------------------------------
class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description_md: str = Field(default="", max_length=50000)
    type: TicketType = TicketType.task
    priority: TicketPriority = TicketPriority.normal
    status: TicketStatus = TicketStatus.backlog
    assignee_id: str | None = None
    assignee_username: str | None = None
    labels: list[str] = []
    due_date: date | None = None
    estimate_points: int | None = Field(default=None, ge=0, le=100)
    parent_id: str | None = None
    board_position: float | None = None
    client_ref: str | None = Field(default=None, max_length=120)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        return v

    @field_validator("assignee_username")
    @classmethod
    def _lower_user(cls, v: str | None) -> str | None:
        return v.lower() if v else v


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description_md: str | None = Field(default=None, max_length=50000)
    type: TicketType | None = None
    priority: TicketPriority | None = None
    assignee_id: str | None = None
    assignee_username: str | None = Field(
        default=None, validation_alias=AliasChoices("assignee_username", "assignee")
    )
    due_date: date | None = None
    estimate_points: int | None = Field(default=None, ge=0, le=100)
    parent_id: str | None = None
    labels: list[str] | None = None
    board_position: float | None = None
    version: int | None = None


class TransitionRequest(BaseModel):
    to: TicketStatus
    blocked_reason: str | None = Field(default=None, min_length=3, max_length=500)
    position: float | None = None
    version: int | None = None


class TicketOut(BaseModel):
    id: str
    key: str
    number: int
    project_id: str
    project_key: str
    title: str
    description_md: str
    type: TicketType
    priority: TicketPriority
    status: TicketStatus
    blocked_reason: str | None = None
    assignee: UserBrief | None = None
    reporter: UserBrief | None = None
    labels: list[LabelOut] = []
    due_date: date | None = None
    estimate_points: int | None = None
    parent_id: str | None = None
    parent_key: str | None = None
    children_count: int = 0
    comment_count: int = 0
    attachments: list[AttachmentOut] = []
    board_position: float
    version: int
    created_at: UTCDT
    updated_at: UTCDT
    closed_at: UTCDTOpt = None
    is_overdue: bool = False


class TicketLite(BaseModel):
    id: str
    key: str
    number: int
    project_key: str
    title: str
    type: TicketType
    priority: TicketPriority
    status: TicketStatus
    assignee: UserBrief | None = None
    labels: list[LabelOut] = []
    due_date: date | None = None
    board_position: float
    children_count: int = 0
    comment_count: int = 0
    is_overdue: bool = False


class TransitionResult(BaseModel):
    ticket: TicketOut
    warnings: list[str] = []


# --- comments / mentions ---------------------------------------------------
COMMENT_MAX = 10000


class CommentCreate(BaseModel):
    body_md: str = Field(min_length=1, max_length=COMMENT_MAX)


class CommentUpdate(BaseModel):
    body_md: str = Field(min_length=1, max_length=COMMENT_MAX)


class CommentOut(BaseModel):
    id: str
    ticket_id: str
    ticket_key: str
    body_md: str
    author: UserBrief
    mentions: list[UserBrief] = []
    edited_at: UTCDTOpt = None
    created_at: UTCDT


# --- activity / notifications ---------------------------------------------
class ActivityOut(BaseModel):
    id: str
    action: str
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    actor: UserBrief | None = None
    ticket_id: str | None = None
    ticket_key: str | None = None
    request_id: str | None = None
    created_at: UTCDT


class NotificationOut(BaseModel):
    id: str
    type: str
    payload: dict = {}
    actor: UserBrief | None = None
    ticket_id: str | None = None
    ticket_key: str | None = None
    read_at: UTCDTOpt = None
    created_at: UTCDT


class NotificationPage(Page[NotificationOut]):
    unread_count: int = 0


class UnreadCount(BaseModel):
    count: int


# --- api keys --------------------------------------------------------------
class ApiKeyCreate(BaseModel):
    name: str = Field(default="agent", max_length=80)


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    user_id: str
    revoked_at: UTCDTOpt = None
    last_used_at: UTCDTOpt = None
    created_at: UTCDT


class ApiKeyCreated(ApiKeyOut):
    key: str


# --- views -----------------------------------------------------------------
class BoardColumn(BaseModel):
    status: TicketStatus
    title: str
    count: int
    items: list[TicketLite]
    has_more: bool = False


class BoardOut(BaseModel):
    project: ProjectOut
    columns: list[BoardColumn]
    generated_at: UTCDT


class MyWorkMentions(BaseModel):
    notification_id: str
    ticket: TicketLite
    comment_id: str | None = None
    snippet: str
    unread: bool = True
    created_at: UTCDT


class MyWorkOut(BaseModel):
    assigned: list[TicketLite] = []
    due_soon: list[TicketLite] = []
    overdue: list[TicketLite] = []
    closed_recent: list[TicketLite] = []
    mentions: list[MyWorkMentions] = []


class SearchHit(BaseModel):
    ticket: TicketLite
    snippet: str
    rank: float = 0.0


class SearchOut(BaseModel):
    items: list[SearchHit]
    total: int


# --- meta ------------------------------------------------------------------
class OptionOut(BaseModel):
    value: str
    label: str


class MetaOut(BaseModel):
    statuses: list[OptionOut]
    types: list[OptionOut]
    priorities: list[OptionOut]
    version: str


class HealthOut(BaseModel):
    status: str
    db: str
    version: str
    uptime_s: float


# --- agent -----------------------------------------------------------------
class AgentMeOut(BaseModel):
    user: UserOut
    projects: list[dict]


class AgentTicketCreate(TicketCreate):
    project_key: str = Field(pattern=PROJECT_KEY_PATTERN)
    project_id: str | None = None


# --- webhooks --------------------------------------------------------------
WEBHOOK_EVENTS = (
    "ticket.created",
    "ticket.updated",
    "ticket.status_changed",
    "ticket.assigned",
    "ticket.done",
    "comment.created",
)


class WebhookCreate(BaseModel):
    url: str = Field(min_length=8, max_length=1000)
    events: list[str] = Field(default_factory=lambda: ["ticket.created"])
    project_id: str | None = None
    active: bool = True

    @field_validator("events")
    @classmethod
    def _known_events(cls, v: list[str]) -> list[str]:
        unknown = [e for e in v if e not in WEBHOOK_EVENTS]
        if unknown:
            raise ValueError(f"unknown events: {', '.join(unknown)}")
        return v


class WebhookUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=8, max_length=1000)
    events: list[str] | None = None
    active: bool | None = None


class WebhookOut(BaseModel):
    id: str
    url: str
    events: list[str]
    project_id: str | None = None
    active: bool
    failures: int
    last_status: int | None = None
    last_sent_at: UTCDTOpt = None
    created_at: UTCDT


class WebhookCreated(WebhookOut):
    secret: str


class WebhookTestResult(BaseModel):
    status_code: int | None
    duration_ms: int
    ok: bool
    error: str | None = None


_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


ProjectDetail.model_rebuild()
