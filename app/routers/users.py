from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models, schemas
from app.auth import verify_token
from app.clerk_client import clerk

router = APIRouter(prefix="/users", tags=["Users"])

INVITE_LINK_EXPIRY_DAYS = 14
DEFAULT_INVITE_SIGNUP_URL = "http://localhost:3000/sign-up"
INVALID_INVITE_MESSAGE = "This invite link is invalid, expired, or has already been used."

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/test")
def test_endpoint():
    return {"message": "Test endpoint working"}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_optional_string(value):
    if value is None:
        return None

    normalized = str(value).strip()
    return normalized or None


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_invite_url(token: str) -> str:
    base_url = os.getenv("INVITE_SIGNUP_URL", DEFAULT_INVITE_SIGNUP_URL).strip()
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'invite': token})}"


def verify_admin_secret(x_admin_secret: Optional[str]):
    configured_secret = os.getenv("ADMIN_INVITE_SECRET")

    if not configured_secret:
        raise HTTPException(status_code=500, detail="Invite link creation is not configured")

    if x_admin_secret != configured_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


def get_clerk_user_primary_email(clerk_user) -> Optional[str]:
    primary_email_id = getattr(clerk_user, "primary_email_address_id", None)
    email_addresses = getattr(clerk_user, "email_addresses", []) or []

    for email_address in email_addresses:
        email_id = getattr(email_address, "id", None)
        email_value = getattr(email_address, "email_address", None)

        if primary_email_id and email_id == primary_email_id:
            return email_value

    if email_addresses:
        return getattr(email_addresses[0], "email_address", None)

    return None


def get_active_invite(db: Session, email: str):
    normalized_email = normalize_email(email)
    return (
        db.query(models.Invite)
        .filter(
            func.lower(models.Invite.email) == normalized_email,
            or_(models.Invite.invite_type == "email", models.Invite.invite_type.is_(None)),
            models.Invite.is_active == True,
            models.Invite.used_by_clerk_id.is_(None),
        )
        .first()
    )


def get_active_link_invite(db: Session, token: str):
    now = datetime.now(timezone.utc)
    token_hash = hash_invite_token(token)

    return (
        db.query(models.Invite)
        .filter(models.Invite.token_hash == token_hash)
        .filter(models.Invite.invite_type == "link")
        .filter(models.Invite.is_active == True)
        .filter(models.Invite.used_by_clerk_id.is_(None))
        .filter(
            or_(
                models.Invite.expires_at.is_(None),
                models.Invite.expires_at > now,
            )
        )
        .first()
    )


@router.post("/invite-check")
def invite_check(data: schemas.InviteCheckRequest, db: Session = Depends(get_db)):
    invite = get_active_invite(db, data.email)

    if not invite:
        return {
            "allowed": False,
            "message": "This platform is invite-only. This email is not on the approved invite list.",
        }

    return {"allowed": True}


@router.post("/invites/link", response_model=schemas.InviteLinkCreateResponse)
def create_invite_link(
    data: schemas.InviteLinkCreateRequest,
    db: Session = Depends(get_db),
    x_admin_secret: Optional[str] = Header(None, alias="X-Admin-Secret"),
):
    verify_admin_secret(x_admin_secret)

    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_LINK_EXPIRY_DAYS)

    invite = models.Invite(
        invite_type="link",
        token_hash=hash_invite_token(raw_token),
        is_active=True,
        expires_at=expires_at,
        note=normalize_optional_string(data.note),
    )

    db.add(invite)
    db.commit()

    return schemas.InviteLinkCreateResponse(
        invite_url=build_invite_url(raw_token),
        expires_at=expires_at,
    )


@router.post("/invites/validate", response_model=schemas.InviteTokenValidateResponse)
def validate_invite_link(
    data: schemas.InviteTokenValidateRequest,
    db: Session = Depends(get_db),
):
    invite = get_active_link_invite(db, data.invite_token)

    if not invite:
        return schemas.InviteTokenValidateResponse(
            valid=False,
            message=INVALID_INVITE_MESSAGE,
        )

    return schemas.InviteTokenValidateResponse(valid=True)


@router.post("/onboard")
def onboard_user(
    data: schemas.OnboardUserRequest,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    print("BODY DATA:", data)
    print("JWT PAYLOAD:", payload)
    clerk_id = payload.get("sub")

    first_name = None
    last_name = None
    avatar_url = None
    primary_email = None

    try:
        clerk_user = clerk.users.get(user_id=clerk_id)
        first_name = clerk_user.first_name
        last_name = clerk_user.last_name
        avatar_url = clerk_user.image_url if clerk_user.has_image else None
        primary_email = get_clerk_user_primary_email(clerk_user)
    except Exception:
        pass

    if not primary_email:
        raise HTTPException(status_code=400, detail="Unable to resolve primary email for this account")

    existing_user = (
        db.query(models.User)
        .filter(models.User.clerk_id == clerk_id)
        .first()
    )

    if existing_user:
        return {"message": "User already onboarded"}

    invite = None

    if data.invite_token:
        invite = get_active_link_invite(db, data.invite_token)
        if not invite:
            raise HTTPException(
                status_code=403,
                detail=INVALID_INVITE_MESSAGE,
            )
    else:
        invite = get_active_invite(db, primary_email)

        if not invite:
            raise HTTPException(
                status_code=403,
                detail="This platform is invite-only. This email is not on the approved invite list.",
            )

    user = models.User(
        clerk_id=clerk_id,
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name or ''} {last_name or ''}".strip() or None,
        avatar_url=avatar_url,
        doctor_id=normalize_optional_string(data.doctor_id),
        city=normalize_optional_string(data.city),
        state=normalize_optional_string(data.state),
        experience=data.experience,
        specialization=data.specialization,
        hospital=normalize_optional_string(data.hospital),
    )

    db.add(user)
    invite.used_by_clerk_id = clerk_id
    invite.used_by_email = primary_email
    invite.used_at = datetime.now(timezone.utc)
    invite.is_active = False
    db.commit()

    return {"message": "User created"}
