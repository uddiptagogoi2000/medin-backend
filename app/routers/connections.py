from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app import models
from app.auth import verify_token
from app.identity import get_user_display_name
from app.routers.users import get_db

router = APIRouter(prefix="/connections", tags=["Connections"])


def enrich_users(users: list[models.User], following_ids: set[str]):
    return [
        {
            "clerk_id": user.clerk_id,
            "id": user.id,
            "city": user.city,
            "state": user.state,
            "hospital": user.hospital,
            "specialization": user.specialization,
            "experience": user.experience,
            "name": get_user_display_name(user),
            "avatar": user.avatar_url,
            "is_following": user.clerk_id in following_ids,
        }
        for user in users
    ]

@router.get("/following")
def get_following(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    following = (
        db.query(models.Follow)
        .filter(models.Follow.follower_clerk_id == clerk_id)
        .all()
    )

    following_ids = [f.following_clerk_id for f in following]

    users = (
        db.query(models.User)
        .filter(models.User.clerk_id.in_(following_ids))
        .all()
    )

    return enrich_users(users, set(following_ids))


@router.get("/followers")
def get_followers(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")
    following_ids = set(get_following_ids(clerk_id, db))

    followers = (
        db.query(models.Follow)
        .filter(models.Follow.following_clerk_id == clerk_id)
        .all()
    )

    follower_ids = [f.follower_clerk_id for f in followers]

    users = (
        db.query(models.User)
        .filter(models.User.clerk_id.in_(follower_ids))
        .all()
    )

    return enrich_users(users, following_ids)

def get_following_ids(clerk_id: str, db: Session):
    following = (
        db.query(models.Follow.following_clerk_id)
        .filter(models.Follow.follower_clerk_id == clerk_id)
        .all()
    )

    return [f[0] for f in following]

@router.get("/suggestions")
def get_suggestions(
    limit: int = Query(6, ge=1, le=20),
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    me = db.query(models.User).filter(
        models.User.clerk_id == clerk_id
    ).first()

    if not me:
        return {
            "same_hospital": [],
            "same_specialization": [],
        }

    following_ids = get_following_ids(clerk_id, db)

    excluded_ids = set(following_ids)
    excluded_ids.add(clerk_id)

    # 🏥 SAME HOSPITAL
    same_hospital = []
    if me.hospital:
        hospital_users = (
            db.query(models.User)
            .filter(
                models.User.hospital == me.hospital,
                ~models.User.clerk_id.in_(excluded_ids),
            )
            .limit(limit)
            .all()
        )

        same_hospital = hospital_users

        for user in hospital_users:
            excluded_ids.add(user.clerk_id)

    # 🧑‍⚕️ SAME SPECIALIZATION
    same_specialization = []
    if me.specialization:
        specialization_users = (
            db.query(models.User)
            .filter(
                models.User.specialization == me.specialization,
                ~models.User.clerk_id.in_(excluded_ids),
            )
            .limit(limit)
            .all()
        )

        same_specialization = specialization_users

    def enrich(user):
        return {
            "clerk_id": user.clerk_id,
            "id": user.id,
            "city": user.city,
            "state": user.state,
            "hospital": user.hospital,
            "specialization": user.specialization,
            "experience": user.experience,
            "name": get_user_display_name(user),
            "avatar": user.avatar_url,
        }

    return {
        "same_hospital": [enrich(u) for u in same_hospital],
        "same_specialization": [enrich(u) for u in same_specialization],
    }
