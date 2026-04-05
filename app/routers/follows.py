from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models
from app.auth import verify_token
from app.identity import get_user_display_name
from app.routers.users import get_db
from app.schemas import SuggestedDoctor

router = APIRouter(prefix="/follows", tags=["Follows"])

@router.post("/{target_clerk_id}")
def toggle_follow(
    target_clerk_id: str,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    my_clerk_id = payload.get("sub")

    if my_clerk_id == target_clerk_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    existing = (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_clerk_id == my_clerk_id,
            models.Follow.following_clerk_id == target_clerk_id,
        )
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"following": False}

    new_follow = models.Follow(
        follower_clerk_id=my_clerk_id,
        following_clerk_id=target_clerk_id,
    )

    db.add(new_follow)
    db.commit()

    return {"following": True}

@router.get("/{clerk_id}/followers-count")
def get_followers_count(clerk_id: str, db: Session = Depends(get_db)):
    count = (
        db.query(models.Follow)
        .filter(models.Follow.following_clerk_id == clerk_id)
        .count()
    )

    return {"followers": count}

@router.get("/{clerk_id}/following-count")
def get_following_count(clerk_id: str, db: Session = Depends(get_db)):
    count = (
        db.query(models.Follow)
        .filter(models.Follow.follower_clerk_id == clerk_id)
        .count()
    )

    return {"following": count}

@router.get("/{target_clerk_id}/is-following")
def is_following(
    target_clerk_id: str,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    my_clerk_id = payload.get("sub")

    existing = (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_clerk_id == my_clerk_id,
            models.Follow.following_clerk_id == target_clerk_id,
        )
        .first()
    )

    return {"following": existing is not None}

@router.get("/suggestions", response_model=list[SuggestedDoctor])
def get_suggestions(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    my_id = payload.get("sub")

    me = db.query(models.User).filter(
        models.User.clerk_id == my_id
    ).first()

    if not me:
        return []

    # Get already followed
    followed_ids = {
        f.following_clerk_id
        for f in db.query(models.Follow)
        .filter(models.Follow.follower_clerk_id == my_id)
        .all()
    }

    followed_ids.add(my_id)

    # Get same specialization first
    candidates = db.query(models.User).filter(
        models.User.specialization == me.specialization,
        ~models.User.clerk_id.in_(followed_ids)
    ).limit(3).all()

    # Fallback same city
    if len(candidates) < 3:
        more = db.query(models.User).filter(
            models.User.city == me.city,
            ~models.User.clerk_id.in_(followed_ids)
        ).limit(3 - len(candidates)).all()

        candidates.extend(more)

    result = []

    for user in candidates:
        result.append({
            "clerk_id": user.clerk_id,
            "name": get_user_display_name(user),
            "avatar": user.avatar_url,
            "specialization": user.specialization,
            "hospital": user.hospital,
            "city": user.city,
            "experience": user.experience,
            "is_following": False,  # since we filtered already
        })

    return result
