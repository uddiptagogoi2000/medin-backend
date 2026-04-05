from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models, schemas
from app.auth import verify_token
from app.clerk_client import clerk

router = APIRouter(prefix="/users", tags=["Users"])

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
            models.Invite.is_active == True,
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

@router.post("/onboard")
def onboard_user(data: dict, payload=Depends(verify_token), db: Session = Depends(get_db)):
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

    invite = get_active_invite(db, primary_email)

    if not invite:
        raise HTTPException(
            status_code=403,
            detail="This platform is invite-only. This email is not on the approved invite list.",
        )

    existing_user = (
        db.query(models.User)
        .filter(models.User.clerk_id == clerk_id)
        .first()
    )

    if existing_user:
        return {"message": "User already onboarded"}

    user = models.User(
        clerk_id=clerk_id,
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name or ''} {last_name or ''}".strip() or None,
        avatar_url=avatar_url,
        doctor_id=normalize_optional_string(data.get("doctor_id")),
        city=normalize_optional_string(data.get("city")),
        state=normalize_optional_string(data.get("state")),
        experience=data["experience"],
        specialization=data["specialization"],
        hospital=normalize_optional_string(data.get("hospital")),
    )

    db.add(user)
    invite.used_by_clerk_id = clerk_id
    db.commit()

    return {"message": "User created"}
