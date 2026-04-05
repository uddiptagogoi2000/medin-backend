import logging
import re
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query as FastQuery
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import verify_token
from app.identity import get_user_display_name
from app.routers.users import get_db

logger = logging.getLogger(__name__)

def extract_preview_text(content_json: dict, limit: int = 180) -> str:
    text_parts = []

    def walk(node):
        if node.get("type") == "text":
            text_parts.append(node.get("text", ""))
        for child in node.get("content", []) or []:
            walk(child)

    walk(content_json)

    full_text = " ".join(text_parts)

    # Clean multiple spaces / newlines
    full_text = re.sub(r"\s+", " ", full_text).strip()

    return full_text[:limit]


def extract_first_image(content_json: dict) -> Optional[str]:
    def walk(node):
        if node.get("type") == "image":
            return node.get("attrs", {}).get("src")
        for child in node.get("content", []) or []:
            result = walk(child)
            if result:
                return result
        return None

    return walk(content_json)


def normalize_tags(tags: Optional[List[str]]) -> List[str]:
    if not tags:
        return []

    normalized_tags = []
    seen = set()

    for tag in tags:
        normalized = re.sub(r"\s+", " ", tag.strip().lower())
        if not normalized or normalized in seen:
            continue

        normalized_tags.append(normalized)
        seen.add(normalized)

    return normalized_tags


def can_view_post(post: models.Post, viewer_clerk_id: str, db: Session) -> bool:
    if post.visibility == "public":
        return True

    if post.author_clerk_id == viewer_clerk_id:
        return True

    if post.visibility == "private":
        return False

    return (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_clerk_id == viewer_clerk_id,
            models.Follow.following_clerk_id == post.author_clerk_id,
        )
        .first()
        is not None
    )

router = APIRouter(prefix="/posts", tags=["Posts"])


def build_post_feed_responses(
    posts: List[models.Post],
    viewer_clerk_id: str,
    db: Session,
):
    if not posts:
        return []

    enrich_started_at = time.perf_counter()
    post_ids = [post.id for post in posts]
    author_ids = list({post.author_clerk_id for post in posts})

    db_users = (
        db.query(models.User)
        .filter(models.User.clerk_id.in_(author_ids))
        .all()
    )
    db_user_map = {user.clerk_id: user for user in db_users}

    like_count_rows = (
        db.query(models.Like.post_id, func.count(models.Like.id))
        .filter(models.Like.post_id.in_(post_ids))
        .group_by(models.Like.post_id)
        .all()
    )
    like_counts = {post_id: count for post_id, count in like_count_rows}

    comment_count_rows = (
        db.query(models.Comment.post_id, func.count(models.Comment.id))
        .filter(models.Comment.post_id.in_(post_ids))
        .group_by(models.Comment.post_id)
        .all()
    )
    comment_counts = {post_id: count for post_id, count in comment_count_rows}

    repost_count_rows = (
        db.query(models.Repost.post_id, func.count(models.Repost.id))
        .filter(models.Repost.post_id.in_(post_ids))
        .group_by(models.Repost.post_id)
        .all()
    )
    repost_counts = {post_id: count for post_id, count in repost_count_rows}

    liked_post_ids = {
        row[0]
        for row in db.query(models.Like.post_id)
        .filter(
            models.Like.user_clerk_id == viewer_clerk_id,
            models.Like.post_id.in_(post_ids),
        )
        .all()
    }

    reposted_post_ids = {
        row[0]
        for row in db.query(models.Repost.post_id)
        .filter(
            models.Repost.user_clerk_id == viewer_clerk_id,
            models.Repost.post_id.in_(post_ids),
        )
        .all()
    }

    followed_author_ids = {
        row[0]
        for row in db.query(models.Follow.following_clerk_id)
        .filter(
            models.Follow.follower_clerk_id == viewer_clerk_id,
            models.Follow.following_clerk_id.in_(author_ids),
        )
        .all()
    }

    responses = []
    for post in posts:
        db_user = db_user_map.get(post.author_clerk_id)

        if post.is_anonymous:
            author_name = "Anonymous Doctor"
            author_avatar = None
            author_specialization = None
            author_hospital = None
        else:
            author_name = get_user_display_name(db_user)
            author_avatar = db_user.avatar_url if db_user else None
            author_specialization = db_user.specialization if db_user else None
            author_hospital = db_user.hospital if db_user else None

        responses.append({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "preview_text": post.preview_text,
            "first_image": post.first_image,
            "tags": post.tags or [],
            "visibility": post.visibility,
            "is_anonymous": post.is_anonymous,
            "author_clerk_id": post.author_clerk_id,
            "created_at": post.created_at,
            "author_name": author_name,
            "author_avatar": author_avatar,
            "author_specialization": author_specialization,
            "author_hospital": author_hospital,
            "like_count": like_counts.get(post.id, 0),
            "comment_count": comment_counts.get(post.id, 0),
            "repost_count": repost_counts.get(post.id, 0),
            "is_liked_by_me": post.id in liked_post_ids,
            "is_reposted_by_me": post.id in reposted_post_ids,
            "is_following_author": post.author_clerk_id in followed_author_ids,
        })

    logger.info(
        "post_enrichment viewer=%s posts=%d authors=%d duration_ms=%d",
        viewer_clerk_id,
        len(posts),
        len(author_ids),
        int((time.perf_counter() - enrich_started_at) * 1000),
    )

    return responses


def build_post_feed_response(
    post: models.Post,
    viewer_clerk_id: str,
    db: Session,
):
    return build_post_feed_responses([post], viewer_clerk_id, db)[0]

@router.post("/", response_model=schemas.PostFeedResponse)
def create_post(
    post: schemas.PostCreate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    preview_text = extract_preview_text(post.content)
    first_image = extract_first_image(post.content)

    new_post = models.Post(
        title=post.title,
        content=post.content,
        preview_text=preview_text,
        first_image=first_image,
        tags=normalize_tags(post.tags),
        visibility=post.visibility,
        is_anonymous=post.is_anonymous,
        author_clerk_id=clerk_id,
    )

    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    return build_post_feed_response(new_post, clerk_id, db)

@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    post = (
        db.query(models.Post)
        .filter(models.Post.id == post_id)
        .first()
    )

    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found"
        )

    # 🔐 Only author can delete
    if post.author_clerk_id != clerk_id:
        raise HTTPException(
            status_code=403,
            detail="Not allowed to delete this post"
        )

    # Delete related likes/comments first (optional but safer)
    db.query(models.Like).filter(
        models.Like.post_id == post_id
    ).delete()

    db.query(models.Comment).filter(
        models.Comment.post_id == post_id
    ).delete()

    db.delete(post)
    db.commit()

    return {
        "success": True,
        "message": "Post deleted"
    }

@router.put("/{post_id}", response_model=schemas.PostFeedResponse)
def edit_post(
    post_id: int,
    post: schemas.PostUpdate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    existing_post = (
        db.query(models.Post)
        .filter(models.Post.id == post_id)
        .first()
    )

    if not existing_post:
        raise HTTPException(
            status_code=404,
            detail="Post not found"
        )

    # 🔐 Only author can edit
    if existing_post.author_clerk_id != clerk_id:
        raise HTTPException(
            status_code=403,
            detail="Not allowed to edit this post"
        )

    has_updates = False

    if post.title is not None:
        existing_post.title = post.title
        has_updates = True

    if post.content is not None:
        existing_post.content = post.content
        existing_post.preview_text = extract_preview_text(post.content)
        existing_post.first_image = extract_first_image(post.content)
        has_updates = True

    if post.visibility is not None:
        existing_post.visibility = post.visibility
        has_updates = True

    if post.is_anonymous is not None:
        existing_post.is_anonymous = post.is_anonymous
        has_updates = True

    if post.tags is not None:
        existing_post.tags = normalize_tags(post.tags)
        has_updates = True

    if not has_updates:
        raise HTTPException(
            status_code=400,
            detail="No fields provided to update"
        )

    db.commit()
    db.refresh(existing_post)

    return build_post_feed_response(existing_post, clerk_id, db)
 
@router.get("/", response_model=list[schemas.PostFeedResponse])
def get_posts(
    skip: int = 0,
    limit: int = FastQuery(10, ge=1, le=50),
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")
    started_at = time.perf_counter()

    following_ids = db.query(models.Follow.following_clerk_id).filter(
        models.Follow.follower_clerk_id == clerk_id
    )

    posts = (
        db.query(models.Post)
        .filter(
            or_(
                models.Post.visibility == "public",
                models.Post.author_clerk_id == clerk_id,
                models.Post.author_clerk_id.in_(following_ids),
            )
        )
        .order_by(models.Post.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    responses = build_post_feed_responses(posts, clerk_id, db)
    logger.info(
        "get_posts viewer=%s skip=%d limit=%d posts=%d duration_ms=%d",
        clerk_id,
        skip,
        limit,
        len(posts),
        int((time.perf_counter() - started_at) * 1000),
    )
    return responses

@router.get("/{post_id}", response_model=schemas.PostFeedResponse)
def get_single_post(
    post_id: int,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    post = db.query(models.Post).filter(models.Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if not can_view_post(post, clerk_id, db):
        raise HTTPException(status_code=403, detail="Not allowed")

    return build_post_feed_response(post, clerk_id, db)

@router.post("/{post_id}/like")
def toggle_like(
    post_id: int,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    existing = (
        db.query(models.Like)
        .filter(
            models.Like.post_id == post_id,
            models.Like.user_clerk_id == clerk_id,
        )
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"liked": False}

    new_like = models.Like(
        post_id=post_id,
        user_clerk_id=clerk_id,
    )
    db.add(new_like)
    db.commit()

    return {"liked": True}


@router.post("/{post_id}/repost")
def toggle_repost(
    post_id: int,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    post = db.query(models.Post).filter(models.Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.author_clerk_id == clerk_id:
        raise HTTPException(status_code=400, detail="Cannot repost your own post")

    if post.is_anonymous:
        raise HTTPException(status_code=400, detail="Anonymous posts cannot be reposted")

    if not can_view_post(post, clerk_id, db):
        raise HTTPException(status_code=403, detail="Not allowed")

    existing = (
        db.query(models.Repost)
        .filter(
            models.Repost.post_id == post_id,
            models.Repost.user_clerk_id == clerk_id,
        )
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"reposted": False}

    repost = models.Repost(
        post_id=post_id,
        user_clerk_id=clerk_id,
    )
    db.add(repost)
    db.commit()

    return {"reposted": True}

@router.post("/{post_id}/comment", response_model=schemas.CommentResponse)
def create_comment(
    post_id: int,
    comment: schemas.CommentCreate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    post = db.query(models.Post).filter(models.Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if not can_view_post(post, clerk_id, db):
        raise HTTPException(status_code=403, detail="Not allowed")

    new_comment = models.Comment(
        post_id=post_id,
        author_clerk_id=clerk_id,
        content=comment.content,
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    db_user = db.query(models.User).filter(
        models.User.clerk_id == clerk_id
    ).first()

    return {
        "id": new_comment.id,
        "post_id": new_comment.post_id,
        "content": new_comment.content,
        "created_at": new_comment.created_at,
        "author": {
            "clerk_id": clerk_id,
            "name": get_user_display_name(db_user),
            "avatar": db_user.avatar_url if db_user else None,
            "specialization": db_user.specialization if db_user else None,
            "hospital": db_user.hospital if db_user else None,
        }
    }

@router.delete("/{post_id}/comment/{comment_id}")
def delete_comment(
    post_id: int,
    comment_id: int,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    comment = (
        db.query(models.Comment)
        .filter(
            models.Comment.id == comment_id,
            models.Comment.post_id == post_id,
        )
        .first()
    )

    if not comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    if comment.author_clerk_id != clerk_id:
        raise HTTPException(
            status_code=403,
            detail="Not allowed to delete this comment"
        )

    db.delete(comment)
    db.commit()

    return {
        "success": True,
        "message": "Comment deleted"
    }

@router.put("/{post_id}/comment/{comment_id}", response_model=schemas.CommentResponse)
def edit_comment(
    post_id: int,
    comment_id: int,
    comment: schemas.CommentUpdate,
    payload=Depends(verify_token),
    db: Session = Depends(get_db),
):
    clerk_id = payload.get("sub")

    existing_comment = (
        db.query(models.Comment)
        .filter(
            models.Comment.id == comment_id,
            models.Comment.post_id == post_id,
        )
        .first()
    )

    if not existing_comment:
        raise HTTPException(
            status_code=404,
            detail="Comment not found"
        )

    if existing_comment.author_clerk_id != clerk_id:
        raise HTTPException(
            status_code=403,
            detail="Not allowed to edit this comment"
        )

    existing_comment.content = comment.content
    db.commit()
    db.refresh(existing_comment)

    db_user = db.query(models.User).filter(
        models.User.clerk_id == clerk_id
    ).first()

    return {
        "id": existing_comment.id,
        "post_id": existing_comment.post_id,
        "content": existing_comment.content,
        "created_at": existing_comment.created_at,
        "author": {
            "clerk_id": clerk_id,
            "name": get_user_display_name(db_user),
            "avatar": db_user.avatar_url if db_user else None,
            "specialization": db_user.specialization if db_user else None,
            "hospital": db_user.hospital if db_user else None,
        }
    }

@router.get("/{post_id}/comments")
def get_comments(
    post_id: int,
    skip: int = 0,
    limit: int = FastQuery(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.Comment)
        .filter(models.Comment.post_id == post_id)
        .order_by(models.Comment.created_at.desc())
    )

    comments = query.offset(skip).limit(limit + 1).all()

    has_more = len(comments) > limit
    comments = comments[:limit]

    clerk_ids = list({c.author_clerk_id for c in comments})
    db_users = (
        db.query(models.User)
        .filter(models.User.clerk_id.in_(clerk_ids))
        .all()
    )

    db_user_map = {
        user.clerk_id: user
        for user in db_users
    }

    result = []

    for comment in comments:
        db_user = db_user_map.get(comment.author_clerk_id)

        result.append({
            "id": comment.id,
            "post_id": comment.post_id,
            "content": comment.content,
            "created_at": comment.created_at,
            "author": {
                "clerk_id": comment.author_clerk_id,
                "name": get_user_display_name(db_user),
                "avatar": db_user.avatar_url if db_user else None,
                "specialization": db_user.specialization if db_user else None,
                "hospital": db_user.hospital if db_user else None,
            }
        })

    return {
        "comments": result,
        "has_more": has_more,
    }
