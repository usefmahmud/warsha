"""CLI: bootstrap accounts, mint API keys, seed a demo project.

    python -m app.cli init-db
    python -m app.cli seed-agents --owner-password '<secret>'
    python -m app.cli create-api-key --username omar --name laptop
    python -m app.cli seed-demo
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys

from sqlalchemy import func

from .database import SessionLocal, init_db
from .models import (
    ApiKey,
    Label,
    Project,
    ProjectMember,
    ProjectRole,
    Ticket,
    User,
    UserRole,
)
from .security import generate_api_key, hash_password

AGENTS = ["hakim", "maryam", "omar", "yassin", "layla", "salim"]


def _db():
    init_db()
    return SessionLocal()


def cmd_init_db(_args) -> None:
    init_db()
    print("schema ok")


def cmd_create_user(args) -> None:
    with _db() as db:
        if db.query(User).filter(func.lower(User.email) == args.email.lower()).first():
            print(f"user {args.email} already exists", file=sys.stderr)
            raise SystemExit(1)
        password = args.password or secrets.token_urlsafe(12)
        user = User(
            email=args.email.lower(),
            username=args.username.lower(),
            name=args.name or args.username,
            password_hash=hash_password(password),
            role=UserRole(args.role),
            color=args.color,
        )
        db.add(user)
        db.commit()
        print(f"created {user.username} <{user.email}> role={user.role.value}")
        if not args.password:
            print(f"generated password: {password}")


def cmd_seed_agents(args) -> None:
    with _db() as db:
        created: list[tuple[str, str, str]] = []
        if db.query(func.count(User.id)).scalar() == 0:
            password = args.owner_password or secrets.token_urlsafe(12)
            owner = User(
                email=args.owner_email.lower(),
                username=args.owner_username.lower(),
                name=args.owner_name,
                password_hash=hash_password(password),
                role=UserRole.owner,
            )
            db.add(owner)
            created.append((owner.username, owner.email, password))
        for name in AGENTS:
            email = f"{name}@atlas.local"
            if db.query(User).filter(func.lower(User.email) == email).first():
                continue
            password = secrets.token_urlsafe(12)
            db.add(
                User(
                    email=email,
                    username=name,
                    name=name.capitalize(),
                    password_hash=hash_password(password),
                    role=UserRole.member,
                )
            )
            created.append((name, email, password))
        db.commit()

    if not created:
        print("nothing to do — all accounts exist")
        return
    print("username,email,one_time_password")
    for username, email, password in created:
        print(f"{username},{email},{password}")
    print("\nStore these now; they are not shown again. Change them on first login.")


def cmd_create_api_key(args) -> None:
    with _db() as db:
        user = db.query(User).filter(func.lower(User.username) == args.username.lower()).first()
        if user is None:
            print(f"no such user: {args.username}", file=sys.stderr)
            raise SystemExit(1)
        plaintext, prefix, key_hash = generate_api_key()
        db.add(ApiKey(user_id=user.id, name=args.name, prefix=prefix, key_hash=key_hash))
        db.commit()
        print(f"API key for {user.username} ({args.name}): {plaintext}")
        print("Store it now; it cannot be retrieved later.")


def cmd_seed_demo(_args) -> None:
    with _db() as db:
        owner = db.query(User).filter(User.role == UserRole.owner).order_by(User.created_at).first()
        if owner is None:
            print("create a user first (seed-agents)", file=sys.stderr)
            raise SystemExit(1)
        project = db.query(Project).filter(Project.key == "ATL").first()
        if project is None:
            project = Project(
                key="ATL",
                name="Atlas",
                description="منصة إدارة المشاريع والتيكتس",
                created_by=owner.id,
            )
            db.add(project)
            db.flush()
            db.add(
                ProjectMember(
                    project_id=project.id, user_id=owner.id, role_in_project=ProjectRole.lead
                )
            )
            for name, color in (("backend", "#2563EB"), ("frontend", "#8B5CF6"), ("ops", "#F59E0B")):
                db.add(Label(project_id=project.id, name=name, color=color))
            db.flush()
        existing = db.query(func.count(Ticket.id)).filter(Ticket.project_id == project.id).scalar()
        if not existing:
            for index, title in enumerate(
                ["Backend API", "Board UI (RTL)", "Docker deploy", "Agent onboarding"], start=1
            ):
                db.add(
                    Ticket(
                        project_id=project.id,
                        number=index,
                        key=f"{project.key}-{index}",
                        title=title,
                        description_md=f"Demo ticket — {title}",
                        reporter_id=owner.id,
                        board_position=index * 1024.0,
                    )
                )
            project.ticket_seq = 4
        db.commit()
        print(f"demo project {project.key} ready")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="atlas-cli", description="Atlas admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db").set_defaults(func=cmd_init_db)

    p_user = sub.add_parser("create-user")
    p_user.add_argument("--email", required=True)
    p_user.add_argument("--username", required=True)
    p_user.add_argument("--password", default="")
    p_user.add_argument("--name", default="")
    p_user.add_argument("--role", default="member", choices=[r.value for r in UserRole])
    p_user.add_argument("--color", default="#2563EB")
    p_user.set_defaults(func=cmd_create_user)

    p_seed = sub.add_parser("seed-agents")
    p_seed.add_argument(
        "--owner-email", default=os.getenv("ATLAS_OWNER_EMAIL", "owner@atlas.local")
    )
    p_seed.add_argument("--owner-username", default="youssef")
    p_seed.add_argument("--owner-name", default="يوسف")
    p_seed.add_argument("--owner-password", default="")
    p_seed.set_defaults(func=cmd_seed_agents)

    p_key = sub.add_parser("create-api-key")
    p_key.add_argument("--username", required=True)
    p_key.add_argument("--name", default="agent")
    p_key.set_defaults(func=cmd_create_api_key)

    sub.add_parser("seed-demo").set_defaults(func=cmd_seed_demo)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
