from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app import models, schemas
from app.identity import build_full_name, get_user_display_name
from app.auth import verify_token
from app.routers.posts import build_post_feed_responses
from app.routers.users import get_db
from app.clerk_client import clerk

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.get("/me")
def get_my_profile(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    # 1️⃣ Fetch user from DB
    user = db.query(models.User).filter(
        models.User.clerk_id == clerk_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "identity": {
            "clerk_id": clerk_id,
            "name": get_user_display_name(user),
            "avatar": user.avatar_url,
        },
        "basic": {
            "city": user.city,
            "state": user.state,
            "specialization": user.specialization,
            "hospital": user.hospital,
            "experience": user.experience,
        },
    }

@router.get("/{clerk_id}")
def get_public_profile(
    clerk_id: str,
    db: Session = Depends(get_db),
):
    # 1️⃣ Fetch user from DB
    user = db.query(models.User).filter(
        models.User.clerk_id == clerk_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2️⃣ Fetch related sections
    experiences = db.query(models.Experience).filter(
        models.Experience.user_clerk_id == clerk_id
    ).all()

    educations = db.query(models.Education).filter(
        models.Education.user_clerk_id == clerk_id
    ).all()

    publications = db.query(models.Publication).filter(
        models.Publication.user_clerk_id == clerk_id
    ).all()

    # 3️⃣ Stats
    cases_count = db.query(models.Post).filter(
        models.Post.author_clerk_id == clerk_id
    ).count()

    followers_count = db.query(models.Follow).filter(
        models.Follow.following_clerk_id == clerk_id
    ).count()

    following_count = db.query(models.Follow).filter(
        models.Follow.follower_clerk_id == clerk_id
    ).count()

    return {
        "identity": {
            "clerk_id": clerk_id,
            "name": get_user_display_name(user),
            "avatar": user.avatar_url,
        },
        "basic": {
            "city": user.city,
            "state": user.state,
            "specialization": user.specialization,
            "hospital": user.hospital,
            "experience": user.experience,
            "about": user.about,
        },
        "stats": {
            "cases_count": cases_count,
            "followers": followers_count,
            "following": following_count,
        },
        "experiences": experiences,
        "educations": educations,
        "publications": publications,
    }


@router.put("/basic")
def update_basic_info(
    data: schemas.ProfileBasicUpdate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    user = db.query(models.User).filter(
        models.User.clerk_id == clerk_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return user

@router.put("/about")
def update_about(
    data: schemas.ProfileAboutUpdate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    user = db.query(models.User).filter(
        models.User.clerk_id == clerk_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.about = data.about

    db.commit()
    db.refresh(user)

    return {"message": "About updated successfully"}

@router.post("/experience")
def add_experience(
    data: schemas.ExperienceCreate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    exp = models.Experience(
        user_clerk_id=clerk_id,
        **data.dict()
    )

    db.add(exp)
    db.commit()
    db.refresh(exp)

    return exp

@router.put("/experience/{exp_id}")
def update_experience(
    exp_id: int,
    data: schemas.ExperienceUpdate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    exp = db.query(models.Experience).filter(
        models.Experience.id == exp_id,
        models.Experience.user_clerk_id == clerk_id
    ).first()

    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(exp, field, value)

    db.commit()
    db.refresh(exp)

    return exp

@router.delete("/experience/{exp_id}")
def delete_experience(
    exp_id: int,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    exp = db.query(models.Experience).filter(
        models.Experience.id == exp_id,
        models.Experience.user_clerk_id == clerk_id
    ).first()

    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")

    db.delete(exp)
    db.commit()

    return {"message": "Experience deleted"}

@router.post("/education")
def add_education(
    data: schemas.EducationCreate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    edu = models.Education(
        user_clerk_id=clerk_id,
        **data.dict()
    )

    db.add(edu)
    db.commit()
    db.refresh(edu)

    return edu

@router.put("/education/{edu_id}")
def update_education(
    edu_id: int,
    data: schemas.EducationUpdate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    edu = db.query(models.Education).filter(
        models.Education.id == edu_id,
        models.Education.user_clerk_id == clerk_id
    ).first()

    if not edu:
        raise HTTPException(status_code=404, detail="Education not found")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(edu, field, value)

    db.commit()
    db.refresh(edu)

    return edu

@router.delete("/education/{edu_id}")
def delete_education(
    edu_id: int,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    edu = db.query(models.Education).filter(
        models.Education.id == edu_id,
        models.Education.user_clerk_id == clerk_id
    ).first()

    if not edu:
        raise HTTPException(status_code=404, detail="Education not found")

    db.delete(edu)
    db.commit()

    return {"message": "Education deleted"}

@router.post("/publication")
def add_publication(
    data: schemas.PublicationCreate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    pub = models.Publication(
        user_clerk_id=clerk_id,
        **data.dict()
    )

    db.add(pub)
    db.commit()
    db.refresh(pub)

    return pub

@router.put("/publication/{pub_id}")
def update_publication(
    pub_id: int,
    data: schemas.PublicationUpdate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    pub = db.query(models.Publication).filter(
        models.Publication.id == pub_id,
        models.Publication.user_clerk_id == clerk_id
    ).first()

    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(pub, field, value)

    db.commit()
    db.refresh(pub)

    return pub

@router.delete("/publication/{pub_id}")
def delete_publication(
    pub_id: int,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    pub = db.query(models.Publication).filter(
        models.Publication.id == pub_id,
        models.Publication.user_clerk_id == clerk_id
    ).first()

    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    db.delete(pub)
    db.commit()

    return {"message": "Publication deleted"}

@router.put("/avatar")
async def update_avatar(
    file: UploadFile = File(...),
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.clerk_id == clerk_id).first()

    try:
        file_bytes = await file.read()  # 👈 IMPORTANT

        res = clerk.users.set_profile_image(
            user_id=clerk_id,
            file={
                "file_name": file.filename,
                "content": file_bytes,
            },
        )

        if user:
            user.avatar_url = res.image_url
            db.commit()

        return {
            "avatar_url": res.image_url
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Avatar upload failed")
    
@router.delete("/avatar")
def delete_avatar(
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.clerk_id == clerk_id).first()

    try:
        clerk.users.delete_profile_image(user_id=clerk_id)

        updated_user = clerk.users.get(user_id=clerk_id)

        if user:
            user.avatar_url = updated_user.image_url
            db.commit()

        return {
            "avatar_url": updated_user.image_url
        }

    except Exception:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to delete avatar")

@router.put("/identity")
def update_identity(
    data: schemas.ProfileIdentityUpdate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")
    user = db.query(models.User).filter(models.User.clerk_id == clerk_id).first()

    update_data = {}

    if data.first_name is not None:
        update_data["first_name"] = data.first_name

    if data.last_name is not None:
        update_data["last_name"] = data.last_name

    if update_data:
        clerk.users.update(
            user_id=clerk_id,
            **update_data
        )

    if user:
        first_name = data.first_name if data.first_name is not None else user.first_name
        last_name = data.last_name if data.last_name is not None else user.last_name
        user.first_name = first_name
        user.last_name = last_name
        user.full_name = build_full_name(first_name, last_name)
        db.commit()

    return {"message": "Identity updated"}

@router.get("/{clerk_id}/activity/posts", response_model=list[schemas.PostFeedResponse])
def get_user_posts_activity(
    clerk_id: str,
    skip: int = 0,
    limit: int = 10,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    viewer_clerk_id = payload.get("sub")

    posts = (
        db.query(models.Post)
        .filter(
            models.Post.author_clerk_id == clerk_id,
            models.Post.is_anonymous == False,
        )
        .order_by(models.Post.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return build_post_feed_responses(posts, viewer_clerk_id, db)

@router.get("/{clerk_id}/activity/comments")
def get_user_comments_activity(
    clerk_id: str,
    skip: int = 0,
    limit: int = 10,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    comments = (
        db.query(models.Comment)
        .filter(models.Comment.author_clerk_id == clerk_id)
        .order_by(models.Comment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    post_ids = [comment.post_id for comment in comments]
    posts = (
        db.query(models.Post)
        .filter(models.Post.id.in_(post_ids))
        .all()
    )
    post_map = {post.id: post for post in posts}

    return [{
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at,
            "post": {
                "id": post.id,
                "title": post.title,
                "preview_text": post.preview_text,
                "first_image": post.first_image,
            } if post else None
        } for comment in comments for post in [post_map.get(comment.post_id)]]

@router.get("/{clerk_id}/activity/likes")
def get_user_likes_activity(
    clerk_id: str,
    skip: int = 0,
    limit: int = 10,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    likes = (
        db.query(models.Like)
        .filter(models.Like.user_clerk_id == clerk_id)
        .order_by(models.Like.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    post_ids = [like.post_id for like in likes]

    posts = (
        db.query(models.Post)
        .filter(models.Post.id.in_(post_ids))
        .all()
    )

    post_map = {post.id: post for post in posts}

    result = []

    for like in likes:
        post = post_map.get(like.post_id)

        if not post:
            continue

        result.append({
            "liked_at": like.created_at,
            "post": {
                "id": post.id,
                "title": post.title,
                "preview_text": post.preview_text,
                "first_image": post.first_image,
                "created_at": post.created_at,
            }
        })

    return result


@router.get("/{clerk_id}/activity/reposts", response_model=list[schemas.PostFeedResponse])
def get_user_reposts_activity(
    clerk_id: str,
    skip: int = 0,
    limit: int = 10,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    viewer_clerk_id = payload.get("sub")

    reposts = (
        db.query(models.Repost)
        .filter(models.Repost.user_clerk_id == clerk_id)
        .order_by(models.Repost.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    post_ids = [repost.post_id for repost in reposts]

    posts = (
        db.query(models.Post)
        .filter(models.Post.id.in_(post_ids))
        .all()
    )

    post_map = {post.id: post for post in posts}

    ordered_posts = [
        post_map[repost.post_id]
        for repost in reposts
        if repost.post_id in post_map
    ]

    return build_post_feed_responses(ordered_posts, viewer_clerk_id, db)
