from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
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

@router.post("/onboard")
def onboard_user(data: dict, payload=Depends(verify_token), db: Session = Depends(get_db)):
    print("BODY DATA:", data)
    print("JWT PAYLOAD:", payload)
    clerk_id = payload.get("sub")

    first_name = None
    last_name = None
    avatar_url = None

    try:
        clerk_user = clerk.users.get(user_id=clerk_id)
        first_name = clerk_user.first_name
        last_name = clerk_user.last_name
        avatar_url = clerk_user.image_url if clerk_user.has_image else None
    except Exception:
        pass

    user = models.User(
        clerk_id=clerk_id,
        first_name=first_name,
        last_name=last_name,
        full_name=f"{first_name or ''} {last_name or ''}".strip() or None,
        avatar_url=avatar_url,
        doctor_id=data["doctor_id"],
        city=data["city"],
        state=data["state"],
        experience=data["experience"],
        specialization=data["specialization"],
        hospital=data["hospital"],
    )

    db.add(user)
    db.commit()

    return {"message": "User created"}
