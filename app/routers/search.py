from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import verify_token
from app.identity import get_user_display_name
from app.routers.users import get_db

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/", response_model=schemas.GlobalSearchResponse)
def global_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=10),
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")
    query = q.strip()
    normalized_query = query.lower()

    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    like_pattern = f"%{query}%"
    prefix_pattern = f"{query}%"
    tag_like_pattern = f"%{normalized_query}%"

    following_ids = db.query(models.Follow.following_clerk_id).filter(
        models.Follow.follower_clerk_id == clerk_id
    )

    db_matched_users = (
        db.query(models.User)
        .filter(
            or_(
                models.User.doctor_id.ilike(like_pattern),
                models.User.city.ilike(like_pattern),
                models.User.state.ilike(like_pattern),
                models.User.specialization.ilike(like_pattern),
                models.User.hospital.ilike(like_pattern),
                models.User.clerk_id.ilike(like_pattern),
                models.User.first_name.ilike(like_pattern),
                models.User.last_name.ilike(like_pattern),
                models.User.full_name.ilike(like_pattern),
            )
        )
        .order_by(
            case(
                (models.User.full_name.ilike(prefix_pattern), 0),
                (models.User.first_name.ilike(prefix_pattern), 1),
                (models.User.last_name.ilike(prefix_pattern), 2),
                (models.User.specialization.ilike(prefix_pattern), 0),
                (models.User.hospital.ilike(prefix_pattern), 3),
                (models.User.city.ilike(prefix_pattern), 4),
                else_=5,
            ),
            models.User.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
    users = db_matched_users

    posts = (
        db.query(models.Post)
        .filter(
            or_(
                models.Post.visibility == "public",
                models.Post.author_clerk_id == clerk_id,
                models.Post.author_clerk_id.in_(following_ids),
            )
        )
        .filter(
            or_(
                models.Post.title.ilike(like_pattern),
                models.Post.preview_text.ilike(like_pattern),
                func.array_to_string(models.Post.tags, " ").ilike(tag_like_pattern),
                models.Post.author_clerk_id.in_(
                    db.query(models.User.clerk_id).filter(
                        or_(
                            models.User.first_name.ilike(like_pattern),
                            models.User.last_name.ilike(like_pattern),
                            models.User.full_name.ilike(like_pattern),
                        )
                    )
                ),
            )
        )
        .order_by(
            case(
                (models.Post.title.ilike(prefix_pattern), 0),
                (models.Post.preview_text.ilike(prefix_pattern), 1),
                (func.array_to_string(models.Post.tags, " ").ilike(tag_like_pattern), 2),
                (
                    models.Post.author_clerk_id.in_(
                        db.query(models.User.clerk_id).filter(models.User.full_name.ilike(prefix_pattern))
                    ),
                    3,
                ),
                else_=3,
            ),
            models.Post.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    author_ids = list({post.author_clerk_id for post in posts})
    author_users = (
        db.query(models.User)
        .filter(models.User.clerk_id.in_(author_ids))
        .all()
    )
    author_user_map = {user.clerk_id: user for user in author_users}

    users_response = []
    for user in users:
        users_response.append(
            {
                "clerk_id": user.clerk_id,
                "name": get_user_display_name(user),
                "avatar": user.avatar_url,
                "doctor_id": user.doctor_id,
                "specialization": user.specialization,
                "hospital": user.hospital,
                "city": user.city,
                "state": user.state,
            }
        )

    posts_response = []
    for post in posts:
        if post.is_anonymous:
            author_name = "Anonymous Doctor"
            author_avatar = None
        else:
            author_user = author_user_map.get(post.author_clerk_id)
            author_name = get_user_display_name(author_user)
            author_avatar = author_user.avatar_url if author_user else None

        posts_response.append(
            {
                "id": post.id,
                "title": post.title,
                "preview_text": post.preview_text,
                "first_image": post.first_image,
                "tags": post.tags or [],
                "visibility": post.visibility,
                "is_anonymous": post.is_anonymous,
                "author_clerk_id": post.author_clerk_id,
                "author_name": author_name,
                "author_avatar": author_avatar,
                "created_at": post.created_at,
            }
        )

    return {
        "query": query,
        "users": users_response,
        "posts": posts_response,
    }
